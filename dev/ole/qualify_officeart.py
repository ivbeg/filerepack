"""Qualify public OfficeArt runtime against real originals and encoding controls."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from filerepack import FileRepacker, RepackOptions
from filerepack.format_support import Budget, FormatLimits
from filerepack.ole_art_layout import inspect_art
from filerepack.ole_verify import ole_fingerprint, read_compound
from filerepack.verification import preservation_equal
from test.ole_art_fixtures import NAMES, control
from test.ole_fixtures import CORPUS
from dev.ole.qualify import render


def digest(data):
    return hashlib.sha256(data).hexdigest()


def metafiles(path):
    layout = inspect_art(read_compound(str(path)), Budget(FormatLimits()))
    return [record.metafile.fingerprint() for record in layout.metafiles]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writer', required=True, type=Path)
    parser.add_argument('--soffice', default='soffice')
    parser.add_argument('--pdftoppm', default='pdftoppm')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    writer = str(args.writer.resolve())
    os.environ['FILEREPACK_OLE_COMPACTOR'] = writer
    checksums = {name: digest((CORPUS / name).read_bytes()) for name in NAMES}
    report = {'platform': platform.platform(), 'python': platform.python_version(),
              'writer': subprocess.check_output([writer, '--version'], text=True).strip(),
              'renderer': subprocess.check_output([args.soffice, '--version'], text=True).strip(),
              'rasterizer': subprocess.run([args.pdftoppm, '-v'], text=True,
                                          capture_output=True).stderr.strip().splitlines()[0],
              'fixture_sha256': checksums, 'cases': [],
              'scope': 'Public API with native writer; controls change only zlib encodings. '
                       'macOS qualification; Microsoft Office repair behavior unmeasured.'}
    with tempfile.TemporaryDirectory(prefix='filerepack-officeart-runtime-') as scratch:
        base = Path(scratch)
        for name in NAMES:
            for variant in ('original', 'zlib0', 'zlib1'):
                directory = base / (name + '-' + variant)
                directory.mkdir()
                before, after = directory / 'before', directory / 'after'
                before.mkdir()
                after.mkdir()
                source, candidate = before / name, after / name
                if variant == 'original':
                    shutil.copyfile(CORPUS / name, source)
                else:
                    source.write_bytes(control(name, int(variant[-1])).data)
                source_bytes = source.read_bytes()
                baseline = directory / ('baseline' + source.suffix)
                baseline.touch()
                subprocess.run([writer, str(source), str(baseline)], check=True,
                               capture_output=True, timeout=120)
                assert ole_fingerprint(str(source)) == ole_fingerprint(str(baseline))
                summary = FileRepacker().repack(
                    str(source), outfile=str(candidate), options=RepackOptions(ole_recompress=True))
                result = summary.results[0]
                strategy = result.details['strategy']
                kind = {'ole-compaction': 'ole', 'ppt-ole-recompression': 'ppt-ole',
                        'ole-officeart-recompression': 'officeart'}[strategy]
                assert preservation_equal(str(source), str(candidate), kind)
                assert metafiles(source) == metafiles(candidate)
                assert candidate.stat().st_size <= baseline.stat().st_size
                assert source.read_bytes() == source_bytes
                pages = render(source, before, args.soffice, args.pdftoppm)
                candidate_pages = render(candidate, after, args.soffice, args.pdftoppm)
                assert pages == candidate_pages, (name, variant, 'rendered pages differ')
                case = {'fixture': name, 'variant': variant,
                        'source_bytes': len(source_bytes),
                        'compaction_bytes': baseline.stat().st_size,
                        'candidate_bytes': candidate.stat().st_size, 'verifier': kind,
                        'intent_equal': True, 'decoded_metafiles_equal': True,
                        'strict_manifest_equal': ole_fingerprint(str(source)) ==
                        ole_fingerprint(str(candidate)),
                        'render': {'equal': True, 'pages': pages, 'dpi': 96,
                                   'macro_security_level': 3},
                        'details': result.details}
                report['cases'].append(case)
                print(name, variant, len(source_bytes), '->', candidate.stat().st_size,
                      strategy, 'render equal', flush=True)
    assert checksums == {name: digest((CORPUS / name).read_bytes()) for name in NAMES}
    report['source_checksums_unchanged'] = True
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
