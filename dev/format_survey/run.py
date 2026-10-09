"""Run frozen samples in isolated processes; report independently verified final savings."""

import argparse
import collections
import csv
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

from collect import write_json
from verify import Unavailable, compare, digest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SCHEMA = 2


def snapshot_runtime(run):
    destination = run / 'runtime' / 'filerepack'
    if not destination.exists():
        destination.mkdir(parents=True)
        for source in sorted((ROOT / 'filerepack').rglob('*.py')):
            target = destination / source.relative_to(ROOT / 'filerepack')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    checksum = hashlib.sha256()
    for path in sorted(destination.rglob('*.py')):
        checksum.update(path.relative_to(destination).as_posix().encode() + b'\0')
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def environment(run):
    result = {
        'schema_version': SCHEMA, 'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'runtime_sha256': snapshot_runtime(run),
        'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'packages': {}, 'tools': {},
        'options': {'keep_meta': True, 'lossy': False, 'convert_container': False,
                    'keep_if_larger': True},
        'harness_sha256': hashlib.sha256(b''.join(
            path.read_bytes() for path in sorted(HERE.glob('*.py'))
            if not path.name.startswith('test_')
        )).hexdigest(),
    }
    for name in ('Pillow', 'pyarrow', 'duckdb', 'pikepdf', 'psutil', 'typer'):
        try:
            result['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result['packages'][name] = None
    for name, flag in [('7zz', 'i'), ('qpdf', '--version'), ('jpegtran', '-version'),
                       ('jpegoptim', '--version'), ('oxipng', '--version'),
                       ('optipng', '-version'), ('svgo', '--version'), ('scour', '--version'),
                       ('cwebp', '-version'), ('dwebp', '-version'), ('pdfinfo', '-v'),
                       ('pdftoppm', '-v'), ('rsvg-convert', '--version')]:
        path = shutil.which(name)
        if path is None:
            result['tools'][name] = None
            continue
        try:
            value = subprocess.run([path, flag], capture_output=True, timeout=5)
            version = (value.stdout + value.stderr).decode(errors='replace')[:2000].strip()
        except (OSError, subprocess.TimeoutExpired) as error:
            version = str(error)
        result['tools'][name] = {'path': path, 'version': version}
    return result


def worker(task_path):
    task = json.loads(task_path.read_text())
    run = Path(task['run'])
    sys.path.insert(0, str(run / 'runtime'))
    from filerepack import FileRepacker, RepackOptions
    source, output, scratch = map(Path, (task['source'], task['output'], task['scratch']))
    source_hash = digest(source)
    result = dict(task['sample'], profile=task['profile'], schema_version=SCHEMA)
    if source_hash != task['sample']['sha256']:
        result.update(status='input_hash_mismatch', verified_saved_bytes=0)
        write_json(Path(task['result']), result)
        return
    scratch.mkdir(parents=True, exist_ok=True)
    import tempfile
    tempfile.tempdir = str(scratch)
    os.environ['TMPDIR'] = os.environ['TEMP'] = os.environ['TMP'] = str(scratch)
    options = RepackOptions(
        quiet=True, keep_meta=True, lossy=False, convert_container=False,
        # Historical name: True REJECTS larger files (the CLI's --allow-grow=False).
        keep_if_larger=True, deep_walking=task['profile'] == 'deep',
        max_extract_bytes=task['decoded_byte_limit'], max_extract_ratio=100,
    )
    if task.get('profile_version') == 1:
        from filerepack import options_for_profile
        options = options_for_profile(
            task['profile'], quiet=True, convert_container=False,
            max_extract_bytes=task['decoded_byte_limit'], max_extract_ratio=100,
        )
    deep = task.get('profile_version') == 1 or task['profile'] == 'deep'
    started = time.monotonic()
    try:
        summary = FileRepacker(quiet=True, temppath=str(scratch)).repack(
            str(source), outfile=str(output), options=options
        )
        result['repack_elapsed_seconds'] = time.monotonic() - started
        result['library_summary'] = asdict(summary)
        published_output = output if output.exists() else source
        result['actual_output_bytes'] = published_output.stat().st_size
        result['output_sha256'] = digest(published_output) if output.exists() else None
        result['outcome_status'] = summary.outcome.status if summary.outcome else None
        result['outcome_reason'] = summary.outcome.reason if summary.outcome else None
        changed = result['output_sha256'] != source_hash
        if not output.exists():
            changed = False
        result['changed'] = changed
        result['raw_saved_bytes'] = source.stat().st_size - published_output.stat().st_size
        try:
            contract = compare(source, published_output, result['format'],
                               deep=deep, limit=task['decoded_byte_limit'],
                               keep_meta=options.keep_meta)
            result['verification_contract'] = contract
            result['status'] = 'verified_shrink' if changed else 'unchanged'
            if changed and result['raw_saved_bytes'] <= 0:
                result['status'] = 'unexpected_growth'
            if not output.exists() and result['outcome_status']:
                result['status'] = result['outcome_status']
        except Unavailable as error:
            result.update(status='verification_unavailable', verification_reason=str(error))
        except (ValueError, OSError, ImportError) as error:
            result.update(status='preservation_failed', verification_reason=str(error))
    except Exception as error:
        result.update(status='repack_error', error='{}: {}'.format(type(error).__name__, error))
    result['source_unchanged'] = digest(source) == source_hash
    if not result['source_unchanged']:
        result['status'] = 'source_changed'
    result['verified_saved_bytes'] = max(0, result.get('raw_saved_bytes', 0)) if (
        result['status'] == 'verified_shrink' and result['source_unchanged']
    ) else 0
    write_json(Path(task['result']), result)


def directory_bytes(path):
    total = 0
    for item in path.rglob('*'):
        try:
            if item.is_file():
                total += item.stat().st_size
        except FileNotFoundError:
            pass  # Encoders may remove their scratch between listing and stat.
    return total


def terminate(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        try:
            import psutil
            for child in psutil.Process(process.pid).children(recursive=True):
                child.kill()
        except Exception:
            pass
        process.kill()
    process.wait()


def execute_sample(sample, profile, config, run):
    key = sample['blob_sha'] + '-' + profile
    work = run / 'work' / key
    work.mkdir(parents=True, exist_ok=True)
    result_path = run / 'results' / (key + '.json')
    if result_path.exists():
        result = json.loads(result_path.read_text())
        if result.get('schema_version') != SCHEMA:
            raise ValueError('Cached benchmark uses a different harness schema')
        if result.get('sha256') != sample['sha256']:
            raise ValueError('Cached result belongs to different input bytes')
        if digest(run / sample['local_path']) != sample['sha256']:
            raise ValueError('Cached input bytes have changed')
        if result.get('output_sha256') and digest(run / result['output_path']) != (
            result['output_sha256']
        ):
            raise ValueError('Cached output bytes have changed')
        return result
    task = {
        'sample': sample, 'profile': profile, 'run': str(run),
        'source': str(run / sample['local_path']),
        'output': str(work / ('output.' + sample['format'])),
        'scratch': str(work / 'scratch'), 'result': str(result_path),
        'decoded_byte_limit': config['decoded_byte_limit'],
        'profile_version': config.get('profile_version'),
    }
    task_path = work / 'task.json'
    write_json(task_path, task)
    try:
        import psutil
    except ImportError:
        psutil = None
    peak_rss = None if psutil is None else 0
    peak_scratch = 0
    started = time.monotonic()
    timed_out = False
    with (work / 'worker.log').open('wb') as log:
        process = subprocess.Popen([sys.executable, str(HERE / 'run.py'), '--worker',
                                    str(task_path)], stdout=log, stderr=log,
                                   start_new_session=os.name == 'posix')
        while process.poll() is None:
            peak_scratch = max(peak_scratch, directory_bytes(work))
            if psutil is not None:
                try:
                    root = psutil.Process(process.pid)
                    processes = [root] + root.children(recursive=True)
                    rss = sum(item.memory_info().rss for item in processes if item.is_running())
                    peak_rss = max(peak_rss, rss)
                except psutil.Error:
                    pass
            if time.monotonic() - started > config['timeout_seconds']:
                timed_out = True
                terminate(process)
                break
            time.sleep(0.1)
    if timed_out or not result_path.exists():
        result = dict(sample, profile=profile, schema_version=SCHEMA,
                      status='timeout' if timed_out else 'worker_failed',
                      verified_saved_bytes=0,
                      source_unchanged=digest(run / sample['local_path']) == sample['sha256'])
    else:
        result = json.loads(result_path.read_text())
    result.update(elapsed_seconds=time.monotonic() - started,
                  sampled_peak_rss_bytes=peak_rss, sampled_peak_scratch_bytes=peak_scratch,
                  log_path=(work / 'worker.log').relative_to(run).as_posix(),
                  output_path=Path(task['output']).relative_to(run).as_posix())
    write_json(result_path, result)
    return result


def summarize(results):
    groups = collections.defaultdict(list)
    for row in results:
        groups[(row['format'], row['profile'])].append(row)
    summary = []
    for (kind, profile), rows in sorted(groups.items()):
        total = sum(row['size'] for row in rows)
        saved = sum(row['verified_saved_bytes'] for row in rows)
        statuses = collections.Counter(row['status'] for row in rows)
        summary.append({
            'format': kind, 'profile': profile, 'samples': len(rows),
            'input_bytes': total, 'verified_saved_bytes': saved,
            'weighted_savings_pct': 100 * saved / total if total else 0,
            'verified_shrinks': statuses['verified_shrink'],
            'unchanged': statuses['unchanged'],
            'unverified': sum(value for status, value in statuses.items()
                              if status not in ('verified_shrink', 'unchanged')),
            'preservation_failures': statuses['preservation_failed'] + statuses['source_changed'],
            'elapsed_seconds': sum(row.get('elapsed_seconds', 0) for row in rows),
            'statuses': dict(statuses),
        })
    return summary


def write_report(run, results):
    summary = summarize(results)
    write_json(run / 'benchmark-summary.json', summary)
    write_json(run / 'benchmark-results.json', results)
    with (run / 'benchmark-summary.csv').open('w', newline='', encoding='utf-8') as stream:
        fields = [key for key in summary[0] if key != 'statuses'] if summary else ['format']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(summary)
    lines = ['# GitHub file-format pilot', '',
             'A purposive sample; these results do not estimate all of GitHub.', '',
             '| Format | Profile | Files | Verified smaller | Unchanged | Unverified | '
             'Preservation failures | Verified bytes saved | Weighted saving |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in summary:
        lines.append('| {format} | {profile} | {samples} | {verified_shrinks} | {unchanged} | '
                     '{unverified} | {preservation_failures} | {verified_saved_bytes} | '
                     '{weighted_savings_pct:.2f}% |'.format(**row))
    lines += ['', 'All downloaded inputs, including retained/error/unverified cases, contribute '
              'to the byte denominator. Only smaller independently compared outputs contribute '
              'to savings. Archive shallow/deep rows are separate experiments; do not add them.',
              '', 'Resource peaks are sampled every 100 ms and include worker/tool descendants '
              'for RSS, and work directories for scratch. They can miss brief peaks. Timings '
              'include independent comparison and process startup; repack-only timing is in '
              'each result. See README.md for the exact contracts and limitations.', '',
              '## Cases requiring investigation', '']
    for row in results:
        if row['status'] not in ('unchanged', 'verified_shrink'):
            lines.append('- `{}` `{}` `{}`: {}'.format(
                row['format'], row['profile'], row['repository'] + '/' + row['path'],
                row.get('verification_reason') or row.get('error') or row['status']))
    (run / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    if args.run is None:
        parser.error('--run is required')
    run = args.run.resolve()
    config = json.loads((run / 'config.json').read_text())
    samples = json.loads((run / 'samples.json').read_text())
    env_path = run / 'environment.json'
    if not env_path.exists():
        write_json(env_path, environment(run))
    results = []
    for sample in samples:
        if sample['download_status'] != 'downloaded':
            continue
        profiles = ['shallow', 'deep'] if sample['format'] in ('zip', 'npz') else ['preserve']
        for profile in profiles:
            row = execute_sample(sample, profile, config, run)
            results.append(row)
            print('{} {} {} saved={}'.format(sample['format'], profile, row['status'],
                                             row['verified_saved_bytes']), flush=True)
            write_report(run, results)
    write_report(run, results)


if __name__ == '__main__':
    main()
