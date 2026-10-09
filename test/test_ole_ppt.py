"""Real PPT VBA wrappers, graph ambiguity, bounded decoding and byte preservation."""

import io
import shutil
import struct
import zipfile
import zlib

import pytest

from filerepack import FileRepacker, ole, ole_ppt
from filerepack.ole_verify import CompoundFile, ole_fingerprint, read_compound
from test.ole_fixtures import CORPUS, compound_bytes, ppt_project_streams
from test.test_ole import native_writer as _native_writer

from test.test_ole_protection import summary_properties, write_source

native_writer = _native_writer


@pytest.fixture
def macro_ppt():
    return read_compound(str(CORPUS / "SimpleMacro.ppt"))


def project_storage(compound):
    data = compound.streams[("PowerPoint Document",)]
    # Pinned real fixture: one edit, four persist objects and VBAInfo at offset 911.
    assert struct.unpack_from("<HHI", data, 911) == (2, 1024, 12)
    assert struct.unpack_from("<III", data, 919) == (3, 1, 2)
    assert struct.unpack_from("<HHI", data, 38386) == (0x10, 4113, 3844)
    payload = data[38394:42238]
    raw = zlib.decompress(payload[4:])
    assert len(raw) == struct.unpack_from("<I", payload)[0] == 12288
    return payload, raw


def empty_vba_info(identifier=0, has_macros=0, version=2, *, persist=None, storage=False):
    data = bytearray(44)
    struct.pack_into("<III", data, 32, identifier, has_macros, version)
    records = {
        0: ole_ppt.PptRecord(1000, 36, 0xF, None),
        8: ole_ppt.PptRecord(2000, 28, 0xF, 0),
        16: ole_ppt.PptRecord(1023, 20, 0x1F, 8),
        24: ole_ppt.PptRecord(1024, 12, 2, 16),
    }
    if storage:
        records[40] = ole_ppt.PptRecord(4113, 4, 0, None)
    return bytes(data), records, persist or {}


def test_empty_vba_info_atom_is_macro_free_only_without_project_storage():
    data, records, persist = empty_vba_info()
    assert ole_ppt._check_vba(data, records, persist, 0, 1) is False

    for fields in (
        {"identifier": 3},
        {"has_macros": 1},
        {"version": 3},
        {"storage": True},
        {"persist": {0: 40}},
    ):
        data, records, persist = empty_vba_info(**fields)
        with pytest.raises(ValueError):
            ole_ppt._check_vba(data, records, persist, 0, 1)


@pytest.mark.parametrize("extension", ["ppt", "pot", "pps"])
def test_unsigned_ppt_aliases_preserve_encoded_project(
    tmp_path, native_writer, macro_ppt, extension
):
    source = tmp_path / ("macro." + extension)
    write_source(source, macro_ppt.streams, macro_ppt)
    before = ole_fingerprint(str(source))
    inspection = ole.inspect_ole(str(source))
    assert inspection.eligible and inspection.unsigned_vba
    assert ole.pack_ole(str(source)).replaced
    assert ole_fingerprint(str(source)) == before
    assert read_compound(str(source)).streams == macro_ppt.streams


def test_uncompressed_project_is_preserved_without_reserialization(
    tmp_path, native_writer, macro_ppt
):
    _, raw = project_storage(macro_ppt)
    streams = ppt_project_streams(macro_ppt.streams, raw, flags=0)
    source = tmp_path / "uncompressed.ppt"
    write_source(source, streams, macro_ppt)
    before = ole_fingerprint(str(source))
    assert ole.inspect_ole(str(source)).unsigned_vba
    assert ole.pack_ole(str(source)).replaced
    assert ole_fingerprint(str(source)) == before
    assert read_compound(str(source)).streams == streams


@pytest.mark.parametrize(
    "fault",
    [
        "missing-reference",
        "zero-reference",
        "duplicate-target",
        "child-target",
        "info-parent",
        "info-header",
        "atom-header",
        "has-macros",
        "version",
        "duplicate-id",
        "history",
        "duplicate-list",
    ],
)
def test_ambiguous_ppt_project_graph_skips_before_writer(tmp_path, monkeypatch, macro_ppt, fault):
    streams = dict(macro_ppt.streams)
    data = bytearray(streams[("PowerPoint Document",)])
    if fault == "missing-reference":
        struct.pack_into("<I", data, 919, 100)
    elif fault == "zero-reference":
        struct.pack_into("<I", data, 919, 0)
    elif fault == "duplicate-target":
        struct.pack_into("<I", data, 42238 + 24, 38386)
    elif fault == "child-target":
        struct.pack_into("<I", data, 42238 + 20, 911)
    elif fault == "info-parent":
        struct.pack_into("<H", data, 682, 2001)
    elif fault == "info-header":
        struct.pack_into("<H", data, 903, 0xF)
    elif fault == "atom-header":
        struct.pack_into("<H", data, 911, 3)
    elif fault == "duplicate-list":
        # The Environment container is a second direct DocInfoList after this mutation.
        struct.pack_into("<H", data, 58, 2000)
    elif fault == "has-macros":
        struct.pack_into("<I", data, 923, 0)
    elif fault == "version":
        struct.pack_into("<I", data, 927, 3)
    elif fault == "duplicate-id":
        # Two complete ranges overlap at ID 3; all offsets still point to real records.
        body = struct.pack("<7I", (3 << 20) | 1, 0, 3122, 38386, (2 << 20) | 3, 38386, 35641)
        directory = struct.pack("<HHI", 0, 6002, len(body)) + body
        old_edit = data[42266:]
        data = data[:42238] + directory + old_edit
        current = bytearray(streams[("Current User",)])
        struct.pack_into("<I", current, 16, 42238 + len(directory))
        streams[("Current User",)] = bytes(current)
    else:
        directory = len(data)
        data.extend(data[42238:42266])
        edit = len(data)
        data.extend(data[42266:42302])
        struct.pack_into("<II", data, edit + 16, 42266, directory)
        current = bytearray(streams[("Current User",)])
        struct.pack_into("<I", current, 16, edit)
        streams[("Current User",)] = bytes(current)
    streams[("PowerPoint Document",)] = bytes(data)
    assert_skip(tmp_path, monkeypatch, macro_ppt, streams)


def assert_skip(tmp_path, monkeypatch, original, streams):
    source = tmp_path / "source.ppt"
    write_source(source, streams, original)
    before = source.read_bytes()
    monkeypatch.setattr(ole, "resolve_tool", lambda key: pytest.fail("Writer reached"))
    assert not ole.inspect_ole(str(source)).eligible
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "fault",
    [
        "bad-zlib",
        "checksum",
        "truncated",
        "trailing",
        "concatenated",
        "raw-deflate",
        "gzip",
        "zero-size",
        "large-size",
        "short-size",
        "long-size",
        "unknown-instance",
    ],
)
def test_invalid_project_wrapper_skips(tmp_path, monkeypatch, macro_ppt, fault):
    payload, raw = project_storage(macro_ppt)
    payload = bytearray(payload)
    flags = 0x10
    if fault == "bad-zlib":
        payload[4:6] = b"xx"
    elif fault == "checksum":
        payload[-1] ^= 1
    elif fault == "truncated":
        payload = payload[:-1]
    elif fault == "trailing":
        payload.extend(b"padding")
    elif fault == "concatenated":
        payload.extend(zlib.compress(b"another stream"))
    elif fault in ("raw-deflate", "gzip"):
        compressor = zlib.compressobj(wbits=-15 if fault == "raw-deflate" else 31)
        payload = payload[:4] + compressor.compress(raw) + compressor.flush()
    elif fault == "zero-size":
        struct.pack_into("<I", payload, 0, 0)
    elif fault == "large-size":
        struct.pack_into("<I", payload, 0, ole_ppt.MAX_VBA_BYTES + 1)
    elif fault == "short-size":
        struct.pack_into("<I", payload, 0, len(raw) - 512)
    elif fault == "long-size":
        struct.pack_into("<I", payload, 0, len(raw) + 512)
    else:
        flags = 0x20
    assert_skip(
        tmp_path,
        monkeypatch,
        macro_ppt,
        ppt_project_streams(macro_ppt.streams, bytes(payload), flags),
    )


def test_decompression_cannot_exceed_declared_output_budget(tmp_path, monkeypatch, macro_ppt):
    payload = struct.pack("<I", 512) + zlib.compress(b"\0" * (4 * 1024 * 1024))
    monkeypatch.setattr(
        ole_ppt, "CompoundFile", lambda raw: pytest.fail("Unbounded decode reached CFB")
    )
    assert_skip(tmp_path, monkeypatch, macro_ppt, ppt_project_streams(macro_ppt.streams, payload))


def test_encoded_project_budget_is_checked_before_decode(tmp_path, monkeypatch, macro_ppt):
    monkeypatch.setattr(ole_ppt, "MAX_VBA_BYTES", 1000)
    monkeypatch.setattr(ole_ppt.zlib, "decompressobj", lambda: pytest.fail("Decoder reached"))
    assert_skip(tmp_path, monkeypatch, macro_ppt, macro_ppt.streams)


@pytest.mark.parametrize(
    "fault",
    [
        "signature",
        "encrypted",
        "rights-managed",
        "signature-property",
        "missing-project",
        "missing-cache",
        "embedded",
        "invalid-cfb",
    ],
)
def test_nested_project_protection_and_unknown_layouts_skip(
    tmp_path, monkeypatch, macro_ppt, fault
):
    _, raw = project_storage(macro_ppt)
    nested = CompoundFile(raw)
    streams = dict(nested.streams)
    if fault == "signature":
        streams[("_signatures",)] = b"signature"
    elif fault == "encrypted":
        streams[("EncryptedPackage",)] = b"opaque"
    elif fault == "rights-managed":
        streams[("\x06DataSpaces", "Info")] = b"opaque"
    elif fault == "signature-property":
        streams[("\x05DocumentSummaryInformation",)] = summary_properties((1, 0x18))
    elif fault == "missing-project":
        del streams[("PROJECT",)]
    elif fault == "missing-cache":
        del streams[("VBA", "_VBA_PROJECT")]
    elif fault == "embedded":
        streams = {("embedded",) + path: payload for path, payload in streams.items()}
    if fault == "invalid-cfb":
        raw = b"not CFB" + raw[7:]
    else:
        metadata = (
            {
                e.path: (e.clsid, e.state, e.created, e.modified)
                for e in nested.entries
                if e.kind == 1
            }
            if fault != "embedded"
            else {}
        )
        raw = compound_bytes(streams, storages=metadata)
    payload = struct.pack("<I", len(raw)) + zlib.compress(raw)
    assert_skip(tmp_path, monkeypatch, macro_ppt, ppt_project_streams(macro_ppt.streams, payload))


def test_nested_independent_reader_disagreement_blocks_writer(tmp_path, monkeypatch, macro_ppt):
    def disagree(source, compound):
        assert source.read(8) == bytes.fromhex("d0cf11e0a1b11ae1")
        assert ("VBA", "Module1") in compound.streams
        raise ValueError("Independent nested reader disagreement")

    monkeypatch.setattr(ole_ppt, "independent_manifest", disagree)
    assert_skip(tmp_path, monkeypatch, macro_ppt, macro_ppt.streams)


def test_unsigned_ppt_inside_nested_archive_preserves_macro_payload(
    tmp_path, native_writer, macro_ppt
):
    if not (shutil.which("7zz") or shutil.which("7z")):
        pytest.skip("Archive writer unavailable")
    member = tmp_path / "macro.ppt"
    write_source(member, macro_ppt.streams, macro_ppt)
    before = ole_fingerprint(str(member))
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("macro.ppt", member.read_bytes())
        archive.writestr("opaque.dat", b"opaque application bytes")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("inner.zip", inner.getvalue())
    result = FileRepacker().repack(str(outer))
    assert result.total_outsize < result.total_insize
    with zipfile.ZipFile(outer) as archive:
        with zipfile.ZipFile(io.BytesIO(archive.read("inner.zip"))) as nested:
            assert nested.read("opaque.dat") == b"opaque application bytes"
            output = nested.read("macro.ppt")
    assert len(output) < member.stat().st_size
    member.write_bytes(output)
    assert ole_fingerprint(str(member)) == before
    assert read_compound(str(member)).streams == macro_ppt.streams
