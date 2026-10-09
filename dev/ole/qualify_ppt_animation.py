"""Compare supplied PPT source/candidate and reject unsafe storage-sharing controls.

Use only private intermediates. Java reader control requires pinned POI 5.4.1
jars; neither this writer experiment nor those dependencies ship at runtime.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from dev.ole.qualify_ppt_notes import render
from filerepack.format_support import format_scope
from filerepack.ole_art_layout import equal_art, inspect_art
from filerepack.ole_ppt import read_records
from filerepack.ole_ppt_host import inspect_host
from filerepack.ole_ppt_storage import storage_diagnostics
from filerepack.ole_verify import read_compound

DOCUMENT, CURRENT = ('PowerPoint Document',), ('Current User',)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sharing_control(source, compound, writer, root, budget):
    """Deliberately unsupported candidate; caller must prove reader rejection."""
    host = inspect_host(compound, budget, pictures=True)
    wrappers = [host.data[p:p + 8 + host.records[p].size] for p in host.storages]
    assert len(wrappers) == 7 and len(set(wrappers)) == 1
    first = host.storages[0]
    document = bytearray(host.data[:first] + wrappers[0])
    directory = len(document)
    tail = bytearray(host.data[host.directory:])
    for identifier, field in host.fields.items():
        target = host.persist[identifier]
        struct.pack_into('<I', tail, field - host.directory,
                         first if target in host.storages else target)
    struct.pack_into('<I', tail, host.edit - host.directory + 20, directory)
    current = bytearray(host.current)
    struct.pack_into('<I', current, 16, host.edit + directory - host.directory)
    document.extend(tail)
    docpath, curpath = root / 'control-document', root / 'control-current'
    docpath.write_bytes(document)
    curpath.write_bytes(current)
    output = root / 'unsupported-sharing-control.ppt'
    output.touch()
    subprocess.run([writer, '--replace-ppt-streams', str(docpath), str(curpath),
                    str(source), str(output)], check=True, capture_output=True, timeout=120)
    return output


def reader(path, root, prefix, classpath, *, edit):
    args = ['java', '-cp', classpath, 'PptStorageCompatibility', str(path),
            str(root / (prefix + '-saved.ppt'))]
    if edit:
        args.append(str(root / (prefix + '-edited.ppt')))
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=60)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--writer', required=True)
    parser.add_argument('--poi-classpath', required=True)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args()
    source, candidate = args.source.resolve(), args.candidate.resolve()
    assert source != candidate and args.report.resolve() not in (source, candidate)
    initial = source.read_bytes()
    before, after = read_compound(str(source)), read_compound(str(candidate))
    with format_scope({'ole_writer': args.writer}) as budget:
        assert equal_art(inspect_art(before, budget), inspect_art(after, budget))
        diagnostics = storage_diagnostics(before.streams[DOCUMENT], budget)
    old, new = before.streams[DOCUMENT], after.streams[DOCUMENT]
    assert len(old) == len(new)
    records = read_records(old)
    spans = [(p, r) for p, r in records.items() if r.kind in (1008, 4113, 4116, 5000)]
    assert all(old[p:p + 8 + r.size] == new[p:p + 8 + r.size] for p, r in spans)
    assert all(before.streams[p] == after.streams[p] for p in before.streams
               if p not in (DOCUMENT, ('Pictures',)))
    result = {
        'date': '2026-10-09', 'source_sha256': digest(initial),
        'candidate_sha256': digest(candidate.read_bytes()), 'source_bytes': len(initial),
        'candidate_bytes': candidate.stat().st_size, 'complete_officeart_contract_equal': True,
        'unaffected_streams_exact': True, 'immutable_notes_storage_animation_tag_spans': len(spans),
        'source_mode': oct(source.stat().st_mode & 0o777),
        'candidate_mode': oct(candidate.stat().st_mode & 0o777),
        'mtime_preserved': source.stat().st_mtime_ns == candidate.stat().st_mtime_ns,
        'renderer': subprocess.check_output(['soffice', '--version'], text=True).strip(),
        'native_sha256': digest(Path(args.writer).read_bytes()), 'diagnostics': diagnostics,
        'poi_version': '5.4.1',
    }
    with tempfile.TemporaryDirectory(prefix='filerepack-ppt-animation-qa-') as scratch:
        root = Path(scratch)
        with format_scope({'ole_writer': args.writer}) as budget:
            control = sharing_control(source, before, args.writer, root, budget)
        inputs = (('source', source), ('candidate', candidate), ('sharing_control', control))
        for name, path in inputs:
            output = reader(path, root, name, args.poi_classpath, edit=name != 'sharing_control')
            expected = ('storages=1 resolved=1' if name == 'sharing_control'
                        else 'storages=7 resolved=7')
            assert all(expected in line for line in output.splitlines() if line.startswith('file='))
            if name != 'sharing_control':
                marker = 'independent_edit=true changed_persist=3 unchanged_other_payloads=6'
                assert marker in output
            result[name + '_reader'] = output.splitlines()
        result['storage_sharing_qualified'] = False
        result['sharing_control_bytes'] = control.stat().st_size
        result['sharing_control_sha256'] = digest(control.read_bytes())
        if not args.no_render:
            for mode in ('slides', 'notes'):
                print('Comparing', mode, flush=True)
                a = render(source, root / ('source-' + mode), notes=mode == 'notes')
                b = render(candidate, root / ('candidate-' + mode), notes=mode == 'notes')
                assert a == b
                result[mode + '_render'] = {
                    'equal_page_rgb': True, 'page_count': len(a), 'pages': a,
                }
    assert source.read_bytes() == initial
    result['source_unchanged'] = True
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print('Complete preservation, reader/edit and render controls passed', flush=True)


if __name__ == '__main__':
    main()
