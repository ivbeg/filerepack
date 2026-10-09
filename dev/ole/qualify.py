"""Reproduce the pinned OLE writer pilot without modifying corpus files."""

import argparse
import hashlib
import json
import platform
import os
import shutil
import subprocess
import tempfile
import time
import zlib
from pathlib import Path

from PIL import Image

from filerepack.ole import inspect_ole
from filerepack import FileRepacker, RepackOptions
from filerepack.ole_verify import ole_fingerprint, read_compound
from filerepack.verification import preservation_equal
from test.ole_fixtures import CORPUS, compound_bytes, ppt_project_streams, ppt_embedded_streams


def render(source, directory, soffice, pdftoppm):
    profile = directory / 'profile'
    (profile / 'user').mkdir(parents=True)
    (profile / 'user' / 'registrymodifications.xcu').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
        '</item></oor:items>')
    result = subprocess.run([soffice, '-env:UserInstallation=' + profile.as_uri(),
                             '--headless', '--convert-to', 'pdf', '--outdir', str(directory),
                             str(source)], capture_output=True, text=True, timeout=120)
    pdf = directory / (source.stem + '.pdf')
    if result.returncode or not pdf.is_file():
        raise RuntimeError('LibreOffice export failed: ' + result.stdout + result.stderr)
    subprocess.run([pdftoppm, '-r', '96', '-png', str(pdf), str(directory / 'page')],
                   check=True, capture_output=True, timeout=120)
    pages = []
    for path in sorted(directory.glob('page-*.png')):
        with Image.open(path) as image:
            rgb = image.convert('RGB')
            pages.append({'size': list(rgb.size),
                          'sha256': hashlib.sha256(rgb.tobytes()).hexdigest()})
    if not pages:
        raise RuntimeError('Renderer produced no pages')
    return pages


def measure(command, source, destination, empty):
    if empty:
        destination.touch()
    started = time.perf_counter()
    result = subprocess.run(command + [str(source), str(destination)],
                            capture_output=True, text=True, timeout=120)
    data = {'seconds': round(time.perf_counter() - started, 6), 'exit_code': result.returncode}
    if result.returncode:
        data['error'] = (result.stderr or result.stdout)[-2000:]
        return data
    data['bytes'] = destination.stat().st_size
    data['savings_bytes'] = source.stat().st_size - destination.stat().st_size
    try:
        original = ole_fingerprint(str(source))
        candidate = ole_fingerprint(str(destination))
        data['manifest_equal'] = original == candidate
        if original != candidate:
            data['differences'] = manifest_diff(original, candidate)
    except (OSError, ValueError) as exc:
        data['manifest_equal'] = False
        data['error'] = str(exc)
    return data


def manifest_diff(original, candidate):
    before = {e.path: e for e in original.entries}
    after = {e.path: e for e in candidate.entries}
    return [{'path': list(path),
             'fields': ['presence'] if path not in before or path not in after else
             [field for field in before[path].__dataclass_fields__
              if getattr(before[path], field) != getattr(after[path], field)]}
            for path in sorted(set(before) | set(after))
            if before.get(path) != after.get(path)][:10]


def runtime_records(source, destination):
    started = time.perf_counter()
    summary = FileRepacker().repack(str(source), outfile=str(destination),
                                    options=RepackOptions(ole_recompress=True))
    result = summary.results[0] if summary.results else None
    details = result.details if result else {}
    kind = 'ppt-ole' if details.get('strategy') == 'ppt-ole-recompression' else 'ole'
    equal = preservation_equal(str(source), str(destination), kind)
    if not equal:
        raise ValueError('Runtime PPT candidate did not preserve content')
    return {'seconds': round(time.perf_counter() - started, 6),
            'bytes': destination.stat().st_size,
            'savings_bytes': source.stat().st_size - destination.stat().st_size,
            'intent_equal': equal, 'verification_kind': kind, 'details': details,
            'strict_manifest_equal': ole_fingerprint(str(source)) ==
            ole_fingerprint(str(destination))}



def prepare_source(fixture, source, compound, variant):
    if variant == 'original':
        shutil.copyfile(fixture, source)
        return
    metadata = {e.path: (e.clsid, e.state, e.created, e.modified)
                for e in compound.entries if e.kind != 5}
    metadata[('opaque metadata',)] = (
        bytes(range(16)), 0xD1003456, 132999999999999999, 133000000000000001)
    root = next(e for e in compound.entries if e.kind == 5)
    streams = compound.streams
    if variant == 'uncompressed':
        # The fixture helper asserts the pinned sample's exact final-object layout.
        raw = zlib.decompress(streams[('PowerPoint Document',)][38398:42238])
        streams = ppt_project_streams(streams, raw, flags=0)
    elif variant.startswith('embedded-zlib'):
        data = streams[('PowerPoint Document',)]
        objects = [zlib.decompress(data[4580:7195]), zlib.decompress(data[7207:9797])]
        level = int(variant[-1])
        streams = ppt_embedded_streams([zlib.compress(raw, level) for raw in objects])
    holes = variant == 'holes'
    source.write_bytes(compound_bytes(
        streams, storages=metadata, root=(root.clsid, root.state, root.created, root.modified),
        free_sectors=80 if holes else 0, mini_gaps=5 if holes else 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--dotnet')
    parser.add_argument('--openmcdf-dll')
    parser.add_argument('--soffice')
    parser.add_argument('--pdftoppm')
    parser.add_argument('--ppt-uncompressed', action='store_true',
                        help='also qualify a controlled uncompressed SimpleMacro.ppt wrapper')
    parser.add_argument('--ppt-recompress', action='store_true',
                        help='also qualify the public opt-in PPT path and controlled OLE encodings')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.ppt_recompress:
        os.environ['FILEREPACK_OLE_COMPACTOR'] = str(Path(args.writer).resolve())
    report = {'platform': platform.platform(), 'python': platform.python_version(),
              'writer': subprocess.check_output([args.writer, '--version'], text=True).strip(),
              'olefile': '0.47', 'openmcdf': '3.3.0',
              'corpus_commit': json.loads((CORPUS / 'provenance.json').read_text())['commit'],
              'peak_memory': 'Not measured; fixed file/entry/depth bounds are enforced separately',
              'cases': [], 'skips': []}
    if args.soffice:
        report['renderer'] = subprocess.check_output([args.soffice, '--version'], text=True).strip()
        report['rasterizer'] = subprocess.run([args.pdftoppm, '-v'], text=True,
                                              capture_output=True).stderr.strip().splitlines()[0]
    report['ppt_record_runtime'] = args.ppt_recompress
    with tempfile.TemporaryDirectory(prefix='filerepack-ole-qualification-') as scratch:
        base = Path(scratch)
        for fixture in sorted(CORPUS.iterdir()):
            if fixture.suffix not in ('.doc', '.xls', '.ppt'):
                continue
            eligibility = inspect_ole(str(fixture))
            if not eligibility.eligible:
                report['skips'].append({'name': fixture.name, 'reason': eligibility.reason})
                continue
            compound = read_compound(str(fixture))
            unsigned_vba = eligibility.unsigned_vba
            fixture_sha256 = hashlib.sha256(fixture.read_bytes()).hexdigest()
            variants = ['original', 'holes']
            if args.ppt_uncompressed and fixture.name == 'SimpleMacro.ppt':
                variants.append('uncompressed')
            if args.ppt_recompress and fixture.name == 'ole2-embedding-2003.ppt':
                variants.extend(['embedded-zlib1', 'embedded-zlib0'])
            for variant in variants:
                holes = variant == 'holes'
                case_name = fixture.name + ('' if variant == 'original' else '-' + variant)
                directory = base / case_name
                directory.mkdir()
                source = directory / fixture.name
                prepare_source(fixture, source, compound, variant)
                candidate = directory / ('rust' + fixture.suffix)
                record = {'name': case_name, 'source_bytes': source.stat().st_size,
                          'fixture_name': fixture.name, 'variant': variant,
                          'fixture_sha256': fixture_sha256, 'unsigned_vba': unsigned_vba,
                          'free_regular_bytes_estimate': inspect_ole(str(source)).free_sector_bytes,
                          'controlled_holes': holes,
                          'rust': measure([args.writer], source, candidate, True)}
                if args.dotnet and args.openmcdf_dll:
                    record['openmcdf'] = measure([args.dotnet, args.openmcdf_dll], source,
                                                directory / ('openmcdf' + fixture.suffix), False)
                if args.ppt_recompress and fixture.suffix == '.ppt':
                    candidate = directory / 'runtime.ppt'
                    record['record_recompression'] = runtime_records(source, candidate)
                if args.soffice and not holes:
                    before = directory / 'before'
                    after = directory / 'after'
                    before.mkdir()
                    after.mkdir()
                    # Same basename and renderer/font environment for both versions.
                    shutil.copyfile(source, before / fixture.name)
                    shutil.copyfile(candidate, after / fixture.name)
                    try:
                        pages = render(before / fixture.name, before, args.soffice, args.pdftoppm)
                        output_pages = render(after / fixture.name, after,
                                              args.soffice, args.pdftoppm)
                        record['render'] = {'pages': pages, 'equal': pages == output_pages,
                                            'macros_security_level': 3, 'dpi': 96}
                    except (RuntimeError, subprocess.SubprocessError) as exc:
                        record['render'] = {'equal': False, 'error': str(exc)}
                report['cases'].append(record)
                print(case_name, record['rust'], flush=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
