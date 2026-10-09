# -*- coding: utf-8 -*-

"""JSON/XML minification and data-URI image extraction."""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, FrozenSet, List, NoReturn, Optional, Tuple
from xml.parsers import expat

from .containers import pack_members, staging_dir
from .models import PackResult
from .native import MAX_NATIVE_BYTES
from . import candidates as tx
from .transactions import guard_packer


_JSON_SPACE_OR_STRING = re.compile(rb'"(?:[^"\\]|\\.)*"|[ \t\r\n]+', re.DOTALL)
_XML_WHITESPACE = re.compile(rb'[ \t\r\n]+')
_XML_MARKUP = re.compile(
    rb'<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>|<(?:"[^"]*"|\'[^\']*\'|[^\'">])*?>',
    re.DOTALL,
)
_XML_QUOTES = re.compile(rb'("[^"]*"|\'[^\']*\')')
_XML_ATTRIBUTE = re.compile(
    r'([^\s=<>/"\']+)[ \t\r\n]*=[ \t\r\n]*(["\'])(.*?)\2',
    re.DOTALL,
)
# Only these OPC roots with recognized empty children are eligible; unknown trees keep gaps.
_CONTENT_TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types}'
_RELATIONSHIPS = 'http://schemas.openxmlformats.org/package/2006/relationships}'
_ELEMENT_ONLY = {
    _CONTENT_TYPES + 'Types': frozenset({_CONTENT_TYPES + 'Default', _CONTENT_TYPES + 'Override'}),
    _RELATIONSHIPS + 'Relationships': frozenset({_RELATIONSHIPS + 'Relationship'}),
}
_DATA_URI = re.compile(
    r'data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/= \t\r\n]+)',
    re.IGNORECASE,
)
_IMAGE_EXT = {
    'png': '.png', 'jpeg': '.jpg', 'jpg': '.jpg',
    'gif': '.gif', 'webp': '.webp',
}


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError('Non-standard JSON constant: ' + value)


def minify_json_bytes(data: bytes) -> Optional[bytes]:
    """Validate UTF-8 JSON without numeric conversion; retain every non-space token."""
    try:
        json.loads(
            data.decode('utf-8-sig'), parse_int=str, parse_float=str,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        logging.debug('Skipping unsupported or invalid JSON: %s', error)
        return None
    return _JSON_SPACE_OR_STRING.sub(
        lambda match: match.group(0) if match.group(0).startswith(b'"') else b'', data,
    )


@guard_packer
def pack_json(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        with open(filepath, 'rb') as fh:
            raw = fh.read(MAX_NATIVE_BYTES + 1)
        if len(raw) > MAX_NATIVE_BYTES:
            return None
    except OSError:
        return None
    payload = minify_json_bytes(raw)
    if payload is None:
        return None
    insize = len(raw)
    out_temp = tx.make_temp('.json')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(payload)
        return tx.commit_output(
            out_temp, filepath, insize, verify='json',
            **tx.commit_kwargs(**commit),
        )
    except Exception:
        tx.remove_quietly(out_temp)
        return None


_MAX_JSON_LINE = 16 * 1024 * 1024


def _json_line(line: bytes) -> Optional[bytes]:
    ending = b''
    if line.endswith(b'\r\n'):
        line, ending = line[:-2], b'\r\n'
    elif line.endswith(b'\n'):
        line, ending = line[:-1], b'\n'
    # JSON Lines is UTF-8 without a BOM and every line must contain one value.
    if line.startswith(b'\xef\xbb\xbf'):
        return None
    compact = minify_json_bytes(line)
    return None if compact is None else compact + ending


def verify_jsonl(source_path: str, candidate_path: str) -> bool:
    with open(source_path, 'rb') as source, open(candidate_path, 'rb') as candidate:
        while True:
            original = source.readline(_MAX_JSON_LINE + 1)
            output = candidate.readline(_MAX_JSON_LINE + 1)
            if not original:
                return not output
            if len(original) > _MAX_JSON_LINE or _json_line(original) != output:
                return False


@guard_packer
def pack_jsonl(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    """Compact one record at a time without changing tokens or line boundaries."""
    out_temp = tx.make_temp('.jsonl')
    try:
        with open(filepath, 'rb') as source, open(out_temp, 'wb') as target:
            while True:
                line = source.readline(_MAX_JSON_LINE + 1)
                if not line:
                    break
                if len(line) > _MAX_JSON_LINE:
                    return None
                compact = _json_line(line)
                if compact is None:
                    return None
                target.write(compact)
        if not verify_jsonl(filepath, out_temp):
            return None
        return tx.commit_output(
            out_temp, filepath, os.path.getsize(filepath), verify='jsonl',
            **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError) as error:
        logging.debug('JSON Lines optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)


@dataclass
class _XmlContext:
    preserve: bool
    children: FrozenSet[str]
    eligible: bool
    gaps: List[Tuple[int, int]] = field(default_factory=list)


class _XmlPolicy:
    """Use Expat byte offsets to approve only literal OPC indentation gaps."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.stack: List[_XmlContext] = []
        self.gaps: List[Tuple[int, int]] = []
        self.parser = expat.ParserCreate(namespace_separator='}')
        self.parser.StartElementHandler = self.start
        self.parser.EndElementHandler = self.end
        self.parser.CharacterDataHandler = self.text
        self.parser.StartCdataSectionHandler = self.cdata
        self.parser.XmlDeclHandler = self.declaration
        self.parser.StartDoctypeDeclHandler = self.reject
        self.parser.EntityDeclHandler = self.reject
        self.parser.ExternalEntityRefHandler = self.reject
        self.parser.SkippedEntityHandler = self.reject

    def reject(self, *args: Any) -> NoReturn:
        raise ValueError('DTD and declared/external entities are unsupported')

    def declaration(self, version: str, encoding: Optional[str], standalone: int) -> None:
        if version != '1.0' or (encoding and encoding.lower() not in (
            'utf-8', 'utf8', 'us-ascii', 'ascii',
        )):
            raise ValueError('Only XML 1.0 in UTF-8 or ASCII is supported')

    def start(self, name: str, attrs: dict) -> None:
        space = attrs.get('http://www.w3.org/XML/1998/namespace}space')
        if space not in (None, 'preserve', 'default'):
            raise ValueError('Invalid xml:space')
        inherited = bool(self.stack and self.stack[-1].preserve)
        preserve = space == 'preserve' or (space is None and inherited)
        children = _ELEMENT_ONLY.get(name, frozenset()) if not self.stack else frozenset()
        if self.stack:
            parent = self.stack[-1]
            if name not in parent.children:
                parent.eligible = False
            if len(self.stack) > 1:
                self.stack[0].eligible = False  # Only empty children qualify for this policy.
        self.stack.append(_XmlContext(preserve, children, bool(children) and not preserve))

    def end(self, name: str) -> None:
        context = self.stack.pop()
        if context.eligible:
            self.gaps.extend(context.gaps)

    def cdata(self) -> None:
        if self.stack:
            self.stack[0].eligible = False

    def text(self, value: str) -> None:
        if not self.stack:
            return
        if len(self.stack) > 1:
            self.stack[0].eligible = False
        context = self.stack[-1]
        if not context.eligible:
            return
        # Entity references and mixed content disqualify the whole context.
        match = _XML_WHITESPACE.match(self.data, self.parser.CurrentByteIndex)
        if value.strip(' \t\r\n') or match is None:
            context.eligible = False
        else:
            context.gaps.append(match.span())


def _xml_gaps(data: bytes) -> Optional[List[Tuple[int, int]]]:
    try:
        data.decode('utf-8-sig')
        policy = _XmlPolicy(data)
        policy.parser.Parse(data, True)
    except (ValueError, LookupError, expat.ExpatError) as error:
        logging.debug('Skipping unsupported or invalid XML: %s', error)
        return None
    return policy.gaps


def _compact_xml_tag(match: re.Match[bytes]) -> bytes:
    tag = match.group(0)
    if tag.startswith((b'<!', b'<?')):
        return tag
    pieces = _XML_QUOTES.split(tag)
    for index in range(0, len(pieces), 2):
        syntax = _XML_WHITESPACE.sub(b' ', pieces[index])
        syntax = re.sub(rb' *([=/]) *', rb'\1', syntax)
        pieces[index] = syntax.replace(b' >', b'>')
    return b''.join(pieces)


def minify_xml_bytes(data: bytes) -> Optional[bytes]:
    """Preserve lexical content; compact tag syntax and proven OPC indentation only."""
    gaps = _xml_gaps(data)
    if gaps is None:
        return None
    chunks = []
    cursor = 0
    for start, end in sorted(set(gaps)):
        if start >= cursor:
            chunks.append(data[cursor:start])
        cursor = max(cursor, end)
    chunks.append(data[cursor:])
    return _XML_MARKUP.sub(_compact_xml_tag, b''.join(chunks))


def _pack_image_bytes(
    data: bytes, ext: str, options: Optional[dict],
) -> Optional[bytes]:
    with staging_dir() as tmp:
        path = os.path.join(tmp, 'embed' + ext)
        with open(path, 'wb') as fh:
            fh.write(data)
        result = pack_members({'img': path}, options).get('img')
        if result is None or not result.shrank:
            return None
        with open(result.path, 'rb') as fh:
            return fh.read()


def rewrite_data_uris(text: str, options: Optional[dict] = None) -> str:
    """Optimize whole image URIs in href/src attributes, preserving protected regions."""
    try:
        data = text.encode('utf-8')
    except UnicodeError:
        return text
    if _xml_gaps(data) is None:
        return text

    def _repl(match: re.Match[str]) -> str:
        original = str(match.group(0))
        subtype = match.group(1).lower()
        ext = _IMAGE_EXT.get(subtype)
        if ext is None:
            return original
        try:
            encoded = re.sub(r'[ \t\r\n]', '', match.group(2))
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return original
        packed = _pack_image_bytes(raw, ext, options)
        if packed is None or len(packed) >= len(raw):
            return original
        mime = 'jpeg' if subtype in ('jpg', 'jpeg') else subtype
        b64 = base64.b64encode(packed).decode('ascii')
        return f'data:image/{mime};base64,{b64}'

    def _attribute(match: re.Match[str]) -> str:
        if match.group(1) not in ('href', 'xlink:href', 'src'):
            return match.group(0)
        uri = _DATA_URI.fullmatch(match.group(3))
        if uri is None:
            return match.group(0)
        original = match.group(0)
        start = match.start(3) - match.start()
        end = match.end(3) - match.start()
        return original[:start] + _repl(uri) + original[end:]

    def _tag(match: re.Match[bytes]) -> bytes:
        tag = match.group(0)
        if tag.startswith((b'<!', b'<?', b'</')):
            return tag
        return _XML_ATTRIBUTE.sub(_attribute, tag.decode('utf-8')).encode('utf-8')

    return _XML_MARKUP.sub(_tag, data).decode('utf-8')


@guard_packer
def pack_xml(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    try:
        with open(filepath, 'rb') as fh:
            raw = fh.read()
    except OSError:
        return None
    compacted = minify_xml_bytes(raw)
    if compacted is None:
        return None
    try:
        text = compacted.decode('utf-8')
    except UnicodeError:
        return None
    options = {
        'debug': debug, 'quiet': quiet, 'pack_images': bool(commit.get('pack_images', True)),
        'lossy': bool(commit.get('lossy', False)),
        'keep_meta': bool(commit.get('keep_meta', False)),
        'jpeg_quality': commit.get('jpeg_quality'),
        'png_quality': commit.get('png_quality'),
        'ultra': bool(commit.get('ultra', False)),
    }
    rewritten = rewrite_data_uris(text, options)
    payload = rewritten.encode('utf-8')
    if _xml_gaps(payload) is None:
        return None
    insize = len(raw)
    out_temp = tx.make_temp('.xml')
    try:
        with open(out_temp, 'wb') as fh:
            fh.write(payload)
        return tx.commit_output(
            out_temp, filepath, insize, verify='xml',
            **tx.commit_kwargs(**commit),
        )
    except Exception:
        tx.remove_quietly(out_temp)
        return None
