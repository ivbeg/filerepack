"""Preserving Apple CAR/BOMStore compaction and known ZIP rendition recompression.

Framing references: Timac's 2018 CAR research, bomutils' original BOM research
and AssetKit's CoreUI format notes. No source asset catalog is reconstructed;
every allocated block ID and complete tree page survives. Unknown resource
codecs stay opaque. Only verified codec-2 MLEC/CELM streams are decoded.
"""

import hashlib
import logging
import struct
import zlib
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Set, Tuple

from . import candidates as tx
from .format_support import (
    Budget, FormatLimit, UnsupportedFormat, format_scope, inflate, read_small, unchanged,
    write_bytes,
)
from .models import PackResult
from .transactions import guard_packer

_HEADER = 512
_CSI = 184
_CANCEL: ContextVar[Any] = ContextVar('filerepack_car_cancel', default=None)


def _check(budget: Budget) -> None:
    budget.check()
    cancel = _CANCEL.get()
    if cancel is not None and cancel.is_set():
        raise FormatLimit('CAR optimization cancelled')


def _u32(data: bytes, offset: int = 0) -> int:
    return int(struct.unpack_from('>I', data, offset)[0])


def _field(digest: Any, data: bytes) -> None:
    digest.update(struct.pack('>Q', len(data)))
    digest.update(data)


def _gzip_header(data: bytes) -> int:
    """Find the DEFLATE start; the decoder separately verifies CRC/header framing."""
    if len(data) < 18 or data[:3] != b'\x1f\x8b\x08' or data[3] & 0xE0:
        raise ValueError('Invalid CAR gzip envelope')
    flags, position = data[3], 10
    if flags & 4:
        position += 2 + struct.unpack_from('<H', data, position)[0]
    for flag in (8, 16):
        if flags & flag:
            position = data.index(b'\0', position, len(data) - 8) + 1
    if flags & 2:
        position += 2
    if position > len(data) - 8:
        raise ValueError('Truncated CAR gzip header')
    return position


def _zip_stream(data: bytes, budget: Budget, encode: bool) -> Tuple[bytes, bytes]:
    _check(budget)
    if data[:2] == b'\x1f\x8b':
        start, trailer, codec = _gzip_header(data), 8, 'gzip'
    else:
        # Preserve the exact RFC1950 header, including its window/level hints.
        # A 32 KiB window is the qualified ZIP profile; dictionaries are unsupported.
        if len(data) < 6 or data[0] != 0x78 or data[1] & 0x20:
            raise UnsupportedFormat('Unsupported CAR zlib window or dictionary')
        start, trailer, codec = 2, 4, 'zlib'
    raw = inflate(data, budget, codec)
    digest = hashlib.sha256(codec.encode())
    _field(digest, data[:start])
    _field(digest, data[-trailer:])
    _field(digest, raw)
    if encode:
        encoder = zlib.compressobj(9, zlib.DEFLATED, -15)
        deflated = encoder.compress(raw) + encoder.flush()
        candidate = data[:start] + deflated + data[-trailer:]
        _check(budget)
        if len(candidate) < len(data):
            return candidate, digest.digest()
    return data, digest.digest()


def _zip_body(body: bytes, budget: Budget, encode: bool) -> Tuple[bytes, bytes, int]:
    version, codec, count = struct.unpack_from('<3I', body, 4)
    if codec != 2 or version not in (0, 1):
        return body, hashlib.sha256(b'opaque' + body).digest(), 0
    digest = hashlib.sha256(b'zip-body' + body[:12])
    changed = 0
    if version == 0:
        if len(body) != 16 + count:
            raise ValueError('CAR ZIP payload length mismatch')
        stream, normalized = _zip_stream(body[16:], budget, encode)
        _field(digest, normalized)
        changed = int(stream != body[16:])
        return body[:12] + struct.pack('<I', len(stream)) + stream, digest.digest(), changed
    if not count:
        raise ValueError('CAR ZIP rendition has no bands')
    budget.consume(nodes=count)
    digest.update(body[12:16])
    position, chunks = 16, []
    for _ in range(count):
        _check(budget)
        header = body[position:position + 20]
        if len(header) != 20 or header[:4] != b'KCBC':
            raise ValueError('Invalid CAR ZIP band header')
        size = struct.unpack_from('<I', header, 16)[0]
        end = position + 20 + size
        if end > len(body):
            raise ValueError('Truncated CAR ZIP band')
        original = body[position + 20:end]
        stream, normalized = _zip_stream(original, budget, encode)
        _field(digest, header[:16])
        _field(digest, normalized)
        chunks.append(header[:16] + struct.pack('<I', len(stream)) + stream)
        changed += int(stream != original)
        position = end
    if position != len(body):
        raise ValueError('Unexpected CAR ZIP band trailing bytes')
    return body[:16] + b''.join(chunks), digest.digest(), changed


def _rendition(data: bytes, budget: Budget, encode: bool) -> Tuple[bytes, bytes, int]:
    if len(data) < _CSI or data[:4] != b'ISTC':
        raise UnsupportedFormat('Unsupported CAR rendition header')
    if struct.unpack_from('<I', data, 4)[0] != 1:
        raise UnsupportedFormat('Unsupported CAR CSI version')
    tlv_size, _, _, body_size = struct.unpack_from('<4I', data, 168)
    start = _CSI + tlv_size
    if start > len(data) or body_size != len(data) - start:
        raise ValueError('CAR CSI metadata/payload length mismatch')
    position = _CSI
    while position < start:
        _check(budget)
        if start - position < 8:
            raise ValueError('Truncated CAR TLV header')
        length = struct.unpack_from('<I', data, position + 4)[0]
        position += 8 + length
        if position > start:
            raise ValueError('Invalid CAR TLV length')
        budget.consume(nodes=1)
    body = data[start:]
    if body[:4] not in (b'MLEC', b'CELM'):
        return data, hashlib.sha256(b'opaque-rendition' + data).digest(), 0
    if len(body) < 16:
        raise ValueError('Truncated CAR MLEC header')
    rewritten, normalized, changed = _zip_body(body, budget, encode)
    digest = hashlib.sha256(b'rendition')
    _field(digest, data[:180])
    _field(digest, data[_CSI:start])
    _field(digest, normalized)
    result = data[:180] + struct.pack('<I', len(rewritten)) + data[_CSI:start] + rewritten
    return result, digest.digest(), changed


class CarStore:
    """Bounded BOM reader; optimization and logical validation are separate methods."""

    def __init__(self, data: bytes, budget: Budget):
        _check(budget)
        if len(data) < _HEADER or data[:8] != b'BOMStore':
            raise UnsupportedFormat('Not an Apple CAR BOMStore')
        version, self.block_count, index, index_size, variables, vars_size = (
            struct.unpack_from('>6I', data, 8)
        )
        if version != 1 or any(data[32:_HEADER]):
            raise UnsupportedFormat('Unsupported BOMStore header/version')
        self.data, self.budget = data, budget
        self.index_residue, self.vars_residue = index % 16, variables % 16
        self._range(index, index_size)
        self._range(variables, vars_size)
        table = data[index:index + index_size]
        capacity = _u32(table)
        budget.consume(nodes=capacity, decoded=len(data))
        budget.memory(len(data) * 4 + capacity * 256)
        if not capacity or 4 + capacity * 8 > len(table):
            raise ValueError('Invalid CAR block-index capacity')
        self.pointers = [struct.unpack_from('>2I', table, 4 + i * 8)
                         for i in range(capacity)]
        if self.pointers[0] != (0, 0):
            raise ValueError('CAR null block is allocated')
        self.blocks: Dict[int, bytes] = {}
        intervals = [(0, _HEADER), (index, index + index_size),
                     (variables, variables + vars_size)]
        for block_id, (address, size) in enumerate(self.pointers):
            _check(budget)
            if (address, size) == (0, 0):
                continue
            self._range(address, size)
            intervals.append((address, address + size))
            self.blocks[block_id] = data[address:address + size]
        if self.block_count not in (len(self.blocks), len(self.blocks) + 1):
            raise ValueError('CAR allocated-block count mismatch')
        self._free_ranges(table, 4 + capacity * 8, intervals)
        self._allocations(intervals)
        self.variables = data[variables:variables + vars_size]
        self.names = self._variables()
        self.renditions: Set[int] = set()
        self._catalog()

    def _range(self, address: int, size: int) -> None:
        if address < _HEADER or size <= 0 or address + size > len(self.data):
            raise ValueError('Invalid CAR allocation range')

    def _free_ranges(self, table: bytes, start: int, intervals: List[Tuple[int, int]]) -> None:
        if start == len(table):
            self.index_trailer = b''
            return
        count = _u32(table, start)
        self.budget.consume(nodes=count)
        end = start + 4 + count * 8
        if end > len(table):
            raise ValueError('Truncated CAR free-allocation table')
        self.index_trailer = table[end:]
        if len(self.index_trailer) not in (0, 16) or any(self.index_trailer):
            raise UnsupportedFormat('Unsupported CAR block-index trailer')
        for i in range(count):
            address, size = struct.unpack_from('>2I', table, start + 4 + i * 8)
            if (address, size) == (0, 0):
                continue
            self._range(address, size)
            intervals.append((address, address + size))

    def _allocations(self, intervals: List[Tuple[int, int]]) -> None:
        end = 0
        for start, stop in sorted(intervals):
            _check(self.budget)
            if start < end:
                raise ValueError('Overlapping CAR allocations')
            if any(memoryview(self.data)[end:start]):
                raise UnsupportedFormat('Unclassified nonzero CAR allocation gap')
            end = stop
        if any(memoryview(self.data)[end:]):
            raise UnsupportedFormat('Unclassified nonzero CAR trailer')

    def _block(self, block_id: int) -> bytes:
        if block_id not in self.blocks:
            raise ValueError('CAR tree/variable references an unallocated block')
        return self.blocks[block_id]

    def _variables(self) -> Dict[bytes, int]:
        count = _u32(self.variables)
        self.budget.consume(nodes=count)
        position, result = 4, {}
        for _ in range(count):
            _check(self.budget)
            block_id, size = struct.unpack_from('>IB', self.variables, position)
            end = position + 5 + size
            name = self.variables[position + 5:end]
            if end > len(self.variables) or not name or b'\0' in name or name in result:
                raise ValueError('Invalid or duplicate CAR named variable')
            self._block(block_id)
            result[name] = block_id
            position = end
        if position != len(self.variables):
            raise UnsupportedFormat('Unexpected CAR variable-table trailing bytes')
        return result

    def _catalog(self) -> None:
        if not {b'CARHEADER', b'RENDITIONS', b'KEYFORMAT'} <= self.names.keys():
            raise UnsupportedFormat('BOMStore is not a qualified CoreUI asset catalog')
        header = self._block(self.names[b'CARHEADER'])
        if len(header) != 436 or header[:4] != b'RATC':
            raise UnsupportedFormat('Unsupported CARHEADER framing')
        self.storage_version = struct.unpack_from('<I', header, 8)[0]
        if self.storage_version not in range(8, 18):
            raise UnsupportedFormat('Unsupported CAR storage version')
        key = self._block(self.names[b'KEYFORMAT'])
        if len(key) < 12 or key[:8] != b'tmfk\0\0\0\0':
            raise UnsupportedFormat('Unsupported CAR KEYFORMAT')
        tokens = struct.unpack_from('<I', key, 8)[0]
        if not 0 < tokens <= 64 or len(key) != 12 + 4 * tokens:
            raise ValueError('Invalid CAR KEYFORMAT token count')
        expected = struct.unpack_from('<I', header, 16)[0]
        for name, block_id in self.names.items():
            tree = self._block(block_id)
            if name == b'RENDITIONS' or tree[:4] == b'tree':
                entries = self._tree(tree, require_keys=name == b'RENDITIONS')
                if name == b'RENDITIONS':
                    if len(entries) != expected:
                        raise ValueError('CAR rendition count mismatch')
                    keys = [self._block(key_id) for _, key_id in entries]
                    if any(len(key) != tokens * 2 for key in keys) or len(set(keys)) != len(keys):
                        raise ValueError('Invalid or duplicate CAR rendition key')
                    self.renditions = {value for value, _ in entries}

    def _tree(self, tree: bytes, require_keys: bool) -> List[Tuple[int, int]]:
        if len(tree) not in (21, 29) or tree[:4] != b'tree' or _u32(tree, 4) != 1:
            raise UnsupportedFormat('Unsupported CAR BOM tree header')
        root, page_size, count = struct.unpack_from('>3I', tree, 8)
        inline = tree[20]
        if inline not in (0, 1) or (require_keys and inline) or not 12 <= page_size <= 1048576:
            raise UnsupportedFormat('Unsupported CAR tree page/key profile')
        nodes = self._tree_nodes(root, page_size, inline)
        entries = self._tree_entries(nodes, count)
        if len(entries) != count:
            raise ValueError('CAR tree entry count mismatch')
        return entries

    def _tree_nodes(
        self, root: int, page_size: int, inline: int,
    ) -> Dict[int, Tuple[int, int, int, List[Tuple[int, int]]]]:
        nodes: Dict[int, Tuple[int, int, int, List[Tuple[int, int]]]] = {}
        pending = [(root, 0)]
        while pending:
            _check(self.budget)
            block_id, depth = pending.pop()
            if block_id in nodes:
                continue
            if depth > 32:
                raise ValueError('CAR tree depth overflow')
            data = self._block(block_id)
            if len(data) < max(12, page_size):
                raise ValueError('Truncated CAR tree page')
            leaf, length, forward, backward = struct.unpack_from('>HHII', data)
            if leaf not in (0, 1) or 12 + length * 8 > len(data):
                raise ValueError('Invalid CAR tree node length/type')
            self.budget.consume(nodes=1 + length)
            pairs = [struct.unpack_from('>2I', data, 12 + i * 8) for i in range(length)]
            nodes[block_id] = leaf, forward, backward, pairs
            for value, key in pairs:
                self._block(value)
                if not inline:
                    self._block(key)
            if not leaf:
                if not pairs and (forward or backward):
                    raise ValueError('Empty CAR internal tree node')
                pending.extend((value, depth + 1) for value, _ in pairs)
            pending.extend((link, depth) for link in (forward, backward) if link)
        for _, forward, backward, _ in nodes.values():
            if any(link and link not in nodes for link in (forward, backward)):
                raise ValueError('CAR tree sibling references an unknown node')
        return nodes

    def _tree_entries(
        self, nodes: Dict[int, Tuple[int, int, int, List[Tuple[int, int]]]], count: int,
    ) -> List[Tuple[int, int]]:
        leaves = [block_id for block_id, node in nodes.items() if node[0]]
        first_leaves = [block_id for block_id in leaves if nodes[block_id][2] == 0]
        if not leaves:
            if count:
                raise ValueError('Nonempty CAR tree has no leaf')
            ordered_leaves: List[int] = []
        else:
            if len(first_leaves) != 1:
                raise ValueError('CAR tree has an ambiguous first leaf')
            ordered_leaves, leaf_seen = [], set()
            current = first_leaves[0]
            while current:
                if current in leaf_seen or current not in leaves:
                    raise ValueError('Cyclic or invalid CAR leaf chain')
                leaf_seen.add(current)
                ordered_leaves.append(current)
                current = nodes[current][1]
            if len(leaf_seen) != len(leaves):
                raise ValueError('CAR tree has an unlinked leaf')
        result: List[Tuple[int, int]] = []
        for index, block_id in enumerate(ordered_leaves):
            _, forward, backward, pairs = nodes[block_id]
            previous = ordered_leaves[index - 1] if index else 0
            following = ordered_leaves[index + 1] if index + 1 < len(ordered_leaves) else 0
            if (forward, backward) != (following, previous):
                raise ValueError('Invalid CAR leaf forward/backward chain')
            result.extend(pairs)
        if len(result) != count:
            raise ValueError('CAR tree entry count mismatch')
        return result

    def fingerprint(self) -> bytes:
        digest = hashlib.sha256(self.data[:16] + self.data[32:_HEADER])
        _field(digest, self.variables)
        for block_id, block in sorted(self.blocks.items()):
            _check(self.budget)
            digest.update(struct.pack('>I', block_id))
            normalized = (_rendition(block, self.budget, False)[1]
                          if block_id in self.renditions else hashlib.sha256(block).digest())
            _field(digest, normalized)
        return digest.digest()

    def compact(self) -> Tuple[bytes, int]:
        output = bytearray(self.data[:_HEADER])
        pointers = [(0, 0)] * (max(self.blocks) + 1)
        changed = 0
        for block_id in sorted(self.blocks, key=lambda index: self.pointers[index][0]):
            _check(self.budget)
            block = self.blocks[block_id]
            if block_id in self.renditions:
                block, _, streams = _rendition(block, self.budget, True)
                changed += streams
            output.extend(b'\0' * ((self.pointers[block_id][0] - len(output)) % 16))
            pointers[block_id] = len(output), len(block)
            output.extend(block)
        output.extend(b'\0' * ((self.vars_residue - len(output)) % 16))
        variables = len(output)
        output.extend(self.variables)
        output.extend(b'\0' * ((self.index_residue - len(output)) % 16))
        index = len(output)
        output.extend(struct.pack('>I', len(pointers)))
        for address, size in pointers:
            output.extend(struct.pack('>2I', address, size))
        output.extend(struct.pack('>I', 0) + self.index_trailer)
        struct.pack_into('>4I', output, 16, index, len(output) - index,
                         variables, len(self.variables))
        _check(self.budget)
        return bytes(output), changed


def car_fingerprint(data: bytes) -> bytes:
    with format_scope({}) as budget:
        return CarStore(data, budget).fingerprint()


def car_file_fingerprint(path: str) -> bytes:
    with format_scope({}) as budget:
        return CarStore(read_small(path, budget), budget).fingerprint()


@guard_packer
def pack_car(filepath: str, debug: bool = False, quiet: bool = False, **commit: Any) -> PackResult:
    from .validation import validate_options

    validate_options(commit)
    temporary: Optional[str] = None
    with format_scope(commit) as budget:
        token = _CANCEL.set(commit.get('_cancel_event'))
        try:
            original = read_small(filepath, budget)
            catalog = CarStore(original, budget)
            payload, streams = catalog.compact()
            if len(payload) >= len(original):
                return unchanged(filepath, 'no smaller CAR stream/allocation layout')
            temporary = tx.make_temp('.car')
            write_bytes(temporary, payload, budget)
            _check(budget)
            result = tx.commit_output(
                temporary, filepath, len(original), verify='car', lossless=True,
                **tx.commit_kwargs(**commit),
            )
            if result is None:
                result = unchanged(filepath, 'CAR candidate validation/publication refused')
                result.status, result.reason_code = 'failed', 'candidate_refused'
                return result
            result.details = {'strategy': 'car-zip-and-bom-compaction',
                              'storage_version': catalog.storage_version,
                              'blocks': len(catalog.blocks), 'renditions': len(catalog.renditions),
                              'recompressed_streams': streams}
            return result
        except (OSError, ValueError, struct.error, zlib.error) as error:
            logging.warning('CAR optimization skipped: %s', error)
            from .format_support import FormatLimit, OperationCancelled
            result = unchanged(filepath, str(error))
            if isinstance(error, OperationCancelled):
                result.status, result.reason_code = 'cancelled', 'cancelled'
            elif isinstance(error, FormatLimit):
                result.status, result.reason_code = 'skipped', 'resource_limit'
            elif isinstance(error, UnsupportedFormat):
                result.status, result.reason_code = 'unsupported', 'unsupported_profile'
            else:
                result.status, result.reason_code = 'failed', 'invalid_input'
            return result
        finally:
            tx.remove_quietly(temporary)
            _CANCEL.reset(token)
