"""ODF/EPUB wire-layout and control-file preservation regressions."""

import os
import struct
import zipfile

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.tools import resolve_szip
from test.package_fixtures import write_package


@pytest.mark.parametrize('kind', ['odt', 'epub'])
@pytest.mark.parametrize('deep', [False, True])
def test_mimetype_remains_stored_first_without_extra(tmp_path, kind, deep):
    if resolve_szip() is None:
        pytest.skip('7z extraction backend missing')
    path = tmp_path / ('book.' + kind)
    entries = write_package(path, kind)
    before = path.stat().st_size
    result = FileRepacker().repack(str(path), options=RepackOptions(deep_walking=deep))
    assert result.total_outsize < before
    with zipfile.ZipFile(path) as zf:
        first = zf.infolist()[0]
        assert first.filename == 'mimetype' and first.header_offset == 0
        assert first.compress_type == zipfile.ZIP_STORED
        assert first.extra == b''
        for name, data in entries.items():
            if name.startswith('META-INF/') or name.endswith('.opf') or name == 'mimetype':
                assert zf.read(name) == data
    raw = path.read_bytes()
    fields = struct.unpack('<4s5H3I2H', raw[:30])
    assert fields[0] == b'PK\x03\x04' and fields[3] == 0 and fields[-1] == 0
    assert raw[30:38] == b'mimetype'
    assert raw[38:38 + len(entries['mimetype'])] == entries['mimetype']


def repack_package(path, *, deep=True, dryrun=False, outfile=None):
    if resolve_szip() is None:
        pytest.skip('7z extraction backend missing')
    return FileRepacker().repack(str(path), outfile=str(outfile) if outfile else None,
                                options=RepackOptions(deep_walking=deep, dryrun=dryrun))


@pytest.mark.parametrize('kind', ['odt', 'epub'])
def test_backend_compressed_mimetype_is_corrected(tmp_path, monkeypatch, kind):
    path = tmp_path / ('book.' + kind)
    entries = write_package(path, kind)
    real_verify = FileRepacker._verify_archive_candidate
    observed = []

    def compressed_candidate(self, filename, family, options):
        with zipfile.ZipFile(filename) as source:
            data = [(entry, source.read(entry.filename)) for entry in source.infolist()]
        with zipfile.ZipFile(filename, 'w') as output:
            for info, payload in data:
                output.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(filename) as source:
            observed.append(source.getinfo('mimetype').compress_type)
        return real_verify(self, filename, family, options)

    monkeypatch.setattr(FileRepacker, '_verify_archive_candidate', compressed_candidate)
    result = repack_package(path)
    assert observed == [zipfile.ZIP_DEFLATED]
    assert result.total_outsize < result.total_insize
    with zipfile.ZipFile(path) as output:
        assert output.getinfo('mimetype').compress_type == zipfile.ZIP_STORED
        assert output.read('mimetype') == entries['mimetype']


@pytest.mark.parametrize('kind', ['odt', 'epub'])
@pytest.mark.parametrize('fault', ['missing_mimetype', 'mimetype_order', 'compressed_mimetype',
                                  'mimetype_extra', 'signature', 'encryption', 'rights',
                                  'missing_control', 'invalid_xml', 'doctype', 'wrong_mimetype'])
def test_unsupported_packages_skip_before_extraction(tmp_path, monkeypatch, kind, fault, caplog):
    from test.package_fixtures import package_entries
    entries = package_entries(kind)
    control = 'META-INF/container.xml' if kind == 'epub' else 'META-INF/manifest.xml'
    if fault == 'missing_mimetype':
        del entries['mimetype']
    elif fault == 'mimetype_order':
        mime = entries.pop('mimetype')
        entries['mimetype'] = mime
    elif fault in ('signature', 'encryption', 'rights'):
        name = {'signature': 'META-INF/documentsignatures.xml',
                'encryption': 'META-INF/encryption.xml', 'rights': 'META-INF/rights.xml'}[fault]
        entries[name] = b'<protected/>'
    elif fault == 'missing_control':
        del entries[control]
    elif fault == 'invalid_xml':
        entries[control] = b'<broken'
    elif fault == 'doctype':
        entries[control] = b'<!DOCTYPE malicious [<!ENTITY a "x">]>' + entries[control]
    elif fault == 'wrong_mimetype':
        entries['mimetype'] = b'application/not-the-package'
    path = tmp_path / ('protected.' + kind)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name)
            if fault == 'mimetype_extra' and name == 'mimetype':
                info.extra = b'\xfe\xca\x00\x00'
            compression = (zipfile.ZIP_DEFLATED if fault == 'compressed_mimetype'
                           and name == 'mimetype' else zipfile.ZIP_STORED)
            archive.writestr(info, payload, compress_type=compression)
    before = path.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *args: pytest.fail('unsupported package was extracted'))
    result = repack_package(path)
    assert result.total_outsize == result.total_insize
    assert path.read_bytes() == before
    assert 'package policy' in caplog.text


@pytest.mark.parametrize('fault', ['missing_rootfile', 'missing_resource', 'spine', 'remote',
                                  'escape', 'duplicate_id', 'no_manifest', 'no_spine'])
def test_epub_references_are_verified(tmp_path, monkeypatch, fault):
    from test.package_fixtures import package_entries
    entries = package_entries('epub')
    if fault == 'missing_rootfile':
        del entries['OEBPS/book.opf']
    elif fault == 'missing_resource':
        del entries['OEBPS/chapter.xhtml']
    else:
        text = entries['OEBPS/book.opf'].decode()
        if fault == 'spine':
            text = text.replace('idref="i2"', 'idref="absent"')
        elif fault == 'remote':
            text = text.replace('../OEBPS/chapter.xhtml', 'https://example.com/chapter.xhtml')
        elif fault == 'escape':
            text = text.replace('../OEBPS/chapter.xhtml', '../../outside.xhtml')
        elif fault == 'duplicate_id':
            text = text.replace('</manifest>', '<item id="i2" href="chapter.xhtml"/></manifest>')
        elif fault == 'no_manifest':
            text = text.replace('<manifest>', '<unused>').replace('</manifest>', '</unused>')
        elif fault == 'no_spine':
            text = text.replace('<spine>', '<unused>').replace('</spine>', '</unused>')
        entries['OEBPS/book.opf'] = text.encode()
    path = tmp_path / 'invalid.epub'
    write_package(path, 'epub', entries=entries)
    before = path.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *args: pytest.fail('invalid references were extracted'))
    assert repack_package(path).total_outsize == len(before)
    assert path.read_bytes() == before


@pytest.mark.parametrize('fault', ['missing_content', 'unlisted', 'missing_reference', 'root_mime',
                                  'duplicate_path', 'checksum', 'encryption_record', 'wrong_size'])
def test_odf_manifest_is_verified(tmp_path, monkeypatch, fault):
    from test.package_fixtures import package_entries
    entries = package_entries('odt')
    if fault == 'missing_content':
        del entries['content.xml']
    elif fault == 'unlisted':
        entries['unexpected.xml'] = b'<surprise/>'
    else:
        manifest = entries['META-INF/manifest.xml'].decode()
        if fault == 'missing_reference':
            manifest = manifest.replace('content.xml', 'missing.xml')
        elif fault == 'root_mime':
            manifest = manifest.replace('opendocument.text', 'opendocument.spreadsheet')
        elif fault == 'duplicate_path':
            manifest = manifest.replace('</manifest:manifest>',
                                        '<manifest:file-entry manifest:full-path="content.xml"/>'
                                        '</manifest:manifest>')
        elif fault in ('checksum', 'wrong_size'):
            attribute = 'checksum="unverified"' if fault == 'checksum' else 'size="1"'
            manifest = manifest.replace('manifest:full-path="content.xml"',
                                        'manifest:full-path="content.xml" manifest:' + attribute)
        elif fault == 'encryption_record':
            manifest = manifest.replace('manifest:media-type="text/xml"/>',
                                        'manifest:media-type="text/xml">'
                                        '<manifest:encryption-data/></manifest:file-entry>')
        entries['META-INF/manifest.xml'] = manifest.encode()
    path = tmp_path / 'invalid.odt'
    write_package(path, 'odt', entries=entries)
    before = path.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *args: pytest.fail('invalid manifest was extracted'))
    assert repack_package(path).total_outsize == len(before)
    assert path.read_bytes() == before


@pytest.mark.parametrize('kind', ['odt', 'epub'])
def test_control_files_bypass_nested_minification(tmp_path, kind):
    from test.package_fixtures import package_entries
    entries = package_entries(kind, {'metadata.json': b' { "x" : 1 } '})
    control = 'OEBPS/book.opf' if kind == 'epub' else 'META-INF/manifest.xml'
    entries[control] = entries[control].replace(b'><', b'>\n  <')
    path = tmp_path / ('deep.' + kind)
    write_package(path, kind, entries=entries)
    result = repack_package(path)
    assert result.total_outsize < result.total_insize
    with zipfile.ZipFile(path) as output:
        assert output.read(control) == entries[control]
        assert output.read('metadata.json') == b'{"x":1}'


@pytest.mark.parametrize('kind', ['odt', 'epub'])
@pytest.mark.parametrize('dryrun', [False, True])
def test_distinct_destination_and_dry_run(tmp_path, kind, dryrun):
    source = tmp_path / ('source.' + kind)
    output = tmp_path / ('output.' + kind)
    write_package(source, kind)
    before = source.read_bytes()
    result = repack_package(source, dryrun=dryrun, outfile=output)
    assert result.total_outsize < result.total_insize
    assert source.read_bytes() == before
    assert output.exists() is not dryrun


@pytest.mark.parametrize('kind', ['odt', 'epub'])
def test_package_mimetype_is_detected_inside_generic_zip(tmp_path, kind):
    path = tmp_path / 'generic.zip'
    write_package(path, kind)
    before = path.stat().st_size
    assert repack_package(path).total_outsize < before
    with zipfile.ZipFile(path) as output:
        assert output.getinfo('mimetype').compress_type == zipfile.ZIP_STORED


@pytest.mark.parametrize('kind', ['odt', 'epub'])
@pytest.mark.parametrize('fault', ['compression', 'order', 'extra', 'control'])
def test_candidate_policy_violation_never_publishes(tmp_path, monkeypatch, kind, fault, caplog):
    import filerepack.archives as archive_module
    source = tmp_path / ('source.' + kind)
    write_package(source, kind)
    before = source.read_bytes()
    real_restore = archive_module.restore_zip_metadata
    candidates = []

    def corrupt_after_restore(filename, *args, **kwargs):
        real_restore(filename, *args, **kwargs)
        candidates.append(filename)
        with zipfile.ZipFile(filename) as archive:
            data = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
        if fault == 'order':
            data.append(data.pop(0))
        with zipfile.ZipFile(filename, 'w') as archive:
            for info, payload in data:
                if info.filename == 'mimetype':
                    if fault == 'compression':
                        info.compress_type = zipfile.ZIP_DEFLATED
                    elif fault == 'extra':
                        info.extra = b'\xfe\xca\x00\x00'
                if fault == 'control' and (info.filename.endswith('.opf') or
                                          info.filename == 'META-INF/manifest.xml'):
                    payload = payload.replace(b'><', b'>\n<')
                archive.writestr(info, payload)

    monkeypatch.setattr(archive_module, 'restore_zip_metadata', corrupt_after_restore)
    result = repack_package(source)
    assert result.total_outsize == result.total_insize
    assert source.read_bytes() == before
    assert candidates and all(not os.path.exists(path) for path in candidates)
    assert 'archive candidate rejected' in caplog.text


@pytest.mark.parametrize('kind', ['odt', 'epub'])
def test_oversized_controls_skip_before_extraction(tmp_path, monkeypatch, kind):
    import filerepack.package_policy as policy
    path = tmp_path / ('large-control.' + kind)
    write_package(path, kind)
    before = path.read_bytes()
    monkeypatch.setattr(policy, '_MAX_CONTROL_BYTES', 64)
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *args: pytest.fail('oversized controls were extracted'))
    assert repack_package(path).total_outsize == len(before)
    assert path.read_bytes() == before
