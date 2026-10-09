"""Additional textual aliases and QGIS preserve exact application contents."""

import os
import sqlite3
import zipfile

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.formats import identify_filename, matches_ext_filter
from filerepack.markup import pack_jsonl
from filerepack.package_policy import inspect_package, verify_package
from filerepack.qgis import minify_qgis_bytes, pack_qgd, pack_qgs, sqlite_fingerprint
from filerepack.tools import resolve_szip
from filerepack.utils import verify_output
from test.format_fixtures import QGIS_XML, qgd_database


ROUTES = [('psb', 'psb'), ('geojson', 'json'), ('ipynb', 'json'), ('jsonl', 'jsonl'),
          ('ndjson', 'jsonl'), ('qgs', 'qgs'), ('qgd', 'qgd'), ('ui', 'xml'),
          ('blend', 'blend'), ('fits', 'fits'), ('fit', 'fits'), ('fts', 'fits'),
          ('nrrd', 'nrrd'), ('ase', 'aseprite'), ('aseprite', 'aseprite')]


@pytest.mark.parametrize(('extension', 'packer'), ROUTES)
def test_added_routes_and_filters(extension, packer):
    kind = identify_filename('example.' + extension.upper())
    assert kind.family == 'standalone' and kind.packer == packer
    assert matches_ext_filter('example.' + extension, [packer])


def test_qgz_route_and_excluded_lidar():
    assert identify_filename('project.QGZ').family == 'zip'
    for extension in ('las', 'laz'):
        assert identify_filename('data.' + extension) is None


@pytest.mark.parametrize('extension', ['geojson', 'ipynb'])
@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'outfile', 'min_savings'])
def test_json_alias_keeps_all_exact_tokens(tmp_path, extension, mode):
    path = tmp_path / ('document.' + extension)
    original = b' { "n": 1.2300E+9999, "n": -0, "cells": [ "keep  \\u0061" ] } \n'
    expected = b'{"n":1.2300E+9999,"n":-0,"cells":["keep  \\u0061"]}'
    path.write_bytes(original)
    output = tmp_path / ('output.' + extension)
    FileRepacker().repack(str(path), outfile=str(output) if mode == 'outfile' else None,
                          options=RepackOptions(dryrun=mode == 'dryrun',
                                                min_savings=100 if mode == 'min_savings' else None))
    assert path.read_bytes() == (expected if mode == 'inplace' else original)
    if mode == 'outfile':
        assert output.read_bytes() == expected and output.suffix == path.suffix


@pytest.mark.parametrize('extension', ['jsonl', 'ndjson'])
@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'min_savings'])
def test_json_lines_preserves_records_tokens_and_line_endings(tmp_path, extension, mode):
    path = tmp_path / ('records.' + extension)
    original = b' { "n": -0, "n": 1E+99999 } \r\n [ "a  b", true ] \n 12345678901234567890 '
    expected = b'{"n":-0,"n":1E+99999}\r\n["a  b",true]\n12345678901234567890'
    path.write_bytes(original)
    FileRepacker().repack(str(path), options=RepackOptions(
        dryrun=mode == 'dryrun', min_savings=100 if mode == 'min_savings' else None,
    ))
    assert path.read_bytes() == (expected if mode == 'inplace' else original)


@pytest.mark.parametrize('invalid', [b'\n', b' {"a":1}\n\n', b'1\n{broken}\n2\n',
                                   b'\xef\xbb\xbf1\n', b'NaN\n', b'{"a": "\xff"}\n',
                                   b'1 2\n', b'"raw\nnewline"\n'])
def test_invalid_json_lines_never_partially_replaces_source(tmp_path, invalid):
    path = tmp_path / 'records.jsonl'
    path.write_bytes(invalid)
    assert pack_jsonl(str(path)) is None
    assert path.read_bytes() == invalid


def test_json_line_bound_and_failed_verification(tmp_path, monkeypatch):
    path = tmp_path / 'records.jsonl'
    source = b' { "keep": 1 } \n'
    path.write_bytes(source)
    monkeypatch.setattr('filerepack.markup._MAX_JSON_LINE', 5)
    assert pack_jsonl(str(path)) is None
    monkeypatch.setattr('filerepack.markup._MAX_JSON_LINE', 1000)
    monkeypatch.setattr('filerepack.markup.verify_jsonl', lambda *args: False)
    assert pack_jsonl(str(path)) is None
    assert path.read_bytes() == source


def test_json_lines_candidate_validation_stays_streaming(tmp_path, monkeypatch):
    path = tmp_path / 'records.ndjson'
    path.write_bytes(b' { "n": 1 } \n' * 2000)
    monkeypatch.setattr('filerepack.verification.read_bounded',
                        lambda *args: pytest.fail('JSON Lines was read as a whole file'))
    assert pack_jsonl(str(path)).replaced
    assert verify_output(str(path), 'ndjson')
    path.write_bytes(b'1\n\n2\n')
    assert not verify_output(str(path), 'jsonl')


def test_qgis_and_ui_keep_text_and_doctype(tmp_path):
    path = tmp_path / 'project.qgs'
    path.write_bytes(QGIS_XML)
    expected = minify_qgis_bytes(QGIS_XML)
    assert pack_qgs(str(path)).replaced
    assert path.read_bytes() == expected
    assert expected.splitlines()[0] == QGIS_XML.splitlines()[0]
    ui = tmp_path / 'form.ui'
    ui.write_bytes(b'<ui  version = "4.0"><string>  keep text  </string></ui>')
    FileRepacker().repack(str(ui))
    assert ui.read_bytes() == b'<ui version="4.0"><string>  keep text  </string></ui>'


@pytest.mark.parametrize('source', [b'<wrong version="1"/>', b'<qgis/>',
                                  b'<!DOCTYPE qgis SYSTEM "file:///untrusted"><qgis version="3"/>',
                                  b'<!DOCTYPE qgis [<!ENTITY x "y">]><qgis version="3">&x;</qgis>'])
def test_unsupported_qgis_xml_is_unchanged(tmp_path, source):
    path = tmp_path / 'bad.qgs'
    path.write_bytes(source)
    assert pack_qgs(str(path)) is None
    assert path.read_bytes() == source


@pytest.mark.parametrize('declaration', [b'<?xml version="1.1"?>',
                                      b'<?xml version="1.0" encoding="ISO-8859-1"?>'])
def test_qgis_doctype_never_bypasses_xml_encoding_or_version_policy(declaration):
    assert minify_qgis_bytes(declaration + QGIS_XML) is None


@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'outfile'])
def test_qgd_preserves_schema_rowids_values_and_application_metadata(tmp_path, mode):
    path = tmp_path / 'project.qgd'
    qgd_database(path)
    expected = sqlite_fingerprint(str(path))
    original = path.read_bytes()
    output = tmp_path / 'output.qgd'
    FileRepacker().repack(str(path), outfile=str(output) if mode == 'outfile' else None,
                          options=RepackOptions(dryrun=mode == 'dryrun'))
    target = output if mode == 'outfile' else path
    assert sqlite_fingerprint(str(target)) == expected
    if mode == 'inplace':
        assert len(target.read_bytes()) < len(original)
    else:
        assert path.read_bytes() == original


def test_qgd_implicit_rowids_must_survive_vacuum(tmp_path):
    path = tmp_path / 'implicit.qgd'
    qgd_database(path, implicit_rowids=True)
    original = path.read_bytes()
    result = pack_qgd(str(path))
    assert result is None or not result.replaced
    assert path.read_bytes() == original
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT rowid FROM auxiliary ORDER BY rowid').fetchall()
        assert rows == [(10,), (1000,)]


@pytest.mark.parametrize('sidecar', ['-wal', '-journal'])
def test_qgd_sidecars_are_never_ignored(tmp_path, sidecar):
    path = tmp_path / 'active.qgd'
    qgd_database(path)
    original = path.read_bytes()
    (tmp_path / ('active.qgd' + sidecar)).write_bytes(b'pending transaction')
    assert pack_qgd(str(path)) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize('deep', [True, False])
def test_qgz_policy_and_nested_optimization(tmp_path, deep):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    database = tmp_path / 'project.qgd'
    qgd_database(database)
    path = tmp_path / 'project.qgz'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('project.qgs', QGIS_XML)
        archive.writestr('project.qgd', database.read_bytes())
        archive.writestr('extra.json', b' { "this stays": "exact" } ')
        archive.writestr('video.wmv', b'untouched application asset')
        archive.writestr('mimetype', b'application/x-qgis-unrelated-asset' * 1000)
    policy = inspect_package(str(path), 'qgz')
    before = path.stat().st_size
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=deep))
    assert path.stat().st_size < before
    verify_package(str(path), policy)
    with zipfile.ZipFile(path) as archive:
        assert archive.read('extra.json') == b' { "this stays": "exact" } '
        assert archive.read('video.wmv') == b'untouched application asset'
        assert archive.read('mimetype') == b'application/x-qgis-unrelated-asset' * 1000
        assert archive.getinfo('mimetype').compress_type == zipfile.ZIP_DEFLATED
        assert archive.read('project.qgs') == (minify_qgis_bytes(QGIS_XML) if deep else QGIS_XML)


@pytest.mark.parametrize('fault', ['missing', 'duplicate_project', 'xml', 'qgd',
                                 'mismatched_qgd', 'wal'])
def test_invalid_qgz_skips_before_extraction(tmp_path, monkeypatch, fault):
    path = tmp_path / 'project.qgz'
    with zipfile.ZipFile(path, 'w') as archive:
        if fault != 'missing':
            archive.writestr('project.qgs', b'<bad/>' if fault == 'xml' else QGIS_XML)
        if fault == 'duplicate_project':
            archive.writestr('other.qgs', QGIS_XML)
        if fault in ('qgd', 'mismatched_qgd'):
            archive.writestr('other.qgd' if fault == 'mismatched_qgd' else 'project.qgd', b'bad')
        if fault == 'wal':
            archive.writestr('project.qgd', b'')
            archive.writestr('project.qgd-wal', b'pending transaction')
    before = path.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *args: pytest.fail('Unsupported QGZ was extracted'))
    FileRepacker().repack(str(path))
    assert path.read_bytes() == before


def test_added_formats_work_in_archive_and_keep_metadata(tmp_path):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    path = tmp_path / 'nested.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('map.geojson', b' { "coordinate": 1.2300E+20 } ')
        archive.writestr('form.ui', b'<ui  version = "4.0"><string> text </string></ui>')
        archive.writestr('records.ndjson', b' { "n": 1 } \n { "n": 2 } \r\n')
    os.chmod(path, 0o640)
    os.utime(path, ns=(1600000000000000000, 1600000000000000001))
    before = path.stat()
    FileRepacker().repack(str(path))
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert path.stat().st_mode == before.st_mode
    with zipfile.ZipFile(path) as archive:
        assert archive.read('map.geojson') == b'{"coordinate":1.2300E+20}'
        assert archive.read('records.ndjson') == b'{"n":1}\n{"n":2}\r\n'
        assert b'<string> text </string>' in archive.read('form.ui')
