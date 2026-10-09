"""Compact qualified NIBArchive tables without merging or instantiating objects.

The version 1/coder 9–10 layout is described in nibsqueeze/NibArchive.md and
https://www.mothersruin.com/software/Archaeology/reverse/uinib.html. Sharing
identical *stored values* preserves object identity; deduplicating objects does
not. Keyed-plist nibs and undocumented versions/framing are left unchanged.
"""

import hashlib
import logging
import struct
from bisect import bisect_right
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import candidates as tx
from .format_support import (
    Budget, FormatLimit, UnsupportedFormat, format_scope, read_small, unchanged, write_bytes,
)
from .models import PackResult
from .native import MAX_NATIVE_BYTES
from .transactions import guard_packer

_MAGIC = b'NIBArchive'
_HEADER = struct.Struct('<10I')
_HEADER_SIZE = 50
_WIDTHS = {0: 1, 1: 2, 2: 4, 3: 8, 4: 0, 5: 0, 6: 4, 7: 8, 9: 0, 10: 4}
_CANCEL: ContextVar[Any] = ContextVar('filerepack_nib_cancel', default=None)


def _check(budget: Budget, cancel: Any = None) -> None:
    budget.check()
    cancel = cancel if cancel is not None else _CANCEL.get()
    if cancel is not None and cancel.is_set():
        raise FormatLimit('NIB optimization cancelled')


def _varint(value: int) -> bytes:
    result = bytearray()
    while value >= 128:
        result.append(value & 127)
        value >>= 7
    result.append(value | 128)
    return bytes(result)


class _Reader:
    def __init__(self, data: bytes, start: int, end: int, budget: Budget, cancel: Any):
        self.data, self.pos, self.end = data, start, end
        self.budget, self.cancel = budget, cancel

    def take(self, count: int) -> bytes:
        _check(self.budget, self.cancel)
        if count < 0 or count > self.end - self.pos:
            raise ValueError('Truncated NIB table record')
        result = self.data[self.pos:self.pos + count]
        self.pos += count
        return result

    def integer(self) -> int:
        value = 0
        # Structural lengths/indexes are bounded to the uint32 header domain.
        for shift in range(0, 35, 7):
            byte = self.take(1)[0]
            value |= (byte & 127) << shift
            if value > 0xFFFFFFFF:
                break
            if byte & 128:
                return value
        raise ValueError('Invalid or overflowing NIB varint')

    def finish(self) -> None:
        if self.pos != self.end:
            raise UnsupportedFormat('NIB table count/length mismatch or unparsed bytes')


@dataclass(frozen=True)
class _Value:
    key: int
    kind: int
    payload: bytes

    def encode(self) -> bytes:
        length = _varint(len(self.payload)) if self.kind == 8 else b''
        return _varint(self.key) + bytes([self.kind]) + length + self.payload


@dataclass(frozen=True)
class _Class:
    name: bytes
    extra: bytes

    def encode(self) -> bytes:
        return _varint(len(self.name)) + _varint(len(self.extra) // 4) + self.extra + self.name


class NibArchive:
    def __init__(self, data: bytes, budget: Budget, cancel: Any = None):
        _check(budget, cancel)
        if len(data) < _HEADER_SIZE or data[:10] != _MAGIC:
            raise UnsupportedFormat('Not a supported compiled NIBArchive (keyed plists skipped)')
        if len(data) > MAX_NATIVE_BYTES:
            raise FormatLimit('NIB archive exceeds the supported 256 MiB limit')
        (version, coder, objects, obj_start, keys, key_start,
         values, val_start, classes, cls_start) = _HEADER.unpack_from(data, 10)
        if version != 1 or coder not in (9, 10):
            raise UnsupportedFormat(f'Unsupported NIBArchive version/coder: {version}/{coder}')
        if not (_HEADER_SIZE == obj_start <= key_start <= val_start <= cls_start <= len(data)):
            raise UnsupportedFormat('Unsupported NIB table offsets/order')
        records = objects + keys + values + classes
        budget.consume(nodes=records, decoded=len(data))
        # Reserve room for Python records, range keys and source/candidate buffers.
        budget.memory(len(data) * 4 + records * 256)
        self.budget, self.cancel, self.coder = budget, cancel, coder
        reader = _Reader(data, obj_start, key_start, budget, cancel)
        self.objects = [(reader.integer(), reader.integer(), reader.integer())
                        for _ in range(objects)]
        reader.finish()
        if any(cls >= classes or start > values or count > values - start
               for cls, start, count in self.objects):
            raise ValueError('Invalid NIB object class/value range')
        reader = _Reader(data, key_start, val_start, budget, cancel)
        self.keys = [reader.take(reader.integer()) for _ in range(keys)]
        reader.finish()
        reader = _Reader(data, val_start, cls_start, budget, cancel)
        self.values = [self._value(reader, objects, keys) for _ in range(values)]
        reader.finish()
        reader = _Reader(data, cls_start, len(data), budget, cancel)
        self.classes: List[_Class] = []
        for _ in range(classes):
            size, extra = reader.integer(), reader.integer()
            budget.consume(nodes=extra)
            auxiliary = reader.take(extra * 4)
            name = reader.take(size)
            if len(name) < 2 or name[-1:] != b'\0' or b'\0' in name[:-1]:
                raise ValueError('Invalid NIB class name termination')
            if any(index >= classes for (index,) in struct.iter_unpack('<I', auxiliary)):
                raise ValueError('Invalid NIB fallback class index')
            self.classes.append(_Class(name, auxiliary))
        reader.finish()

    @staticmethod
    def _value(reader: _Reader, objects: int, keys: int) -> _Value:
        key, kind = reader.integer(), reader.take(1)[0]
        if key >= keys:
            raise ValueError('Invalid NIB value key index')
        if kind == 8:
            size = reader.integer()
        elif kind in _WIDTHS:
            size = _WIDTHS[kind]
        else:
            raise UnsupportedFormat(f'Unsupported NIB value type: {kind}')
        payload = reader.take(size)
        if kind == 10 and struct.unpack('<I', payload)[0] >= objects:
            raise ValueError('Invalid NIB object reference')
        return _Value(key, kind, payload)

    def components(self) -> List[Tuple[int, int]]:
        """Union overlapping ranges, keeping adjacent independent ranges separate."""
        ranges = sorted((start, start + count) for _, start, count in self.objects if count)
        components: List[Tuple[int, int]] = []
        for start, end in ranges:
            _check(self.budget, self.cancel)
            if components and start < components[-1][1]:
                previous, stop = components[-1]
                components[-1] = (previous, max(stop, end))
            else:
                components.append((start, end))
        return components

    def fingerprint(self) -> bytes:
        """Compare logical records independently of physical value-table sharing."""
        digest = hashlib.sha256(_MAGIC + struct.pack('<2I', 1, self.coder))
        digest.update(struct.pack('<2I', len(self.keys), len(self.classes)))
        for key in self.keys:
            digest.update(struct.pack('<I', len(key)) + key)
        for cls in self.classes:
            digest.update(struct.pack('<2I', len(cls.name), len(cls.extra)) + cls.extra + cls.name)
        values = []
        for value in self.values:
            _check(self.budget, self.cancel)
            header = struct.pack('<IBI', value.key, value.kind, len(value.payload))
            record = hashlib.sha256(header)
            record.update(value.payload)
            values.append(record.digest())
        referenced = bytearray(len(values))
        digest.update(struct.pack('<I', len(self.objects)))
        for cls_index, start, count in self.objects:
            _check(self.budget, self.cancel)
            self.budget.consume(nodes=count)
            digest.update(struct.pack('<2I', cls_index, count))
            for index in range(start, start + count):
                referenced[index] = 1
                digest.update(values[index])
        # Unreferenced metadata is retained verbatim in logical record order.
        digest.update(struct.pack('<I', referenced.count(0)))
        for index, value_hash in enumerate(values):
            if not referenced[index]:
                digest.update(value_hash)
        return digest.digest()

    def compact(self) -> bytes:
        components = self.components()
        starts = [start for start, _ in components]
        offsets: List[int] = []
        seen: Dict[Tuple[_Value, ...], int] = {}
        values: List[_Value] = []
        referenced = bytearray(len(self.values))
        for start, end in components:
            _check(self.budget, self.cancel)
            component = tuple(self.values[start:end])
            offset = seen.get(component)
            if offset is None:
                offset = len(values)
                seen[component] = offset
                values.extend(component)
            offsets.append(offset)
            referenced[start:end] = b'\x01' * (end - start)
        values.extend(value for index, value in enumerate(self.values) if not referenced[index])
        objects = bytearray()
        for cls_index, start, count in self.objects:
            _check(self.budget, self.cancel)
            component_index = bisect_right(starts, start) - 1
            offset = offsets[component_index] + start - starts[component_index] if count else 0
            objects.extend(_varint(cls_index) + _varint(offset) + _varint(count))
        tables = [bytes(objects), b''.join(_varint(len(key)) + key for key in self.keys),
                  b''.join(value.encode() for value in values),
                  b''.join(cls.encode() for cls in self.classes)]
        header = [1, self.coder]
        offset = _HEADER_SIZE
        for count, table in zip((len(self.objects), len(self.keys), len(values), len(self.classes)),
                                tables):
            header.extend((count, offset))
            offset += len(table)
        _check(self.budget, self.cancel)
        return _MAGIC + _HEADER.pack(*header) + b''.join(tables)


def nib_fingerprint(data: bytes) -> bytes:
    with format_scope({}) as budget:
        return NibArchive(data, budget).fingerprint()


def nib_file_fingerprint(path: str) -> bytes:
    with format_scope({}) as budget:
        return NibArchive(read_small(path, budget), budget).fingerprint()


@guard_packer
def pack_nib(filepath: str, debug: bool = False, quiet: bool = False, **commit: Any) -> PackResult:
    from .validation import validate_options

    validate_options(commit)
    temporary: Optional[str] = None
    with format_scope(commit) as budget:
        token = _CANCEL.set(commit.get('_cancel_event'))
        try:
            cancel = commit.get('_cancel_event')
            _check(budget, cancel)
            original = read_small(filepath, budget)
            archive = NibArchive(original, budget, cancel)
            payload = archive.compact()
            if len(payload) >= len(original):
                return unchanged(filepath, 'no smaller NIB value-table layout')
            temporary = tx.make_temp('.nib')
            write_bytes(temporary, payload, budget)
            _check(budget, cancel)
            result = tx.commit_output(
                temporary, filepath, len(original), verify='nib', lossless=True,
                **tx.commit_kwargs(**commit),
            )
            if result is None:
                return unchanged(filepath, 'NIB candidate validation/publication refused')
            result.details = {'strategy': 'nib-value-table-compaction', 'version': 1,
                              'coder': archive.coder,
                              'objects': len(archive.objects), 'source_values': len(archive.values),
                              'candidate_values': _HEADER.unpack_from(payload, 10)[6]}
            return result
        except (OSError, ValueError, struct.error) as error:
            logging.warning('NIB optimization skipped: %s', error)
            return unchanged(filepath, str(error))
        finally:
            tx.remove_quietly(temporary)
            _CANCEL.reset(token)
