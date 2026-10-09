"""Collect a frozen, bounded GitHub file survey without checking out repositories."""

import argparse
import collections
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
ALIASES = {'jpeg': 'jpg', 'jpe': 'jpg', 'apng': 'png'}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def extension(path):
    name = PurePosixPath(path).name.lower()
    for suffix in ('tar.gz', 'tar.bz2', 'tar.xz', 'tar.zst'):
        if name.endswith('.' + suffix):
            return suffix
    suffix = name.rsplit('.', 1)[1] if '.' in name.lstrip('.') else ''
    return ALIASES.get(suffix, suffix)


def size_bucket(size):
    if size < 4096:
        return 'tiny'
    if size < 65536:
        return 'small'
    if size < 1048576:
        return 'medium'
    return 'large'


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def request_bytes(url, limit, token=None):
    headers = {'User-Agent': 'filerepack-format-survey/1', 'Accept': 'application/vnd.github+json'}
    # Credentials never accompany downloads from raw.githubusercontent.com.
    if token and url.startswith('https://api.github.com/'):
        headers['Authorization'] = 'Bearer ' + token
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('HTTP body exceeds configured byte limit')
            return data
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError('HTTP {} for {}'.format(error.code, url)) from error
        except URLError:
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError('Request failed')


class GitHub:
    def __init__(self, cache):
        self.cache = cache
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')

    def get(self, path):
        key = hashlib.sha256(path.encode()).hexdigest()
        cached = self.cache / (key + '.json')
        if cached.exists():
            return json.loads(cached.read_text(encoding='utf-8'))
        value = json.loads(request_bytes('https://api.github.com/' + path, 24 * 1024**2,
                                        self.token))
        write_json(cached, value)
        return value

    def tree(self, repo, tree_sha):
        value = self.get('repos/{}/git/trees/{}?recursive=1'.format(repo, tree_sha))
        if not value.get('truncated'):
            return value['tree']
        # Never treat an incomplete recursive response as a complete census.
        entries = []
        pending = [('', tree_sha)]
        while pending:
            prefix, sha = pending.pop()
            tree = self.get('repos/{}/git/trees/{}'.format(repo, sha))
            if tree.get('truncated'):
                raise ValueError('Non-recursive Git tree is truncated')
            for item in tree['tree']:
                item = dict(item, path=prefix + item['path'])
                entries.append(item)
                if item['type'] == 'tree':
                    pending.append((item['path'] + '/', item['sha']))
        return entries


def collect_inventory(config, run):
    github = GitHub(run / 'api-cache')
    manifest_path = run / 'repositories.json'
    manifests = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    frozen = {item['name']: item for item in manifests if item.get('commit_sha')}
    rows = []
    errors = []
    for spec in config['repositories']:
        repo = spec['name']
        print('inventory ' + repo, flush=True)
        try:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
                raise ValueError('Invalid repository name')
            snapshot = frozen.get(repo)
            if snapshot is None:
                metadata = github.get('repos/' + repo)
                branch = quote(metadata['default_branch'], safe='')
                commit = github.get('repos/{}/commits/{}'.format(repo, branch))
                snapshot = {
                    **spec, 'commit_sha': commit['sha'],
                    'tree_sha': commit['commit']['tree']['sha'],
                    'default_branch': metadata['default_branch'],
                    'stars': metadata['stargazers_count'],
                    'license': (metadata.get('license') or {}).get('spdx_id'),
                    'collected_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                }
                manifests.append(snapshot)
                frozen[repo] = snapshot
                write_json(manifest_path, manifests)
            entries = github.tree(repo, snapshot['tree_sha'])
            regular = [x for x in entries if x['type'] == 'blob'
                       and x.get('mode') in ('100644', '100755')]
            snapshot['regular_file_count'] = len(regular)
            snapshot['excluded_links_submodules'] = sum(
                x.get('mode') in ('120000', '160000') for x in entries
            )
            snapshot['inventory_complete'] = True
            for item in regular:
                path = item['path']
                rows.append({
                    'repository': repo, 'stratum': spec['stratum'],
                    'commit_sha': snapshot['commit_sha'], 'path': path,
                    'blob_sha': item['sha'], 'size': item.get('size', 0),
                    'format': extension(path), 'size_bucket': size_bucket(item.get('size', 0)),
                    'role': 'test' if re.search(r'(^|/)(tests?|fixtures?)(/|$)', path) else 'other',
                })
        except (RuntimeError, ValueError, URLError, KeyError) as error:
            errors.append({'repository': repo, 'error': str(error)})
            print('inventory failed: {}: {}'.format(repo, error), flush=True)
        write_json(manifest_path, manifests)
    with (run / 'inventory.jsonl').open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_json(run / 'collection-errors.json', errors)
    return rows


def inventory_statistics(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row['format']].append(row)
    result = []
    for kind, items in groups.items():
        unique = {row['blob_sha']: row['size'] for row in items}
        result.append({
            'format': kind or '(none)', 'files': len(items),
            'repositories': len({row['repository'] for row in items}),
            'bytes': sum(row['size'] for row in items),
            'unique_blobs': len(unique), 'unique_blob_bytes': sum(unique.values()),
        })
    return sorted(result, key=lambda row: (-row['bytes'], row['format']))


def select_samples(rows, config):
    selected = []
    used = set()
    for kind in config['formats']:
        candidates = [row for row in rows if row['format'] == kind
                      and 0 < row['size'] <= config['max_file_bytes']]
        buckets = collections.defaultdict(list)
        for row in candidates:
            buckets[(row['repository'], row['size_bucket'])].append(row)
        for items in buckets.values():
            items.sort(key=lambda row: hashlib.sha256(
                (config['seed'] + row['repository'] + row['path']).encode()
            ).hexdigest())
        count = 0
        while buckets and count < config['per_format']:
            for key in sorted(list(buckets)):
                items = buckets[key]
                row = items.pop(0)
                if not items:
                    del buckets[key]
                if row['blob_sha'] in used:
                    continue
                used.add(row['blob_sha'])
                selected.append(row)
                count += 1
                if count == config['per_format']:
                    break
    return selected


def download_samples(samples, config, run):
    result = []
    downloaded = 0
    for row in samples:
        row = dict(row)
        suffix = '.' + row['format']
        relative = Path('inputs') / (row['blob_sha'] + suffix)
        target = run / relative
        url = 'https://raw.githubusercontent.com/{}/{}/{}'.format(
            row['repository'], row['commit_sha'], quote(row['path'], safe='/')
        )
        row.update(source_url=url, local_path=relative.as_posix())
        try:
            if downloaded + row['size'] > config['max_download_bytes']:
                row['download_status'] = 'budget_exceeded'
            else:
                data = target.read_bytes() if target.exists() else request_bytes(
                    url, config['max_file_bytes']
                )
                if len(data) != row['size'] or git_blob_sha(data) != row['blob_sha']:
                    raise ValueError('Downloaded bytes do not match frozen Git blob')
                downloaded += len(data)
                row['sha256'] = hashlib.sha256(data).hexdigest()
                if data.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
                    row['download_status'] = 'lfs_pointer'
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    row['download_status'] = 'downloaded'
        except (RuntimeError, ValueError, URLError, OSError) as error:
            row.update(download_status='download_failed', download_error=str(error))
        result.append(row)
        print('sample {} {} {}'.format(row['format'], row['download_status'], row['path']),
              flush=True)
        write_json(run / 'samples.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=HERE / 'config.json')
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    args.run.mkdir(parents=True, exist_ok=True)
    frozen_config = args.run / 'config.json'
    if frozen_config.exists() and json.loads(frozen_config.read_text()) != config:
        parser.error('Run configuration is frozen; use a new run directory for changes')
    write_json(frozen_config, config)
    rows = collect_inventory(config, args.run)
    stats = inventory_statistics(rows)
    write_json(args.run / 'inventory-summary.json', stats)
    with (args.run / 'inventory-summary.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stats[0]) if stats else ['format'])
        writer.writeheader()
        writer.writerows(stats)
    download_samples(select_samples(rows, config), config, args.run)
    print('Inventory: {} files; output: {}'.format(len(rows), args.run), flush=True)


if __name__ == '__main__':
    main()
