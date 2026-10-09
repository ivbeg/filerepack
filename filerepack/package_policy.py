"""Application package rules layered on archive member preservation."""

import hashlib
import posixpath
import sqlite3
import struct
import zipfile
from dataclasses import dataclass
from typing import Dict, FrozenSet, NoReturn, Optional
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from .archive_manifest import ArchivePreservationError, member_path
from .markup import minify_xml_bytes
from .qgis import minify_qgis_bytes, sqlite_fingerprint
from . import candidates as tx
from .native import MAX_NATIVE_BYTES

_ODF_NS = 'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
_CONTAINER_NS = 'urn:oasis:names:tc:opendocument:xmlns:container'
_OPF_NS = 'http://www.idpf.org/2007/opf'
_MAX_CONTROL_BYTES = 4 * 1024 * 1024
_ODF_EXTS = frozenset(
    'odt ods odp odg odf odb odc odi odm ott ots otp otg oth otm otc oti otf'.split()
)


@dataclass(frozen=True)
class PackagePolicy:
    kind: str
    controls: FrozenSet[str]
    hashes: Dict[str, str]


def _reject(reason: str) -> NoReturn:
    raise ArchivePreservationError('package policy: ' + reason)


def _payload(archive: zipfile.ZipFile, name: str) -> bytes:
    if name not in archive.namelist() or archive.getinfo(name).is_dir():
        _reject('missing required member: ' + name)
    if archive.getinfo(name).file_size > _MAX_CONTROL_BYTES:
        _reject('control file exceeds supported size: ' + name)
    return archive.read(name)


def _xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    data = minify_xml_bytes(_payload(archive, name))
    if data is None:
        _reject('malformed or unsupported control XML: ' + name)
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        _reject('unsupported control XML: ' + name)


def _layout(path: str, archive: zipfile.ZipFile) -> bytes:
    entries = archive.infolist()
    if not entries or entries[0].filename != 'mimetype' or entries[0].header_offset != 0:
        _reject('mimetype must be the first physical entry')
    mime = entries[0]
    if mime.compress_type != zipfile.ZIP_STORED or mime.extra or mime.file_size > 128:
        _reject('mimetype must be stored with no extra field')
    with open(path, 'rb') as fh:
        header = fh.read(30)
        if len(header) != 30:
            _reject('truncated local mimetype header')
        fields = struct.unpack('<4s5H3I2H', header)
        if (fields[0] != b'PK\x03\x04' or fields[3] != 0 or fields[-1] != 0
                or fh.read(fields[-2]) != b'mimetype'):
            _reject('invalid local mimetype header')
    if any(info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
           or info.flag_bits & 1 for info in entries):
        _reject('unsupported package compression/encryption')
    if any(name.lower().startswith('meta-inf/') and
           (name.lower().endswith('signatures.xml') or
            name.lower() in ('meta-inf/encryption.xml', 'meta-inf/rights.xml'))
           for name in archive.namelist()):
        _reject('signed, encrypted or rights-managed package is protected')
    return _payload(archive, 'mimetype')


def _odf(archive: zipfile.ZipFile, mime: bytes) -> FrozenSet[str]:
    root = _xml(archive, 'META-INF/manifest.xml')
    if root.tag != '{' + _ODF_NS + '}manifest':
        _reject('unsupported ODF manifest namespace')
    entries = {}
    for node in root:
        if node.tag != '{' + _ODF_NS + '}file-entry':
            _reject('unknown ODF manifest record')
        name = node.get('{' + _ODF_NS + '}full-path', '')
        if not name or name in entries:
            _reject('ambiguous ODF manifest path')
        entries[name] = node
        if list(node) or any('checksum' in attr for attr in node.attrib):
            _reject('encrypted/checksummed or unknown ODF manifest semantics')
        if name == '/':
            if node.get('{' + _ODF_NS + '}media-type', '').encode() != mime:
                _reject('ODF root MIME type does not match')
        elif member_path(name) != name.rstrip('/'):
            _reject('noncanonical ODF manifest path')
        elif name not in archive.namelist() and not name.endswith('/'):
            _reject('ODF manifest references a missing member')
        size = node.get('{' + _ODF_NS + '}size')
        if size is not None and (name == '/' or name not in archive.namelist()
                                 or int(size) != archive.getinfo(name).file_size):
            _reject('ODF manifest size does not match')
    if '/' not in entries:
        _reject('missing ODF root declaration')
    for info in archive.infolist():
        if (not info.is_dir() and info.filename != 'mimetype'
                and not info.filename.startswith('META-INF/') and info.filename not in entries):
            _reject('ODF member absent from manifest: ' + info.filename)
    _payload_exists(archive, 'content.xml')
    return frozenset({'mimetype', *(name for name in archive.namelist()
                                  if name.startswith('META-INF/'))})


def _reference(base: str, value: str) -> str:
    url = urlsplit(value)
    if url.scheme or url.netloc or url.query or not url.path:
        _reject('unsupported remote or invalid publication reference')
    name = posixpath.normpath(posixpath.join(base, unquote(url.path)))
    if member_path(name) != name or name.startswith('../'):
        _reject('publication reference escapes package')
    return name


def _epub(archive: zipfile.ZipFile) -> FrozenSet[str]:
    container = _xml(archive, 'META-INF/container.xml')
    if container.tag != '{' + _CONTAINER_NS + '}container':
        _reject('invalid EPUB container namespace')
    rootfiles = container.findall(
        './{' + _CONTAINER_NS + '}rootfiles/{' + _CONTAINER_NS + '}rootfile'
    )
    if not rootfiles:
        _reject('EPUB has no rootfile')
    controls = {'mimetype', *(name for name in archive.namelist() if name.startswith('META-INF/'))}
    for rootfile in rootfiles:
        if rootfile.get('media-type') != 'application/oebps-package+xml':
            _reject('unsupported EPUB rootfile type')
        name = _reference('', rootfile.get('full-path', ''))
        controls.add(name)
        root = _xml(archive, name)
        if root.tag != '{' + _OPF_NS + '}package' or root.get('version') not in ('2.0', '3.0'):
            _reject('unsupported EPUB package document')
        manifest = root.find('{' + _OPF_NS + '}manifest')
        spine = root.find('{' + _OPF_NS + '}spine')
        if manifest is None or spine is None:
            _reject('missing EPUB manifest/spine')
        ids = set()
        for item in manifest:
            identity = item.get('id')
            if item.tag != '{' + _OPF_NS + '}item' or not identity or identity in ids:
                _reject('ambiguous EPUB manifest identity')
            ids.add(identity)
            reference = _reference(posixpath.dirname(name), item.get('href', ''))
            _payload_exists(archive, reference)
        if not ids or not list(spine):
            _reject('empty EPUB manifest/spine')
        for itemref in spine:
            if itemref.tag != '{' + _OPF_NS + '}itemref' or itemref.get('idref') not in ids:
                _reject('EPUB spine references an absent item')
    return frozenset(controls)


def _payload_exists(archive: zipfile.ZipFile, name: str) -> None:
    if name not in archive.namelist() or archive.getinfo(name).is_dir():
        _reject('missing publication resource: ' + name)


def _qgis(archive: zipfile.ZipFile) -> PackagePolicy:
    projects = [info.filename for info in archive.infolist()
                if not info.is_dir() and info.filename.lower().endswith('.qgs')]
    if len(projects) != 1 or '/' in projects[0]:
        _reject('QGZ requires one root-level QGS project')
    project = projects[0]
    compact = minify_qgis_bytes(_payload(archive, project))
    if compact is None:
        _reject('malformed or unsupported QGIS project')
    hashes = {project: hashlib.sha256(compact).hexdigest()}
    mutable = {project}
    for name in archive.namelist():
        if archive.getinfo(name).is_dir():
            continue
        if name.lower().endswith('.qgd'):
            if name[:-4] != project[:-4]:
                _reject('QGIS auxiliary database does not match its project')
            if any(name + suffix in archive.namelist() for suffix in ('-wal', '-journal')):
                _reject('QGIS auxiliary database has pending transaction sidecars')
            size = archive.getinfo(name).file_size
            if size > MAX_NATIVE_BYTES:
                _reject('QGIS auxiliary database exceeds supported bounds')
            if size:
                temporary = tx.make_temp('.qgd')
                try:
                    with open(temporary, 'wb') as target:
                        with archive.open(name) as source:
                            for block in iter(lambda: source.read(tx.COPY_BUF), b''):
                                target.write(block)
                    hashes[name] = sqlite_fingerprint(temporary)
                except (OSError, ValueError, sqlite3.Error) as error:
                    _reject('unsupported QGIS auxiliary database: ' + str(error))
                finally:
                    tx.remove_quietly(temporary)
                mutable.add(name)
            else:
                hashes[name] = hashlib.sha256(b'').hexdigest()
    controls = frozenset(name for name in archive.namelist() if name not in mutable)
    hashes.update({name: _zip_hash(archive, name)
                   for name in controls if not archive.getinfo(name).is_dir()})
    return PackagePolicy('qgis', controls, hashes)


def _zip_hash(archive: zipfile.ZipFile, name: str) -> str:
    checksum = hashlib.sha256()
    with archive.open(name) as source:
        for block in iter(lambda: source.read(tx.COPY_BUF), b''):
            checksum.update(block)
    return checksum.hexdigest()


def inspect_package(path: str, extension: str) -> Optional[PackagePolicy]:
    with zipfile.ZipFile(path) as archive:
        if extension == 'mellel':
            root = _xml(archive, 'main.xml')
            if (root.tag != 'archive' or root.get('creator') != 'com.redlex.mellel'
                    or not (root.get('writer-version', '').isdigit()
                            and root.get('compatibility-version', '').isdigit())):
                _reject('unsupported Mellel document control')
            for node in root.iter('image-data'):
                references, extensions = node.findall('image-ref'), node.findall('extension-hint')
                if len(references) != 1 or len(extensions) != 1:
                    _reject('unsupported Mellel image reference')
                identity, suffix = references[0].text or '', extensions[0].text or ''
                name = 'Images/' + identity + '.' + suffix
                if (not identity or not suffix or '/' in identity or '/' in suffix
                        or member_path(name) != name):
                    _reject('invalid Mellel image reference')
                _payload_exists(archive, name)
            # Protect application-specific image relationships and every decoded byte.
            controls = frozenset(archive.namelist())
            return PackagePolicy('mellel', controls, {
                name: _zip_hash(archive, name) for name in controls
                if not archive.getinfo(name).is_dir()
            })
        if extension == 'qgz':
            return _qgis(archive)
        mime = b''
        if 'mimetype' in archive.namelist() and archive.getinfo('mimetype').file_size <= 128:
            mime = archive.read('mimetype')
        if extension == 'epub' or mime == b'application/epub+zip':
            kind = 'epub'
        elif extension in _ODF_EXTS or mime.startswith(b'application/vnd.oasis.opendocument.'):
            kind = 'odf'
        else:
            return None
        mime = _layout(path, archive)
        if kind == 'epub' and mime != b'application/epub+zip':
            _reject('invalid EPUB mimetype')
        if kind == 'odf' and (not mime.startswith(b'application/vnd.oasis.opendocument.')
                              or any(byte > 127 or byte <= 32 for byte in mime)):
            _reject('unsupported ODF mimetype')
        controls = _epub(archive) if kind == 'epub' else _odf(archive, mime)
        return PackagePolicy(kind, controls, {
            name: hashlib.sha256(_payload(archive, name)).hexdigest() for name in controls
            if not archive.getinfo(name).is_dir()
        })


def verify_package(path: str, policy: PackagePolicy) -> None:
    extension = {'epub': 'epub', 'odf': 'odt', 'qgis': 'qgz', 'mellel': 'mellel'}[policy.kind]
    candidate = inspect_package(path, extension)
    if candidate != policy:
        _reject('changed package controls or required structure')
