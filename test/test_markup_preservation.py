"""Exact lexical and character-data preservation for standalone and nested markup."""

import codecs
import shutil
import zipfile
from xml.etree import ElementTree as ET

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.markup import minify_xml_bytes, pack_json, pack_xml, rewrite_data_uris


CONTENT_TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types'
RELATIONSHIPS = 'http://schemas.openxmlformats.org/package/2006/relationships'


@pytest.mark.parametrize(('source', 'expected'), [
    (b'{ "n": 1.234567890123456789, "same": 1, "same": 2 }',
     b'{"n":1.234567890123456789,"same":1,"same":2}'),
    (b'{ "n": -0, "big": 1E+999999, "decimal": 1.2300e-002 }',
     b'{"n":-0,"big":1E+999999,"decimal":1.2300e-002}'),
    (b' { "escaped": "\\u0061 \\n \\\" \\\\ /", "raw": "\xc3\xa9" } ',
     b'{"escaped":"\\u0061 \\n \\\" \\\\ /","raw":"\xc3\xa9"}'),
    (b' \t 123456789012345678901234567890 \r\n', b'123456789012345678901234567890'),
    (b' \n -0.0000000000000000001 \t', b'-0.0000000000000000001'),
    (b' \n " string with spaces " \t', b'" string with spaces "'),
    (b' \n true \t', b'true'),
    (b' \n false \t', b'false'),
    (b' \n null \t', b'null'),
    (codecs.BOM_UTF8 + b' { "a" : 1 } \n', codecs.BOM_UTF8 + b'{"a":1}'),
    (b'[ "\\\\", "\\\"", { "a": [ 1, 2 ] } ]',
     b'["\\\\","\\\"",{"a":[1,2]}]'),
    (b' \n' + b'9' * 5000 + b' \n', b'9' * 5000),
], ids=['precision-duplicates', 'number-spelling', 'escaped-strings', 'integer-root',
        'decimal-root', 'string-root', 'true-root', 'false-root', 'null-root',
        'utf8-bom', 'backslashes', 'very-large-integer'])
def test_json_keeps_exact_tokens(tmp_path, source, expected):
    path = tmp_path / 'precision.JSON'
    path.write_bytes(source)
    result = pack_json(str(path))
    assert result is not None and result.replaced
    assert path.read_bytes() == expected


@pytest.mark.parametrize('source', [
    b'{"n":NaN}', b'Infinity', b'-Infinity', b'[1,]', b'{"a":1,"b":}',
    b'01', b'1 2', b'"bad\\xescape"', b'"raw\nnewline"', b'[true\x0b,false]',
    b'{"bad":"\xff"}', '{ "a": 1 }'.encode('utf-16'),
])
def test_invalid_json_is_unchanged(tmp_path, source):
    path = tmp_path / 'bad.json'
    path.write_bytes(source)
    assert pack_json(str(path), keep_if_larger=True) is None
    assert path.read_bytes() == source


@pytest.mark.parametrize('source', [
    b'<r xml:space="preserve">\n  <a/>\n  <b/>\n</r>',
    b'<r>\n  <a/>\n  <b/>\n</r>',
    b'<r><a><![CDATA[hello>\n<world]]></a>\n<b/></r>',
    b'<r>Hello <b> world </b>\n <i/> tail &amp; &#10; &#x20;</r>',
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    b'<p:r xmlns:p="urn:custom">\r\n<!-- hello>\n<world -->'
    b'<?note hello>\n<world?><p:a/>\r\n</p:r>',
    codecs.BOM_UTF8 + b'<?xml version="1.0"?><r>\n<a/>\n</r>',
    b'<html xmlns="http://www.w3.org/1999/xhtml"><p>before <b/> after</p></html>',
    b'<r>\r\n\t<a/>\r\n\t<b/>\r\n</r>',
])
def test_xml_preserves_unknown_text_and_protected_regions(source):
    assert minify_xml_bytes(source) == source


def test_xml_only_compacts_tag_syntax_in_unknown_vocabularies():
    source = (b'<p:r  xmlns:p = "urn:test"  value = "a >\n&lt; b &amp; c">\n'
              b'  <p:a   x = \'unchanged  spaces\' />\n</p:r  >')
    expected = (b'<p:r xmlns:p="urn:test" value="a >\n&lt; b &amp; c">\n'
                b'  <p:a x=\'unchanged  spaces\'/>\n</p:r>')
    assert minify_xml_bytes(source) == expected
    before, after = ET.fromstring(source), ET.fromstring(expected)
    assert [(e.tag, e.text, e.tail, e.attrib) for e in before.iter()] == [
        (e.tag, e.text, e.tail, e.attrib) for e in after.iter()
    ]


@pytest.mark.parametrize(('namespace', 'root', 'child'), [
    (CONTENT_TYPES, 'Types', 'Default'),
    (RELATIONSHIPS, 'Relationships', 'Relationship'),
])
def test_xml_known_element_only_indentation(namespace, root, child):
    source = (f'<p:{root} xmlns:p="{namespace}">\r\n  '
              f'<p:{child}/>\r\n  <p:{child}/>\r\n</p:{root}>').encode()
    expected = source.replace(b'\r\n  ', b'').replace(b'\r\n', b'')
    assert minify_xml_bytes(source) == expected


def test_known_root_obeys_xml_space_preserve():
    source = (f'<Types xmlns="{CONTENT_TYPES}" xml:space="preserve">\n'
              '  <Default/>\n</Types>').encode()
    assert minify_xml_bytes(source) == source


def test_known_root_with_child_content_remains_conservative():
    source = (f'<Relationships xmlns="{RELATIONSHIPS}">\n'
              '<Relationship>  keep\n&#10;  </Relationship>\n</Relationships>').encode()
    assert minify_xml_bytes(source) == source


def test_known_indentation_uses_byte_offsets_after_unicode_comment():
    prefix = codecs.BOM_UTF8 + '<?xml version="1.0"?><!--Привет 🌎-->'.encode()
    body = f'<Types xmlns="{CONTENT_TYPES}">\r\n <Default/>\r\n</Types>'.encode()
    assert minify_xml_bytes(prefix + body) == prefix + body.replace(b'\r\n ', b'').replace(
        b'\r\n', b'',
    )


@pytest.mark.parametrize('encoding', ['UTF-8', 'utf-8', 'US-ASCII', 'ascii'])
def test_supported_xml_encoding_declaration_is_retained(encoding):
    source = (f'<?xml version="1.0" encoding="{encoding}" standalone="yes"?>\n'
              '<r  value = "&#233; &amp; &#x20;">\r\n <a/>\r\n</r>').encode()
    expected = source.replace(b'<r  value = ', b'<r value=')
    assert minify_xml_bytes(source) == expected


def test_xml_utf8_bom_and_leading_space_survive_publication(tmp_path):
    path = tmp_path / 'bom.xml'
    source = codecs.BOM_UTF8 + b'\n<r  a = "unchanged value" />\n'
    path.write_bytes(source)
    result = pack_xml(str(path))
    assert result is not None and result.replaced
    assert path.read_bytes() == codecs.BOM_UTF8 + b'\n<r a="unchanged value"/>\n'


@pytest.mark.parametrize('extra', [
    'xml:space="preserve"', 'unexpected="attribute"',
])
def test_xml_known_namespace_is_not_enough(extra):
    source = (f'<Types xmlns="{CONTENT_TYPES}" {extra}>\n'
              '  <Custom/>\n</Types>').encode()
    assert minify_xml_bytes(source) == source


@pytest.mark.parametrize('body', [
    '\n  <Default/>\n mixed text\n',
    '\n  <Default/>\n &#10;\n',
    '\n <![CDATA[ >\n< ]]>\n <Default/>\n',
])
def test_xml_known_root_with_character_content_is_preserved(body):
    source = f'<Types xmlns="{CONTENT_TYPES}">{body}</Types>'.encode()
    assert minify_xml_bytes(source) == source


def test_xml_space_is_inherited_and_default_does_not_enable_unknown_context():
    source = (f'<r xml:space="preserve"><Types xmlns="{CONTENT_TYPES}">\n'
              '<Default/>\n</Types><a xml:space="default">\n<b/>\n</a></r>').encode()
    assert minify_xml_bytes(source) == source


@pytest.mark.parametrize('source', [
    b'<r><unclosed>', b'<r duplicate="1" duplicate="2"/>',
    b'<!DOCTYPE r [<!ENTITY custom "secret">]><r>&custom;</r>',
    b'<!DOCTYPE r SYSTEM "file:///not-read"><r/>',
    b'<r>&undefined;</r>', b'<r xml:space="invalid"/>',
    b'<?xml version="1.0" encoding="ISO-8859-1"?><r>\xe9</r>',
    b'<?xml version="1.0" encoding="ISO-8859-1"?><r/>',
    b'<?xml version="1.0" encoding="UTF-16"?><r/>',
    b'<?xml version="1.0" encoding="US-ASCII"?><r>\xc3\xa9</r>',
    b'<p:r/>',
    b'<?xml version="1.1"?><r/>', '<r>\n<a/>\n</r>'.encode('utf-16'),
])
def test_unsupported_xml_is_unchanged(tmp_path, source):
    path = tmp_path / 'unsafe.xml'
    path.write_bytes(source)
    assert minify_xml_bytes(source) is None
    assert pack_xml(str(path), keep_if_larger=True) is None
    assert path.read_bytes() == source


def test_data_uris_in_text_cdata_comments_and_pi_are_untouched(monkeypatch):
    uri = 'data:image/png;base64,YWJjZA=='
    text = (f'<r title="example {uri}">{uri}<![CDATA[{uri}]]>'
            f'<!-- {uri} --><?note {uri}?></r>')

    def forbidden(*args, **kwargs):
        pytest.fail('protected content was treated as an embedded image')

    monkeypatch.setattr('filerepack.markup._pack_image_bytes', forbidden)
    assert rewrite_data_uris(text) == text


@pytest.mark.parametrize('text', [
    '<r title="href=\'data:image/png;base64,YWJjZA==\'"/>',
    '<r href="data:image/png;base64,invalid=== trailing"/>',
    '<r href="data:image/png;base64,YWJjZA== suffix"/>',
    '<r href="data:image/png;base64,%%%"/>',
    '<broken href="data:image/png;base64,YWJjZA==">',
    '<!DOCTYPE r [<!ENTITY x "y">]><r src="data:image/png;base64,YWJjZA=="/>',
])
def test_unrecognized_attributes_and_invalid_images_are_not_decoded(monkeypatch, text):
    def forbidden(*args, **kwargs):
        pytest.fail('unrecognized or malformed image URI was decoded')

    monkeypatch.setattr('filerepack.markup._pack_image_bytes', forbidden)
    assert rewrite_data_uris(text) == text


def test_skipped_validation_records_a_reason(caplog, tmp_path):
    import logging

    with caplog.at_level(logging.DEBUG):
        path = tmp_path / 'bad.json'
        path.write_bytes(b'NaN')
        assert pack_json(str(path)) is None
        assert minify_xml_bytes(b'<!DOCTYPE r><r/>') is None
    assert 'Non-standard JSON constant: NaN' in caplog.text
    assert 'DTD and declared/external entities are unsupported' in caplog.text


@pytest.mark.parametrize('packer', [pack_json, pack_xml])
def test_markup_dry_run_keeps_source_and_removes_candidate(tmp_path, monkeypatch, packer):
    xml = packer is pack_xml
    path = tmp_path / ('input.xml' if xml else 'input.json')
    candidate = tmp_path / ('candidate.xml' if xml else 'candidate.json')
    source = b'<r  a = "v" />' if xml else b' { "n": 1.234567890123456789 } '
    path.write_bytes(source)
    monkeypatch.setattr('filerepack.candidates.make_temp', lambda suffix: str(candidate))
    result = packer(str(path), dryrun=True)
    assert result is not None and not result.replaced
    assert result.outsize < result.insize
    assert path.read_bytes() == source
    assert not candidate.exists()


@pytest.mark.parametrize('suffix', ['zip', 'docx', 'odt', 'epub'])
def test_real_nested_parts_follow_markup_contract(tmp_path, suffix):
    if not (shutil.which('7zz') or shutil.which('7z')):
        pytest.skip('7zz/7z required for real nested walking')
    if suffix == 'docx' and not shutil.which('zip'):
        pytest.skip('Info-ZIP required for OOXML')
    bodies = {
        'zip': '<r xml:space="preserve">\n  <a><![CDATA[hello>\n<world]]></a>\n</r>',
        'docx': '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main">\n <w:body><w:p><w:r>'
                '<w:t xml:space="preserve">  keep <![CDATA[hello>\n<world]]>  </w:t>'
                '</w:r></w:p></w:body>\n</w:document>',
        'odt': '<office:document-content xmlns:office="urn:oasis:names:tc:'
               'opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:'
               'opendocument:xmlns:text:1.0">\n<office:body><office:text>'
               '<text:p>before <text:span><![CDATA[hello>\n<world]]></text:span> after'
               '</text:p></office:text></office:body>\n</office:document-content>',
        'epub': '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter</title>'
                '</head>\n<body><p xml:space="preserve">before <b>bold</b> after '
                '<![CDATA[hello>\n<world]]></p></body>\n</html>',
    }
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n' + bodies[suffix]).encode()
    xml_name = {'docx': 'word/document.xml', 'odt': 'content.xml',
                'epub': 'OEBPS/chapter.xhtml'}.get(suffix, 'document.xml')
    json_source = b'{ "n": 1.234567890123456789, "key": 1, "key": 2 }\n'
    entries = {xml_name: xml, 'metadata.JSON': json_source, 'unchanged.txt': b'keep me'}
    if suffix in ('odt', 'epub'):
        from test.package_fixtures import package_entries
        entries = package_entries(suffix, entries)
    path = tmp_path / ('nested.' + suffix)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    result = FileRepacker().repack(str(path), options=RepackOptions(deep_walking=True))
    assert result is not None
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == list(entries)
        assert archive.read(xml_name) == xml
        assert archive.read('metadata.JSON') == (
            b'{"n":1.234567890123456789,"key":1,"key":2}'
        )
        assert archive.read('unchanged.txt') == b'keep me'
