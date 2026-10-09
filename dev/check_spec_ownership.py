"""Check unique live requirement ownership and the reviewed canonical audit."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def requirements(path):
    text = path.read_text()
    operation = None
    for section in re.split(r'(?=^## (?:ADDED|MODIFIED|REMOVED) Requirements)', text, flags=re.M):
        match = re.match(r'## (\w+) Requirements', section)
        if match:
            operation = match[1]
        for block in re.split(r'(?=^### Requirement: )', section, flags=re.M)[1:]:
            block = re.split(r'^## ', block, flags=re.M)[0].strip() + '\n'
            title = block.splitlines()[0].removeprefix('### Requirement: ')
            yield (path.parent.name, title), operation, block


def audit_sources(audit):
    reviewed = {(row['source'], (row['capability'], row['requirement'])): row
                for row in audit['entries'] if row['disposition'] != 'superseded'}
    errors = []
    for pattern in ('*/specs/*/spec.md', 'archive/*/specs/*/spec.md'):
        for path in sorted((ROOT / 'openspec/changes').glob(pattern)):
            for key, _, block in requirements(path):
                row = reviewed.get((str(path.relative_to(ROOT)), key))
                if row is None:
                    errors.append(f'Unaudited requirement source: {path}: {key}')
                elif hashlib.sha256(block.encode()).hexdigest() != row['source_requirement_sha256']:
                    errors.append(f'Requirement source changed without audit: {path}: {key}')
    return errors


def main():
    canonical = {}
    owners = {}
    errors = []
    for path in sorted((ROOT / 'openspec/specs').glob('*/spec.md')):
        for key, _, block in requirements(path):
            if key in canonical:
                errors.append(f'Duplicate canonical requirement: {key}')
            canonical[key] = block
    for path in sorted((ROOT / 'openspec/changes').glob('*/specs/*/spec.md')):
        for key, operation, _ in requirements(path):
            if key in owners:
                errors.append(f'Duplicate live delta ownership: {key}: {owners[key]} and {path}')
            owners[key] = path
            if operation == 'MODIFIED' and key not in canonical:
                errors.append(f'MODIFIED requirement lacks canonical baseline: {key}')
            if operation == 'ADDED' and key in canonical:
                errors.append(f'ADDED requirement already exists in baseline: {key}')
    audit = json.loads((ROOT / 'openspec/baseline-audit.json').read_text())
    errors.extend(audit_sources(audit))
    verified = { (row['capability'], row['requirement']): row for row in audit['entries']
                 if row['disposition'].startswith('verified') }
    if set(verified) != set(canonical):
        errors.append('Canonical inventory differs from reviewed verified audit entries')
    for key, row in verified.items():
        if key in canonical and hashlib.sha256(canonical[key].encode()).hexdigest() != (
            row['canonical_requirement_sha256']
        ):
            errors.append(f'Canonical wording changed without audit reconciliation: {key}')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'{len(canonical)} canonical requirements; {len(owners)} uniquely owned live deltas; '
          f"{len(audit['entries'])} historical/active source blocks audited")


if __name__ == '__main__':
    main()
