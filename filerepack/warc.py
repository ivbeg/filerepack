"""Streaming WARC recompression preserving the exact decoded record bytes."""

import hashlib
import io
import logging
import os
import re
import zlib
from contextlib import contextmanager
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple

from . import candidates as tx
from .destinations import DestinationPlan, PathReservation, normalize_path
from .format_support import (
    Budget, FormatLimit, UnsupportedFormat, _OPTIONS, format_scope, unchanged, run_operation,
)
from .models import PackResult
from .transactions import guard_packer
from .validation import validate_options

_CHUNK = 64 * 1024
_MAX_HEADER = 1024 * 1024
_FIELD_NAME = re.compile(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_REQUIRED = (b'warc-type', b'warc-record-id', b'warc-date', b'content-length')
ZOPFLI_RECORD_LIMIT = 512 * 1024


def _check(budget: Budget, cancel: Any) -> None:
    budget.check()
    if cancel is not None and cancel.is_set():
        raise FormatLimit('WARC recompression cancelled')


class _ChunkReader(io.RawIOBase):
    """Expose bounded decoder chunks to BufferedReader without buffering a record."""

    def __init__(self, chunks: Iterator[bytes]):
        super().__init__()
        self.chunks = chunks
        self.pending = b''

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        if not self.pending:
            self.pending = next(self.chunks, b'')
        count = min(len(buffer), len(self.pending))
        buffer[:count] = self.pending[:count]
        self.pending = self.pending[count:]
        return count


def _gzip_members(
    source: BinaryIO, budget: Budget, cancel: Any,
    ranges: Optional[List[Tuple[int, int]]] = None,
) -> Iterator[Iterator[bytes]]:
    """Decode each member separately; zlib verifies its header, CRC and ISIZE."""
    pending = b''

    def member_chunks(decoder: Any) -> Iterator[bytes]:
        nonlocal pending
        while not decoder.eof:
            _check(budget, cancel)
            if not pending:
                pending = source.read(_CHUNK)
            if not pending:
                raise ValueError('Truncated WARC gzip member')
            chunk = decoder.decompress(pending, _CHUNK)
            pending = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
            if chunk:
                yield chunk
        if ranges is not None:
            ranges.append((start, source.tell() - len(pending)))

    while True:
        _check(budget, cancel)
        if not pending:
            pending = source.read(_CHUNK)
        if not pending:
            return
        start = source.tell() - len(pending)
        yield member_chunks(zlib.decompressobj(31))


def operate(
    kind: str, action: str, source: str, candidate: Optional[str],
    options: Dict[str, Any], budget: Budget,
) -> Dict[str, Any]:
    """Qualified optional whole-buffer compressor, confined to the format worker."""
    from importlib.metadata import version
    if kind != 'warc-zopfli' or action != 'rewrite' or candidate is None:
        raise UnsupportedFormat('Unsupported WARC worker operation')
    if version('zopfli') != '0.4.3':
        raise UnsupportedFormat('WARC ultra requires qualified zopfli 0.4.3')
    from zopfli.gzip import compress
    from .format_support import read_small, inflate, write_bytes
    raw = inflate(read_small(source, budget), budget, 'gzip', maximum=ZOPFLI_RECORD_LIMIT)
    encoded = compress(raw, numiterations=15)
    if inflate(encoded, budget, 'gzip', maximum=ZOPFLI_RECORD_LIMIT) != raw:
        raise ValueError('Zopfli candidate does not preserve decoded WARC record')
    write_bytes(candidate, encoded, budget)
    return {'changed': True, 'details': {'encoder': 'zopfli-0.4.3-15'}}


def _copy_range(
    source: BinaryIO, target: BinaryIO, start: int, end: int, budget: Budget, cancel: Any,
) -> None:
    source.seek(start)
    remaining = end - start
    while remaining:
        block = source.read(min(_CHUNK, remaining))
        if not block:
            raise ValueError('Source WARC member changed while replaying')
        _write(target, block, budget, cancel)
        remaining -= len(block)


def _select_member(
    encoded: str, target: BinaryIO, raw_size: int, budget: Budget, cancel: Any,
    options: Dict[str, Any], source: Optional[BinaryIO], span: Optional[Tuple[int, int]],
    counts: Dict[str, Any],
) -> None:
    best = encoded
    size = os.path.getsize(encoded)
    selected = 'zlib'
    if span is not None and span[1] - span[0] <= size:
        size, selected = span[1] - span[0], 'source'
    trial = None
    try:
        if options.get('ultra') and raw_size <= ZOPFLI_RECORD_LIMIT:
            trial = tx.make_temp('.warc.gz')
            try:
                run_operation('warc-zopfli', 'rewrite', encoded, trial, options)
                trial_size = os.path.getsize(trial)
                if trial_size < size:
                    size, best, selected = trial_size, trial, 'zopfli'
            except UnsupportedFormat as exc:
                counts['zopfli_fallback'] = str(exc)
        elif options.get('ultra'):
            counts['zopfli_large_records'] = counts.get('zopfli_large_records', 0) + 1
        if selected == 'source' and source is not None and span is not None:
            _copy_range(source, target, *span, budget, cancel)
        else:
            with open(best, 'rb') as candidate:
                _copy_range(candidate, target, 0, size, budget, cancel)
        counts[selected] = counts.get(selected, 0) + 1
    finally:
        tx.remove_quietly(trial)


def _write_selected_records(
    filepath: str, target: BinaryIO, budget: Budget, cancel: Any, options: Dict[str, Any],
) -> Tuple[int, Dict[str, Any]]:
    # Eligibility is established before retaining any original member. A gzip
    # source with split/grouped records is decoded and rebuilt record by record.
    canonical = False
    if is_gzip(filepath):
        try:
            validate_warc_gzip(filepath)
            canonical = True
        except ValueError:
            budget.check()
    counts: Dict[str, Any] = {}
    if canonical:
        ranges: List[Tuple[int, int]] = []
        count = 0
        with open(filepath, 'rb') as compressed, open(filepath, 'rb') as replay:
            for chunks in _gzip_members(compressed, budget, cancel, ranges):
                temporary = tx.make_temp('.warc.gz')
                try:
                    before = budget.decoded
                    with io.BufferedReader(_ChunkReader(chunks)) as reader, \
                            open(temporary, 'wb') as out:
                        _scan_records(reader, budget, cancel, out)
                    _select_member(temporary, target, budget.decoded - before, budget, cancel,
                                   options, replay, ranges.pop(), counts)
                    count += 1
                finally:
                    tx.remove_quietly(temporary)
        return count, counts
    count = 0
    with _open_decoded(filepath, budget, cancel) as reader:
        while True:
            record = _read_header(reader, budget, cancel)
            if record is None:
                break
            header, length = record
            temporary = tx.make_temp('.warc.gz')
            try:
                compressor = zlib.compressobj(9, zlib.DEFLATED, 31)
                with open(temporary, 'wb') as out:
                    for chunk in _record_chunks(reader, header, length, budget, cancel):
                        _write(out, compressor.compress(chunk), budget, cancel)
                    _write(out, compressor.flush(), budget, cancel)
                _select_member(temporary, target, len(header) + length + 4, budget,
                               cancel, options, None, None, counts)
                count += 1
            finally:
                tx.remove_quietly(temporary)
    if not count:
        raise ValueError('WARC must contain at least one record')
    return count, counts


def _decoded_chunks(source: BinaryIO, budget: Budget, cancel: Any) -> Iterator[bytes]:
    for member in _gzip_members(source, budget, cancel):
        yield from member


def is_gzip(path: str) -> bool:
    with open(path, 'rb') as source:
        return source.read(2) == b'\x1f\x8b'


@contextmanager
def _open_decoded(path: str, budget: Budget, cancel: Any) -> Iterator[BinaryIO]:
    budget.memory(_MAX_HEADER * 4 + _CHUNK * 8)
    with open(path, 'rb') as source:
        signature = source.read(2)
        source.seek(0)
        if signature == b'\x1f\x8b':
            with io.BufferedReader(_ChunkReader(_decoded_chunks(source, budget, cancel))) as reader:
                yield reader
        else:
            yield source


def _read_header(reader: BinaryIO, budget: Budget, cancel: Any) -> Optional[Tuple[bytes, int]]:
    _check(budget, cancel)
    first = reader.readline(_CHUNK + 1)
    if not first:
        return None
    if first not in (b'WARC/1.0\r\n', b'WARC/1.1\r\n'):
        raise ValueError('Unsupported WARC version or invalid record boundary')
    header = bytearray(first)
    fields: Dict[bytes, bytes] = {}
    previous = b''
    size = len(first)
    while True:
        _check(budget, cancel)
        line = reader.readline(_CHUNK + 1)
        size += len(line)
        if size > _MAX_HEADER or len(line) > _CHUNK:
            raise FormatLimit('WARC header exceeds supported bounds')
        if not line.endswith(b'\r\n'):
            raise ValueError('Truncated or non-CRLF WARC header')
        header.extend(line)
        if line == b'\r\n':
            break
        line.decode('utf-8')
        if any(byte < 32 and byte != 9 for byte in line[:-2]) or b'\x7f' in line:
            raise ValueError('Invalid control byte in WARC header')
        previous = _collect_field(line, fields, previous)
    length = _content_length(fields)
    if size + length + 4 > budget.limits.decoded - budget.decoded:
        raise FormatLimit('WARC record exceeds remaining decoded-byte budget')
    budget.consume(nodes=1)
    return bytes(header), length


def _collect_field(line: bytes, fields: Dict[bytes, bytes], previous: bytes) -> bytes:
    if line[:1] in (b' ', b'\t'):
        if not previous:
            raise ValueError('WARC continuation has no preceding header')
        if previous in fields:
            fields[previous] += b' ' + line.strip()
        return previous
    name, colon, value = line[:-2].partition(b':')
    if not colon or not _FIELD_NAME.fullmatch(name):
        raise ValueError('Invalid WARC header field')
    name = name.lower()
    if name in _REQUIRED:
        if name in fields:
            raise ValueError('Duplicate required WARC field')
        fields[name] = value.strip()
    return name


def _content_length(fields: Dict[bytes, bytes]) -> int:
    if len(fields) != len(_REQUIRED) or not all(value.strip() for value in fields.values()):
        raise ValueError('Missing required WARC field')
    value = fields[b'content-length'].strip()
    if not re.fullmatch(rb'[0-9]{1,20}', value):
        raise ValueError('Invalid WARC Content-Length')
    return int(value)


def _record_chunks(
    reader: BinaryIO, header: bytes, length: int, budget: Budget, cancel: Any,
) -> Iterator[bytes]:
    budget.consume(decoded=len(header))
    yield header
    while length:
        _check(budget, cancel)
        chunk = reader.read(min(_CHUNK, length))
        if not chunk:
            raise ValueError('Truncated WARC content block')
        length -= len(chunk)
        budget.consume(decoded=len(chunk))
        yield chunk
    if reader.read(4) != b'\r\n\r\n':
        raise ValueError('Invalid WARC record terminator or Content-Length')
    budget.consume(decoded=4)
    yield b'\r\n\r\n'


def _write(target: BinaryIO, data: bytes, budget: Budget, cancel: Any) -> None:
    _check(budget, cancel)
    budget.consume(written=len(data))
    target.write(data)


def _scan_records(
    reader: BinaryIO, budget: Budget, cancel: Any = None, target: Optional[BinaryIO] = None,
) -> Tuple[str, int]:
    checksum = hashlib.sha256()
    count = 0
    while True:
        record = _read_header(reader, budget, cancel)
        if record is None:
            break
        header, length = record
        compressor = zlib.compressobj(9, zlib.DEFLATED, 31) if target else None
        for chunk in _record_chunks(reader, header, length, budget, cancel):
            checksum.update(chunk)
            if target is not None and compressor is not None:
                _write(target, compressor.compress(chunk), budget, cancel)
        if target is not None and compressor is not None:
            _write(target, compressor.flush(), budget, cancel)
        count += 1
    if not count:
        raise ValueError('WARC must contain at least one record')
    return checksum.hexdigest(), count


def warc_fingerprint(path: str) -> Tuple[str, int]:
    """Hash the complete decoded stream after fully validating record framing."""
    with format_scope({}) as budget:
        cancel = _OPTIONS.get().get('_cancel_event')
        with _open_decoded(path, budget, cancel) as reader:
            return _scan_records(reader, budget, cancel)


def validate_warc_gzip(path: str) -> None:
    """Candidates must have exactly one complete WARC record per gzip member."""
    with format_scope({}) as budget, open(path, 'rb') as source:
        budget.memory(_MAX_HEADER * 4 + _CHUNK * 8)
        cancel = _OPTIONS.get().get('_cancel_event')
        count = 0
        for chunks in _gzip_members(source, budget, cancel):
            with io.BufferedReader(_ChunkReader(chunks)) as reader:
                if _scan_records(reader, budget, cancel)[1] != 1:
                    raise ValueError('WARC candidate must have one record per gzip member')
            count += 1
        if not count:
            raise ValueError('WARC must contain at least one gzip member')


def has_adjacent_index(path: str) -> bool:
    """Recognize common CDX/CDXJ sidecar names, including compressed indexes."""
    stems = {path}
    if path.lower().endswith('.gz'):
        stems.add(path[:-3])
    for stem in tuple(stems):
        if stem.lower().endswith('.warc'):
            stems.add(stem[:-5])
    return any(os.path.lexists(stem + suffix) for stem in stems
               for suffix in ('.cdx', '.cdxj', '.cdx.gz', '.cdxj.gz'))


@guard_packer
def pack_warc(
    filepath: str, debug: bool = False, quiet: bool = False,
    convert_container: bool = True, **commit: Any,
) -> PackResult:
    validate_options(commit)
    filepath = normalize_path(filepath)
    indexed_path = commit.get('_warc_index_source', filepath)
    if has_adjacent_index(indexed_path):
        return unchanged(filepath, 'WARC has an adjacent CDX/CDXJ index; use a distinct output')
    compressed = is_gzip(filepath)
    if not compressed and not filepath.lower().endswith('.warc'):
        return unchanged(filepath, 'Expected a gzip envelope for compressed WARC')
    if not compressed and (not convert_container or commit.get('_nested_member')):
        return unchanged(filepath, 'Plain WARC conversion is disabled for this request/member')
    destination = filepath if compressed else filepath + '.gz'
    plan = DestinationPlan(filepath, destination, overwrite=bool(commit.get('overwrite', False)))
    plan.validate()
    with PathReservation(plan.paths, dryrun=bool(commit.get('dryrun', False))) as reservation:
        plan.validate()
        return _pack_reserved(filepath, destination, indexed_path, reservation, commit)


def _pack_reserved(
    filepath: str, destination: str, indexed_path: str, reservation: PathReservation,
    options: Dict[str, Any],
) -> PackResult:
    temporary: Optional[str] = None
    with format_scope(options) as budget:
        try:
            cancel = options.get('_cancel_event')
            temporary = tx.make_temp('.warc.gz')
            with open(temporary, 'wb') as target:
                count, selections = _write_selected_records(
                    filepath, target, budget, cancel, options,
                )
            _check(budget, cancel)
            if has_adjacent_index(indexed_path) or has_adjacent_index(destination):
                return unchanged(filepath, 'WARC has an adjacent CDX/CDXJ index')
            result = tx.commit_output(
                temporary, destination, os.path.getsize(filepath), verify='warc', lossless=True,
                reference_path=filepath, reservation=reservation,
                overwrite=destination == filepath or bool(options.get('overwrite', False)),
                rejected_path=filepath, **tx.commit_kwargs(**options),
            )
            if result is None:
                _check(budget, cancel)
                return unchanged(filepath, 'WARC candidate validation/publication refused')
            result.details = {'strategy': 'warc-record-gzip', 'records': count,
                              'compression_level': 9, 'external_indexes_require_rebuild': True,
                              'member_selections': selections,
                              'zopfli_record_limit': ZOPFLI_RECORD_LIMIT}
            if result.replaced:
                result.reason = 'Verified WARC record recompression; rebuild external indexes'
                if destination != filepath:
                    reservation.require_source_unchanged()
                    tx.remove_quietly(filepath)
            return result
        except (OSError, ValueError, EOFError, zlib.error) as error:
            logging.warning('WARC recompression skipped: %s', error)
            return unchanged(filepath, str(error))
        finally:
            tx.remove_quietly(temporary)
