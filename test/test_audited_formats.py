"""Audited formats retain decoded contents and refuse unsafe or unverifiable rewrites."""

import gzip
import builtins
import os
import struct
import zipfile
import zlib

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack import candidates as tx
from filerepack.data import pack_sqlite
from filerepack.duckdb import duckdb_fingerprint, pack_duckdb, verify_duckdb
from filerepack.formats import identify_filename, matches_ext_filter
from filerepack.package_policy import inspect_package, verify_package
from filerepack.qgis import sqlite_fingerprint
from filerepack.swf import decode_swf, pack_swf
from filerepack.tgs import decode_tgs, pack_tgs
from filerepack.tools import resolve_szip
from filerepack.verification import validate_output
from test.format_fixtures import qgd_database


def swf_bytes(signature=b'CWS', version=10):
    # RECT uses one bit per coordinate. Frame header, long metadata tag, End.
    rectangle = b'\x08\0'
    metadata = (b'<metadata>keep all movie bytes and scripts</metadata>' * 1000)
    body = (rectangle + b'\0\x18\x01\0' + struct.pack('<HI', (77 << 6) | 63, len(metadata))
            + metadata + b'\0\0')
    header = signature + bytes([version]) + struct.pack('<I', len(body) + 8)
    return header + (zlib.compress(body, 1) if signature == b'CWS' else body)


def tgs_bytes():
    raw = (b'{ "tgs": 1, "v": "5.5.2", "w": 512, "h": 512, "fr": 60, '
           b'"ip": 0, "op": 180, "layers": [], "assets": [], "extra": ['
           + b'1.2300e+9999, -0, "keep  \\u0061", ' * 500 + b'0] }')
    return gzip.compress(raw, compresslevel=1, mtime=1234)


def duckdb_database(path):
    duckdb = pytest.importorskip('duckdb', minversion='1.4.2')
    pytest.importorskip('pyarrow', minversion='19.0')
    connection = duckdb.connect(str(path))
    try:
        connection.execute('CREATE SCHEMA data')
        connection.execute('CREATE TABLE data.kept (i INTEGER PRIMARY KEY, text VARCHAR, '
                           'precise DECIMAL(38,8), stamp TIMESTAMP_NS, payload BLOB, f DOUBLE)')
        connection.execute("INSERT INTO data.kept VALUES "
                           "(1, 'keep  text', 123456789012345678901.12345678, "
                           "TIMESTAMP_NS '2020-01-01 00:00:00.123456789', '\\x00\\xFF', -0.0), "
                           "(2, NULL, NULL, NULL, NULL, 'NaN'::DOUBLE)")
        connection.execute('CREATE INDEX text_index ON data.kept(text)')
        connection.execute('CREATE TABLE junk AS SELECT range AS id, '
                           'repeat(md5(range::VARCHAR), 32) AS value FROM range(20000)')
        connection.execute('CHECKPOINT')
        connection.execute('DELETE FROM junk WHERE id > 0')
        connection.execute('CHECKPOINT')
    finally:
        connection.close()


def audited_fingerprint(path, extension):
    if extension == 'swf':
        return decode_swf(path.read_bytes())
    if extension == 'tgs':
        return decode_tgs(path.read_bytes())
    if extension == 'duckdb':
        return duckdb_fingerprint(str(path))
    return sqlite_fingerprint(str(path))


@pytest.mark.parametrize(('extension', 'packer'), [
    ('map', 'json'), ('har', 'json'), ('topojson', 'json'), ('gltf', 'json'), ('rels', 'xml'),
    ('vscdb', 'sqlite'), ('sqlitedb', 'sqlite'), ('duckdb', 'duckdb'),
    ('swf', 'swf'), ('tgs', 'tgs'),
])
def test_audited_routes_and_filters(extension, packer):
    kind = identify_filename('source.' + extension.upper())
    assert kind.packer == packer
    assert matches_ext_filter('source.' + extension, [packer])
    assert identify_filename('source.mellel').family == 'zip'


@pytest.mark.parametrize('extension', ['map', 'har', 'topojson', 'gltf'])
def test_json_alias_preserves_numbers_duplicate_keys_and_strings(tmp_path, extension):
    path = tmp_path / ('data.' + extension)
    path.write_bytes(b' { "n": 1.234E+99999, "n": -0, "s": "keep  \\u0061" } ')
    FileRepacker().repack(str(path))
    assert path.read_bytes() == b'{"n":1.234E+99999,"n":-0,"s":"keep  \\u0061"}'
    path.write_bytes(b'not JSON: linker map or binary data')
    FileRepacker().repack(str(path))
    assert path.read_bytes() == b'not JSON: linker map or binary data'


def test_json_alias_input_bound_precedes_parsing(tmp_path, monkeypatch):
    path = tmp_path / 'large.har'
    original = b' { "payload": "' + b'keep' * 1000 + b'" } '
    path.write_bytes(original)
    monkeypatch.setattr('filerepack.markup.MAX_NATIVE_BYTES', 32)
    monkeypatch.setattr('filerepack.markup.minify_json_bytes',
                        lambda *a: pytest.fail('Oversized JSON was parsed'))
    FileRepacker().repack(str(path))
    assert path.read_bytes() == original


@pytest.mark.parametrize('extension', ['swf', 'tgs', 'vscdb', 'sqlitedb', 'duckdb'])
@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'min_savings', 'outfile'])
def test_audited_handlers_preserve_contents_metadata_and_lifecycle(tmp_path, extension, mode):
    path = tmp_path / ('source.' + extension)
    if extension == 'swf':
        path.write_bytes(swf_bytes())
    elif extension == 'tgs':
        path.write_bytes(tgs_bytes())
    elif extension == 'duckdb':
        duckdb_database(path)
    else:
        qgd_database(path)
    original, expected = path.read_bytes(), audited_fingerprint(path, extension)
    os.chmod(path, 0o640)
    os.utime(path, ns=(1600000000000000000, 1600000000123456789))
    before = path.stat()
    output = tmp_path / ('output.' + extension)
    result = FileRepacker().repack(str(path), outfile=str(output) if mode == 'outfile' else None,
                                  options=RepackOptions(dryrun=mode == 'dryrun',
                                                        sqlite_offline=True,
                                                        min_savings=100 if mode == 'min_savings'
                                                        else None))
    target = output if mode == 'outfile' else path
    assert audited_fingerprint(target, extension) == expected
    assert target.stat().st_mode == before.st_mode
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    assert result.filepath.endswith('.' + extension)
    if mode in ('inplace', 'outfile'):
        assert target.stat().st_size < len(original)
    if mode != 'inplace':
        assert path.read_bytes() == original


@pytest.mark.parametrize('signature', [b'FWS', b'CWS'])
def test_swf_preserves_movie_version_and_all_tags(tmp_path, signature):
    path = tmp_path / 'movie.swf'
    path.write_bytes(swf_bytes(signature))
    expected = decode_swf(path.read_bytes())
    assert pack_swf(str(path)).replaced
    assert path.read_bytes()[:4] == b'CWS\x0a'
    assert decode_swf(path.read_bytes()) == expected


@pytest.mark.parametrize('extension', ['swf', 'tgs'])
@pytest.mark.parametrize('fault', ['truncated', 'trailing', 'signature', 'size', 'content'])
def test_malformed_animation_unchanged(tmp_path, extension, fault):
    payload = swf_bytes() if extension == 'swf' else tgs_bytes()
    if fault == 'truncated':
        payload = payload[:-5]
    elif fault == 'trailing':
        payload += b'junk'
    elif fault == 'signature':
        payload = b'ZWS' + payload[3:] if extension == 'swf' else b'BAD' + payload[3:]
    elif extension == 'swf':
        if fault == 'size':
            payload = payload[:4] + struct.pack('<I', 0xffffffff) + payload[8:]
        else:
            payload = payload[:8] + zlib.compress(decode_swf(payload)[1][:-2])
    else:
        payload = gzip.compress(b'{"tgs":1}' if fault == 'content' else b'not JSON')
    path = tmp_path / ('invalid.' + extension)
    path.write_bytes(payload)
    FileRepacker().repack(str(path))
    assert path.read_bytes() == payload
    assert not validate_output(str(path), extension).ok


def test_tgs_rejects_concatenation_and_bounds(tmp_path, monkeypatch):
    path = tmp_path / 'sticker.tgs'
    payload = tgs_bytes() + gzip.compress(b'{}')
    path.write_bytes(payload)
    assert pack_tgs(str(path)) is None
    assert path.read_bytes() == payload
    path.write_bytes(tgs_bytes())
    monkeypatch.setattr('filerepack.tgs.MAX_TGS_BYTES', 128)
    assert pack_tgs(str(path)) is None


def test_tgs_optional_zopfli_and_fallback_preserve_exact_json(tmp_path, monkeypatch):
    from filerepack.tgs import compress_tgs
    raw = decode_tgs(tgs_bytes())
    optimized = compress_tgs(raw)
    monkeypatch.setattr('filerepack.tgs.MAX_ZOPFLI_BYTES', 0)
    fallback = compress_tgs(raw)
    assert decode_tgs(optimized) == decode_tgs(fallback) == raw
    assert len(optimized) <= len(fallback)


def test_missing_zopfli_uses_gzip_fallback(monkeypatch):
    from filerepack.tgs import compress_tgs
    real_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name.startswith('zopfli'):
            raise ImportError('optional dependency unavailable')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', missing)
    raw = decode_tgs(tgs_bytes())
    assert decode_tgs(compress_tgs(raw)) == raw


@pytest.mark.parametrize('module', ['duckdb', 'pyarrow'])
def test_missing_duckdb_backend_skips_source(tmp_path, monkeypatch, module):
    path = tmp_path / 'source.duckdb'
    duckdb_database(path)
    original = path.read_bytes()
    real_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == module:
            raise ImportError('optional dependency unavailable')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', missing)
    assert pack_duckdb(str(path)) is None
    assert path.read_bytes() == original


def test_duckdb_nested_values_and_float_bits(tmp_path):
    duckdb = pytest.importorskip('duckdb', minversion='1.4.2')
    path = tmp_path / 'source.duckdb'
    duckdb_database(path)
    connection = duckdb.connect(str(path))
    connection.execute('CREATE TABLE nested (i INTEGER, labels VARCHAR[], '
                       'item STRUCT(lang VARCHAR, stamp TIMESTAMP_NS, f DOUBLE), '
                       'mapping MAP(VARCHAR, DOUBLE))')
    connection.execute("INSERT INTO nested VALUES (1, ['keep', NULL, 'a,''b'], "
                       "{'lang':'en', 'stamp':TIMESTAMP_NS '2020-01-01 00:00:00.123456789', "
                       "'f':'-0.0'::DOUBLE}, map(['nan'], ['NaN'::DOUBLE])), "
                       "(2, NULL, NULL, NULL)")
    connection.close()
    original = tmp_path / 'reference.duckdb'
    original.write_bytes(path.read_bytes())
    assert pack_duckdb(str(path)).replaced
    assert verify_duckdb(str(original), str(path))
    connection = duckdb.connect(str(path))
    connection.execute("UPDATE nested SET item={'lang':item.lang, 'stamp':item.stamp, 'f':1.0} "
                       "WHERE i=1")
    connection.close()
    assert not verify_duckdb(str(original), str(path))


def test_duckdb_arrow_comparison_retains_nested_float_bits_and_batch_boundaries():
    from filerepack.duckdb import _compare_batches
    pa = pytest.importorskip('pyarrow', minversion='19.0')
    dtype = pa.struct([('values', pa.list_(pa.float64()))])
    original = pa.record_batch([pa.array([{'values': [-0.0, float('nan')]}, None],
                                         type=dtype)], names=['nested'])
    changed = pa.record_batch([pa.array([{'values': [0.0, float('nan')]}, None],
                                        type=dtype)], names=['nested'])
    assert not _compare_batches(iter([original]), iter([changed]), [0, 0])
    assert _compare_batches(iter([original.slice(0, 1), original.slice(1)]),
                            iter([original]), [0, 0])


@pytest.mark.parametrize('limit', ['MAX_ROWS', 'MAX_VALUE_BYTES'])
def test_duckdb_verification_bounds_skip_source(tmp_path, monkeypatch, limit):
    path = tmp_path / 'source.duckdb'
    duckdb_database(path)
    original = path.read_bytes()
    monkeypatch.setattr('filerepack.duckdb.' + limit, 1)
    assert pack_duckdb(str(path)) is None
    assert path.read_bytes() == original


def test_mellel_missing_image_reference_skips(tmp_path, monkeypatch):
    path = tmp_path / 'source.mellel'
    write_mellel(path)
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('unreferenced.txt', b'retained')
    reference = tmp_path / 'invalid.mellel'
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(reference, 'w') as target:
        target.writestr('main.xml', source.read('main.xml'))
    original = reference.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *a: pytest.fail('Bad package extracted'))
    FileRepacker().repack(str(reference))
    assert reference.read_bytes() == original


@pytest.mark.parametrize('extension', ['vscdb', 'sqlitedb'])
@pytest.mark.parametrize('sidecar', ['-wal', '-shm', '-journal'])
def test_sqlite_alias_refuses_sidecars_before_open(tmp_path, monkeypatch, extension, sidecar):
    path = tmp_path / ('source.' + extension)
    qgd_database(path)
    original = path.read_bytes()
    marker = tmp_path / (path.name + sidecar)
    marker.write_bytes(b'pending transaction')
    monkeypatch.setattr('sqlite3.connect', lambda *a, **kw: pytest.fail('Active DB opened'))
    assert pack_sqlite(str(path)) is None
    assert path.read_bytes() == original and marker.read_bytes() == b'pending transaction'


@pytest.mark.parametrize('extension', ['vscdb', 'sqlitedb'])
def test_sqlite_alias_refuses_vacuum_that_changes_rowids(tmp_path, extension):
    path = tmp_path / ('source.' + extension)
    qgd_database(path, implicit_rowids=True)
    original = path.read_bytes()
    result = pack_sqlite(str(path))
    assert result is None or not result.replaced
    assert path.read_bytes() == original


@pytest.mark.parametrize('deep', [True, False])
def test_nested_sqlite_and_duckdb_preserve_logical_contents(tmp_path, deep):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    sqlite_path = tmp_path / 'state.vscdb'
    duckdb_path = tmp_path / 'rows.duckdb'
    qgd_database(sqlite_path)
    duckdb_database(duckdb_path)
    expected = sqlite_fingerprint(str(sqlite_path)), duckdb_fingerprint(str(duckdb_path))
    original = sqlite_path.read_bytes(), duckdb_path.read_bytes()
    path = tmp_path / 'databases.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(sqlite_path.name, original[0])
        archive.writestr(duckdb_path.name, original[1])
        archive.writestr('unknown.sqlitedb', b'not a database')
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=deep))
    with zipfile.ZipFile(path) as archive:
        if not deep:
            assert archive.read(sqlite_path.name) == original[0]
            assert archive.read(duckdb_path.name) == original[1]
        assert archive.read('unknown.sqlitedb') == b'not a database'
        sqlite_path.write_bytes(archive.read(sqlite_path.name))
        duckdb_path.write_bytes(archive.read(duckdb_path.name))
    assert (sqlite_fingerprint(str(sqlite_path)), duckdb_fingerprint(str(duckdb_path))) == expected


@pytest.mark.parametrize('fault', ['view', 'sequence', 'macro', 'enum', 'interval', 'wal'])
def test_unsupported_duckdb_refuses_copy(tmp_path, monkeypatch, fault):
    duckdb = pytest.importorskip('duckdb', minversion='1.4.2')
    path = tmp_path / 'source.duckdb'
    connection = duckdb.connect(str(path))
    commands = {'view': 'CREATE VIEW v AS SELECT 1 AS n', 'sequence': 'CREATE SEQUENCE s',
                'macro': 'CREATE MACRO m(x) AS x+1', 'enum': "CREATE TYPE e AS ENUM ('a','b')",
                'interval': 'CREATE TABLE t(a INTERVAL)', 'wal': 'CREATE TABLE t(a INTEGER)'}
    connection.execute(commands[fault])
    connection.close()
    if fault == 'wal':
        (tmp_path / 'source.duckdb.wal').write_bytes(b'pending transaction')
    original = path.read_bytes()
    monkeypatch.setattr('filerepack.duckdb._rewrite',
                        lambda *a: pytest.fail('Unsupported DB copied'))
    assert pack_duckdb(str(path)) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize('extension', ['swf', 'tgs', 'duckdb'])
def test_changed_candidate_is_refused_and_temporaries_cleaned(tmp_path, monkeypatch, extension):
    source = tmp_path / ('source.' + extension)
    if extension == 'duckdb':
        duckdb_database(source)
    else:
        source.write_bytes(swf_bytes() if extension == 'swf' else tgs_bytes())
    original = source.read_bytes()
    real_commit = tx.commit_output
    candidates = []

    def corrupt(candidate, *args, **kwargs):
        candidates.append(candidate)
        if extension == 'swf':
            header, raw = decode_swf(open(candidate, 'rb').read())
            with open(candidate, 'wb') as target:
                target.write(b'CWS' + header + zlib.compress(raw.replace(b'movie', b'WRONG')))
        elif extension == 'tgs':
            raw = decode_tgs(open(candidate, 'rb').read()).replace(b'keep', b'WRONG')
            with open(candidate, 'wb') as target:
                target.write(gzip.compress(raw))
        else:
            import duckdb
            connection = duckdb.connect(candidate)
            connection.execute('DELETE FROM data.kept WHERE i=1')
            connection.close()
        return real_commit(candidate, *args, **kwargs)

    monkeypatch.setattr(tx, 'commit_output', corrupt)
    {'swf': pack_swf, 'tgs': pack_tgs, 'duckdb': pack_duckdb}[extension](str(source))
    assert candidates and not any(os.path.exists(path) for path in candidates)
    assert source.read_bytes() == original


def write_mellel(path, control=None):
    if control is None:
        control = (b'<archive creator="com.redlex.mellel" writer-version="19" '
                   b'compatibility-version="10"><image-data><image-ref>IMG-0</image-ref>'
                   b'<extension-hint>png</extension-hint></image-data></archive>')
    entries = {'Images/': b'', 'main.xml': control,
               'Images/IMG-0.png': b'untouched opaque image' * 1000,
               'extra.map': b' { "all": "unchanged" } '}
    with zipfile.ZipFile(path, 'w') as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 0
            archive.writestr(info, payload)
            info.external_attr = 0  # Mellel writes zero-valued ZIP attributes.
    return entries


@pytest.mark.parametrize('mode', ['inplace', 'dryrun', 'outfile', 'no_archives'])
def test_mellel_preserves_every_member(tmp_path, mode):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    path = tmp_path / 'document.mellel'
    entries = write_mellel(path)
    original = path.read_bytes()
    policy = inspect_package(str(path), 'mellel')
    output = tmp_path / 'output.mellel'
    FileRepacker().repack(str(path), outfile=str(output) if mode == 'outfile' else None,
                          options=RepackOptions(dryrun=mode == 'dryrun',
                                                pack_archives=mode != 'no_archives'))
    target = output if mode == 'outfile' else path
    verify_package(str(target), policy)
    with zipfile.ZipFile(target) as archive:
        assert {name: archive.read(name) for name in archive.namelist()} == entries
        assert all(info.external_attr == 0 for info in archive.infolist())
    if mode in ('inplace', 'outfile'):
        assert target.stat().st_size < len(original)
    if mode in ('dryrun', 'outfile'):
        assert path.read_bytes() == original


@pytest.mark.parametrize('control', [b'<broken', b'<archive/>', b'<wrong/>',
                                   b'<!DOCTYPE archive SYSTEM "file:///bad"><archive/>'])
def test_bad_mellel_control_refuses_extraction(tmp_path, monkeypatch, control):
    path = tmp_path / 'document.mellel'
    write_mellel(path, control)
    original = path.read_bytes()
    monkeypatch.setattr(FileRepacker, '_extract_7z',
                        lambda *a: pytest.fail('Bad package extracted'))
    FileRepacker().repack(str(path))
    assert path.read_bytes() == original


@pytest.mark.parametrize('images', [True, False])
def test_nested_audited_formats_and_no_images(tmp_path, images):
    if resolve_szip() is None:
        pytest.skip('7z backend missing')
    path = tmp_path / 'nested.zip'
    swf, tgs = swf_bytes(), tgs_bytes()
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('movie.swf', swf)
        archive.writestr('sticker.tgs', tgs)
        archive.writestr('linker.map', b'linker map, not JSON')
        archive.writestr('source.map', b' { "version": 3 } ')
        archive.writestr('part.rels', b'<Relationships  xmlns = '
                          b'"http://schemas.openxmlformats.org/package/2006/relationships"/>')
    FileRepacker().repack(str(path), options=RepackOptions(pack_images=images))
    with zipfile.ZipFile(path) as archive:
        assert decode_swf(archive.read('movie.swf')) == decode_swf(swf)
        assert decode_tgs(archive.read('sticker.tgs')) == decode_tgs(tgs)
        assert archive.read('linker.map') == b'linker map, not JSON'
        assert archive.read('source.map') == b'{"version":3}'
        assert b'<Relationships xmlns=' in archive.read('part.rels')
        if not images:
            assert archive.read('movie.swf') == swf and archive.read('sticker.tgs') == tgs
