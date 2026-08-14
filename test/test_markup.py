# -*- coding: utf-8 -*-

import json
import zipfile
from unittest.mock import patch

from filerepack.markup import minify_xml_bytes, pack_json, pack_xml, rewrite_data_uris
from filerepack.formats import identify_filename


class TestPackJson:
    def test_pretty_json_shrinks(self, tmp_path):
        path = tmp_path / 'a.json'
        path.write_text('{\n  "hello": "world",\n  "n": 1\n}\n', encoding='utf-8')
        result = pack_json(str(path), dryrun=False, keep_if_larger=True)
        assert result is not None
        assert result.replaced
        assert json.loads(path.read_text(encoding='utf-8')) == {
            'hello': 'world', 'n': 1,
        }
        assert path.read_text(encoding='utf-8') == '{"hello":"world","n":1}'

    def test_invalid_json_skipped(self, tmp_path):
        path = tmp_path / 'bad.json'
        original = '{not json'
        path.write_text(original, encoding='utf-8')
        assert pack_json(str(path)) is None
        assert path.read_text(encoding='utf-8') == original


class TestPackXml:
    def test_pretty_xml_shrinks_keeps_text(self, tmp_path):
        path = tmp_path / 'a.xml'
        path.write_text(
            '<?xml version="1.0"?>\n'
            '<root xmlns:w="http://example.test/w">\n'
            '  <w:t>Hello world</w:t>\n'
            '</root>\n',
            encoding='utf-8',
        )
        result = pack_xml(str(path), dryrun=False, keep_if_larger=True)
        assert result is not None
        assert result.replaced
        text = path.read_text(encoding='utf-8')
        assert 'Hello world' in text
        assert '\n  <' not in text

    def test_xml_space_preserve_same_line_spaces(self, tmp_path):
        path = tmp_path / 'a.xml'
        original = (
            '<?xml version="1.0"?>\n'
            '<root>\n'
            '  <t xml:space="preserve">  keep  </t>\n'
            '</root>\n'
        )
        path.write_text(original, encoding='utf-8')
        pack_xml(str(path), dryrun=False, keep_if_larger=True)
        assert '  keep  ' in path.read_text(encoding='utf-8')

    def test_unparseable_xml_skipped(self, tmp_path):
        path = tmp_path / 'bad.xml'
        original = '<root><unclosed>'
        path.write_text(original, encoding='utf-8')
        assert pack_xml(str(path)) is None
        assert path.read_text(encoding='utf-8') == original

    def test_minify_xml_bytes_none_on_garbage(self):
        assert minify_xml_bytes(b'not xml') is None

    def test_docx_wt_preserved(self, tmp_path):
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            '    <w:p>\n'
            '      <w:t>Hello world</w:t>\n'
            '    </w:p>\n'
            '  </w:body>\n'
            '</w:document>\n'
        )
        docx = tmp_path / 'a.docx'
        with zipfile.ZipFile(docx, 'w') as zf:
            zf.writestr('word/document.xml', xml)
            zf.writestr('[Content_Types].xml', '<Types></Types>')
        inner = tmp_path / 'document.xml'
        inner.write_text(xml, encoding='utf-8')
        pack_xml(str(inner), dryrun=False, keep_if_larger=True)
        assert 'Hello world' in inner.read_text(encoding='utf-8')
        assert identify_filename('word/document.xml').packer == 'xml'


class TestDataUris:
    def test_unknown_data_uri_left_alone(self):
        text = '<svg><image href="data:image/svg+xml;base64,YQ=="/></svg>'
        assert rewrite_data_uris(text) == text

    def test_packed_png_uri_replaced(self):
        import base64
        raw = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40
        b64 = base64.b64encode(raw).decode('ascii')
        text = f'<svg href="data:image/png;base64,{b64}"/>'
        smaller = b'\x89PNG\r\n\x1a\n'

        def fake_members(members, options=None):
            path = members['img']
            with open(path, 'wb') as fh:
                fh.write(smaller)
            from filerepack.containers import MemberResult
            return {
                'img': MemberResult(
                    'img', path, len(raw), len(smaller), True,
                )
            }

        with patch('filerepack.markup.pack_members', side_effect=fake_members):
            out = rewrite_data_uris(text)
        assert 'data:image/png;base64,' in out
        assert b64 not in out
