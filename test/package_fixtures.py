"""Small standards-shaped ODF/EPUB packages; no application rendering is assumed."""

import zipfile

ODF_MIME = b'application/vnd.oasis.opendocument.text'
ODF_NS = 'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
EPUB_CONTAINER_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
OPF_NS = 'http://www.idpf.org/2007/opf'


def package_entries(kind, extra=None):
    extra = dict(extra or {})
    if kind == 'epub':
        entries = {
            'mimetype': b'application/epub+zip',
            'META-INF/container.xml': (
                f'<container xmlns="{EPUB_CONTAINER_NS}" version="1.0"><rootfiles>'
                '<rootfile full-path="OEBPS/book.opf" media-type="application/oebps-package+xml"/>'
                '</rootfiles></container>'
            ).encode(),
            'OEBPS/chapter.xhtml': b'<html xmlns="http://www.w3.org/1999/xhtml">'
                                   b'<head><title>Test</title></head><body><p>' +
                                   b'hello ' * 10000 + b'</p></body></html>',
            'OEBPS/nav.xhtml': b'<html xmlns="http://www.w3.org/1999/xhtml" '
                              b'xmlns:epub="http://www.idpf.org/2007/ops"><head>'
                              b'<title>Contents</title></head><body><nav epub:type="toc">'
                              b'<ol><li><a href="chapter.xhtml">Chapter</a></li></ol>'
                              b'</nav></body></html>',
        }
        entries.update(extra)
        items = ''.join(f'<item id="i{i}" href="../{name}" media-type="'
                        + ('application/xhtml+xml' if name.endswith('.xhtml') else
                           'application/octet-stream') + '"'
                        + (' properties="nav"' if name == 'OEBPS/nav.xhtml' else '') + '/>'
                        for i, name in enumerate(entries)
                        if name not in ('mimetype', 'META-INF/container.xml'))
        chapter_id = list(entries).index('OEBPS/chapter.xhtml')
        entries['OEBPS/book.opf'] = (
            f'<package xmlns="{OPF_NS}" version="3.0" unique-identifier="bookid">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:identifier id="bookid">urn:uuid:test-book</dc:identifier>'
            '<dc:title>Fixture</dc:title><dc:language>en</dc:language>'
            '<meta property="dcterms:modified">2026-10-03T00:00:00Z</meta></metadata>'
            f'<manifest>{items}</manifest><spine><itemref idref="i{chapter_id}"/></spine></package>'
        ).encode()
        return entries
    entries = {
        'mimetype': ODF_MIME,
        'content.xml': b'<office:document-content '
                       b'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                       b'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
                       b'office:version="1.3"><office:body><office:text><text:p>' +
                       b'hello ' * 10000 +
                       b'</text:p></office:text></office:body></office:document-content>',
    }
    entries.update(extra)
    manifest = (f'<manifest:manifest xmlns:manifest="{ODF_NS}" manifest:version="1.3">'
                '<manifest:file-entry manifest:full-path="/" '
                f'manifest:media-type="{ODF_MIME.decode()}"/>'
                + ''.join(f'<manifest:file-entry manifest:full-path="{name}" '
                          'manifest:media-type="text/xml"/>'
                          for name in entries if name != 'mimetype')
                + '</manifest:manifest>')
    entries['META-INF/manifest.xml'] = manifest.encode()
    return entries


def write_package(path, kind, *, entries=None):
    entries = entries if entries is not None else package_entries(kind)
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data, compress_type=zipfile.ZIP_STORED)
    return entries
