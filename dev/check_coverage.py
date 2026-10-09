"""Enforce measured line-coverage floors for the shared publication boundary."""

import argparse
import json
from pathlib import Path

FLOORS = {'transactions.py': 90, 'candidates.py': 90, 'destinations.py': 90,
          'validation.py': 85, 'reports.py': 85, 'verification.py': 70}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    files = json.loads(args.report.read_text())['files']
    failures = []
    for name, floor in FLOORS.items():
        rows = [value for path, value in files.items()
                if Path(path).name == name and 'filerepack' in Path(path).parts]
        if len(rows) != 1:
            failures.append(name + ': missing or ambiguous coverage')
            continue
        summary = rows[0]['summary']
        measured = 100 * summary['covered_lines'] / summary['num_statements']
        print(f'{name}: {measured:.2f}% (minimum {floor}%)')
        if measured < floor:
            failures.append(f'{name}: {measured:.2f}% < {floor}%')
    if failures:
        raise SystemExit('\n'.join(failures))


if __name__ == '__main__':
    main()
