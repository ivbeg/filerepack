"""Compare v1 profiles on the same frozen, independently checked public corpus."""

import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'dev' / 'format_survey'))
from run import environment, execute_sample  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path,
                        default=ROOT / 'dev/format_survey/runs/pilot-2026-10-04')
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    samples = json.loads((args.corpus / 'samples.json').read_text())
    grouped = collections.defaultdict(list)
    for sample in samples:
        if sample.get('download_status') == 'downloaded':
            grouped[sample['format']].append(sample)
    selected = []
    for kind in sorted(grouped):
        ordered = sorted(grouped[kind], key=lambda sample: (sample['size'], sample['blob_sha']))
        smallest = ordered[0]
        different = [sample for sample in ordered if sample['repository'] != smallest['repository']]
        largest = (different or ordered)[-1]
        selected.extend([smallest, largest] if smallest != largest else [smallest])
    args.run.mkdir(parents=True, exist_ok=False)
    for sample in selected:
        target = args.run / sample['local_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.corpus / sample['local_path'], target)
    (args.run / 'results').mkdir()
    config = {'decoded_byte_limit': 64 * 1024 * 1024, 'timeout_seconds': 90, 'profile_version': 1}
    env = environment(args.run)
    env['options'] = {'profile_version': 1, 'convert_container': False, 'quiet': True,
                      'max_extract_bytes': config['decoded_byte_limit'], 'max_extract_ratio': 100}
    (args.run / 'environment.json').write_text(json.dumps(env, indent=2) + '\n')
    (args.run / 'samples.json').write_text(json.dumps(selected, indent=2) + '\n')
    results = []
    for profile in ('fast', 'balanced', 'maximum', 'preserve'):
        for sample in selected:
            result = execute_sample(sample, profile, config, args.run)
            results.append(result)
            print(profile, sample['format'], sample['path'], result['status'], flush=True)
    summaries = []
    for profile in ('fast', 'balanced', 'maximum', 'preserve'):
        rows = [row for row in results if row['profile'] == profile]
        summaries.append({
            'profile': profile, 'samples': len(rows),
            'input_bytes': sum(row['size'] for row in rows),
            'verified_saved_bytes': sum(row['verified_saved_bytes'] for row in rows),
            'elapsed_seconds': sum(row['elapsed_seconds'] for row in rows),
            'peak_sampled_rss_bytes': max(row['sampled_peak_rss_bytes'] or 0 for row in rows),
            'peak_sampled_work_directory_bytes': max(row['sampled_peak_scratch_bytes']
                                                    for row in rows),
            'accepted': sum(row.get('library_summary', {}).get('outcome', {}).get('status') ==
                            'replaced' for row in rows),
            'inner_candidate_saved_bytes': sum(
                row.get('library_summary', {}).get('inner_insize', 0) -
                row.get('library_summary', {}).get('inner_outsize', 0) for row in rows),
            'statuses': dict(collections.Counter(row['status'] for row in rows)),
        })
    report = {'schema_version': 1, 'environment': env, 'selection':
              'Smallest file and largest file from a different origin for each available format',
              'corpus_sha256': hashlib.sha256(
                  json.dumps(selected, sort_keys=True).encode()).hexdigest(),
              'sampling': '100 ms; worker plus descendants RSS; work directory '
                          'includes final output',
              'limits': config, 'summaries': summaries, 'cases': []}
    for row in results:
        report['cases'].append({key: value for key, value in row.items() if key not in
                                ('library_summary', 'log_path', 'output_path', 'local_path')})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
