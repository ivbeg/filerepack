"""Unsigned VBA qualification and hidden host-signature rejection regressions."""

import struct

import pytest

from filerepack import ole
from filerepack.ole_protection import (
    DOCSUMMARY,
    USERDEFINED,
    check_document_summary,
    check_macro_projects,
)
from filerepack.ole_verify import CompoundFile, ole_fingerprint, read_compound
from test.ole_fixtures import CORPUS, compound_bytes
from test.test_ole import native_writer as _native_writer

native_writer = _native_writer  # Shared native integration requirement.


def property_section(identifiers):
    count = len(identifiers)
    body = b"".join(
        struct.pack("<II", 2, 1252) if identifier == 1 else struct.pack("<II", 3, 0)
        for identifier in identifiers
    )
    index = b"".join(
        struct.pack("<II", identifier, 8 + 8 * count + 8 * n)
        for n, identifier in enumerate(identifiers)
    )
    return struct.pack("<II", 8 + len(index) + len(body), count) + index + body


def summary_properties(ids=(1, 15), user_ids=None):
    sections = [property_section(ids)]
    guids = [DOCSUMMARY]
    if user_ids is not None:
        sections.append(property_section(user_ids))
        guids.append(USERDEFINED)
    header = bytearray(28)
    struct.pack_into("<HH", header, 0, 0xFFFE, 0)
    struct.pack_into("<I", header, 24, len(sections))
    offset = 28 + 20 * len(sections)
    for guid, section in zip(guids, sections):
        header.extend(guid + struct.pack("<I", offset))
        offset += len(section)
    return bytes(header) + b"".join(sections)


def word_variables(names):
    data = bytearray(struct.pack("<HHH", 0xFFFF, len(names), 4))
    for name in names:
        encoded = name.encode("utf-16le")
        data.extend(struct.pack("<H", len(encoded) // 2) + encoded + b"\0" * 4)
    for name in names:
        data.extend(struct.pack("<H", 3) + "abc".encode("utf-16le"))
    return bytes(data)


def insert_variables(streams, variables):
    fib = bytearray(streams[("WordDocument",)])
    offset = 32
    for unit in (2, 4):
        count = struct.unpack_from("<H", fib, offset)[0]
        offset += 2 + unit * count
    fields = offset + 2
    table_name = "1Table" if struct.unpack_from("<H", fib, 10)[0] & 0x200 else "0Table"
    table = streams[(table_name,)]
    struct.pack_into("<II", fib, fields + 60 * 8, len(table), len(variables))
    streams[("WordDocument",)] = bytes(fib)
    streams[(table_name,)] = table + variables


def write_source(path, streams, original=None):
    metadata = (
        {e.path: (e.clsid, e.state, e.created, e.modified) for e in original.entries if e.kind == 1}
        if original
        else {}
    )
    root = next(e for e in original.entries if e.kind == 5) if original else None
    path.write_bytes(
        compound_bytes(
            streams,
            storages=metadata,
            free_sectors=100,
            mini_gaps=3,
            root=(root.clsid, root.state, root.created, root.modified)
            if root
            else (b"\0" * 16, 0, 0, 0),
        )
    )


@pytest.mark.parametrize(
    "filename,extension",
    [
        ("SimpleMacro.doc", "doc"),
        ("SimpleMacro.doc", "dot"),
        ("SimpleMacro.xls", "xls"),
        ("SimpleMacro.xls", "xlt"),
        ("SimpleMacro.xls", "xla"),
        ("external_name.xls", "xls"),
    ],
)
def test_unsigned_projects_keep_all_macro_bytes(tmp_path, native_writer, filename, extension):
    original = read_compound(str(CORPUS / filename))
    source = tmp_path / ("project." + extension)
    write_source(source, original.streams, original)
    before = ole_fingerprint(str(source))
    assert ole.inspect_ole(str(source)).eligible
    assert check_macro_projects(original, ole.OLE_EXTENSIONS[extension])
    result = ole.pack_ole(str(source))
    assert result is not None and result.replaced
    assert ole_fingerprint(str(source)) == before
    assert read_compound(str(source)).streams == original.streams


@pytest.mark.parametrize("name", ["Sign", "SigAgile", "SigV3", "SIGN"])
@pytest.mark.parametrize("macro", [True, False])
def test_word_host_signature_is_rejected_before_writer(tmp_path, monkeypatch, name, macro):
    original = read_compound(str(CORPUS / ("SimpleMacro.doc" if macro else "simple.doc")))
    streams = dict(original.streams)
    insert_variables(streams, word_variables(["Customer", name]))
    source = tmp_path / "signed.doc"
    write_source(source, streams, original)
    before = source.read_bytes()
    monkeypatch.setattr(ole, "resolve_tool", lambda key: pytest.fail("Writer reached"))
    assert "Signed Word VBA" in ole.inspect_ole(str(source)).reason
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "filename",
    ["SimpleMacro.xls", "external_name.xls", "Simple.xls", "SampleShow.ppt", "SimpleMacro.ppt"],
)
def test_signature_property_rejected_even_without_signature_named_stream(
    tmp_path, monkeypatch, filename
):
    original = read_compound(str(CORPUS / filename))
    streams = dict(original.streams)
    streams[("\x05DocumentSummaryInformation",)] = summary_properties((1, 15, 0x18))
    source = tmp_path / filename
    write_source(source, streams, original)
    before = source.read_bytes()
    monkeypatch.setattr(ole, "resolve_tool", lambda key: pytest.fail("Writer reached"))
    assert "GKPIDDSI_DIGSIG" in ole.inspect_ole(str(source)).reason
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == before


def test_parallel_word_variables_and_user_properties_are_retained(tmp_path, native_writer):
    original = read_compound(str(CORPUS / "SimpleMacro.doc"))
    streams = dict(original.streams)
    insert_variables(streams, word_variables(["Customer", "Примечание"]))
    # 0x18 in the UserDefined set is an ordinary custom property, not GKPIDDSI_DIGSIG.
    streams[("\x05DocumentSummaryInformation",)] = summary_properties(user_ids=(1, 0x18))
    source = tmp_path / "variables.doc"
    write_source(source, streams, original)
    before = ole_fingerprint(str(source))
    assert ole.pack_ole(str(source)).replaced
    assert ole_fingerprint(str(source)) == before


@pytest.mark.parametrize(
    "fault",
    [
        "section-count",
        "section-guid",
        "section-overlap",
        "section-length",
        "count",
        "duplicate-id",
        "offset",
        "overlap",
        "padding",
        "truncated",
        "oversized",
    ],
)
def test_ambiguous_property_layout_skips_unsigned_macro(tmp_path, monkeypatch, fault):
    import filerepack.ole_protection as protection

    original = read_compound(str(CORPUS / "SimpleMacro.xls"))
    streams = dict(original.streams)
    props = bytearray(summary_properties(user_ids=(1, 3)))
    start = 68
    if fault == "section-count":
        struct.pack_into("<I", props, 24, 3)
    elif fault == "section-guid":
        props[28:44] = b"\0" * 16
    elif fault == "section-overlap":
        struct.pack_into("<I", props, 64, start)
    elif fault == "section-length":
        struct.pack_into("<I", props, start, len(props) + 100)
    elif fault == "count":
        struct.pack_into("<I", props, start + 4, 0xFFFFFFFF)
    elif fault == "duplicate-id":
        struct.pack_into("<I", props, start + 16, 1)
    elif fault == "offset":
        struct.pack_into("<I", props, start + 12, 0)
    elif fault == "overlap":
        struct.pack_into("<I", props, start + 20, 25)
    elif fault == "padding":
        props.extend(b"private tail")
    elif fault == "truncated":
        props = props[: start + 3]
    else:
        monkeypatch.setattr(protection, "MAX_PROTECTION_BYTES", 64)
    streams[("\x05DocumentSummaryInformation",)] = bytes(props)
    source = tmp_path / "source.xls"
    write_source(source, streams, original)
    before = source.read_bytes()
    monkeypatch.setattr(ole, "resolve_tool", lambda key: pytest.fail("Writer reached"))
    assert not ole.inspect_ole(str(source)).eligible
    result = ole.pack_ole(str(source))
    assert result is not None and not result.replaced and result.reason
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "variables",
    [
        b"\xff\xff",
        word_variables(["a"])[:-1],
        word_variables(["a", "A"]),
        word_variables(["a"]) + b"x",
        word_variables(["Sign\0hidden"]),
    ],
)
def test_ambiguous_word_variables_skip(tmp_path, variables):
    original = read_compound(str(CORPUS / "SimpleMacro.doc"))
    streams = dict(original.streams)
    insert_variables(streams, variables)
    source = tmp_path / "source.doc"
    write_source(source, streams, original)
    assert not ole.inspect_ole(str(source)).eligible


@pytest.mark.parametrize(
    "fault", ["missing-project", "missing-cache", "bad-cache", "bad-dir", "embedded", "other-host"]
)
def test_unknown_vba_layouts_skip(tmp_path, fault):
    original = read_compound(str(CORPUS / "SimpleMacro.doc"))
    streams = dict(original.streams)
    if fault == "missing-project":
        del streams[("Macros", "PROJECT")]
    elif fault == "missing-cache":
        del streams[("Macros", "VBA", "_VBA_PROJECT")]
    elif fault == "bad-cache":
        streams[("Macros", "VBA", "_VBA_PROJECT")] = b"not VBA"
    elif fault == "bad-dir":
        streams[("Macros", "VBA", "dir")] = b""
    elif fault == "embedded":
        streams = {
            ("embedded",) + path if path[0] == "Macros" else path: data
            for path, data in streams.items()
        }
    source = tmp_path / ("source.xls" if fault == "other-host" else "source.doc")
    # Let the fixture allocator reconstruct parents after moving/deleting components.
    write_source(source, streams)
    assert not ole.inspect_ole(str(source)).eligible


def test_property_reader_agrees_with_real_unsigned_projects():
    import olefile

    for filename in ["SimpleMacro.doc", "SimpleMacro.xls", "external_name.xls"]:
        path = str(CORPUS / filename)
        compound = read_compound(path)
        check_document_summary(compound.streams[("\x05DocumentSummaryInformation",)])
        with olefile.OleFileIO(path) as reader:
            assert 0x18 not in reader.getproperties("\x05DocumentSummaryInformation")
            assert not reader.parsing_issues


def test_non_simple_property_storage_does_not_authorize_rewrite(tmp_path):
    source = tmp_path / "source.xls"
    original = read_compound(str(CORPUS / "SimpleMacro.xls"))
    streams = dict(original.streams)
    del streams[("\x05DocumentSummaryInformation",)]
    streams[("\x05DocumentSummaryInformation", "CONTENTS")] = summary_properties()
    write_source(source, streams)
    assert "Non-simple" in ole.inspect_ole(str(source)).reason
    assert CompoundFile(source.read_bytes()).streams == streams
