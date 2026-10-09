"""Isolated batch-preserving Arrow IPC and conservative ORC writers."""

import struct
from contextlib import contextmanager
from itertools import zip_longest
from typing import Any, Dict, Iterator, Optional

from .format_support import Budget, UnsupportedFormat


def _footer_metadata(path: str) -> bool:
    """Arrow 19 cannot expose footer custom metadata; refuse it instead of dropping it."""
    with open(path, 'rb') as source:
        source.seek(-10, 2)
        length, magic = struct.unpack('<I6s', source.read(10))
        if magic != b'ARROW1' or length > 1024 * 1024:
            raise UnsupportedFormat('Unsupported Arrow footer bounds')
        source.seek(-10 - length, 2)
        footer = source.read(length)
    root = struct.unpack_from('<I', footer)[0]
    vtable = root - struct.unpack_from('<i', footer, root)[0]
    size = struct.unpack_from('<H', footer, vtable)[0]
    if size <= 12:
        return False
    offset = struct.unpack_from('<H', footer, vtable + 12)[0]
    if not offset:
        return False
    field = root + offset
    vector = field + struct.unpack_from('<I', footer, field)[0]
    return bool(struct.unpack_from('<I', footer, vector)[0])


@contextmanager
def ipc_reader(path: str) -> Iterator[Any]:
    import pyarrow as pa
    with pa.memory_map(path, 'r') as source:
        file_framing = source.read(6) == b'ARROW1'
        source.seek(0)
        if file_framing:
            if _footer_metadata(path):
                raise UnsupportedFormat('Arrow footer custom metadata has no preserving writer')
            reader = pa.ipc.open_file(source)
        else:
            reader = pa.ipc.open_stream(source)
        yield reader, file_framing


def ipc_batches(reader: Any, file_framing: bool) -> Iterator[Any]:
    if file_framing:
        for index in range(reader.num_record_batches):
            yield reader.get_batch_with_custom_metadata(index)
    else:
        yield from reader.iter_batches_with_custom_metadata()


def _account(batch: Any, budget: Budget) -> None:
    budget.memory(batch.nbytes)
    budget.consume(decoded=batch.nbytes, nodes=batch.num_rows)
    batch.validate(full=True)


def _ipc_operation(
    action: str, source: str, candidate: Optional[str], budget: Budget,
) -> Dict[str, Any]:
    import pyarrow as pa
    from .parquet import _verify_column
    with ipc_reader(source) as (reader, file_framing):
        if action == 'rewrite' and candidate is not None:
            create = pa.ipc.new_file if file_framing else pa.ipc.new_stream
            settings = pa.ipc.IpcWriteOptions(compression='zstd', use_threads=False)
            with pa.OSFile(candidate, 'wb') as sink, create(sink, reader.schema,
                                                          options=settings) as writer:
                for batch, metadata in ipc_batches(reader, file_framing):
                    _account(batch, budget)
                    writer.write_batch(batch, custom_metadata=metadata)
                    budget.check()
                    if sink.tell() > budget.limits.scratch - budget.written:
                        raise UnsupportedFormat('Arrow candidate exceeds scratch budget')
            import os
            budget.consume(written=os.path.getsize(candidate))
            return {'changed': True, 'details': {'framing': 'file' if file_framing else 'stream'}}
        if action == 'compare' and candidate is not None:
            with ipc_reader(candidate) as (other, other_framing):
                if file_framing != other_framing or not reader.schema.equals(
                    other.schema, check_metadata=True,
                ):
                    return {'equal': False}
                for left, right in zip_longest(ipc_batches(reader, file_framing),
                                              ipc_batches(other, other_framing)):
                    if left is None or right is None:
                        return {'equal': False}
                    a, metadata_a = left
                    b, metadata_b = right
                    _account(a, budget)
                    _account(b, budget)
                    if metadata_a != metadata_b or a.num_rows != b.num_rows or any(
                        not _verify_column(a.column(i), b.column(i)) for i in range(a.num_columns)
                    ):
                        return {'equal': False}
                return {'equal': True}
        if action == 'inspect':
            for batch, _metadata in ipc_batches(reader, file_framing):
                _account(batch, budget)
            return {'details': {'framing': 'file' if file_framing else 'stream'}}
    raise UnsupportedFormat('Unsupported Arrow operation')


def _orc_operation(
    action: str, source: str, candidate: Optional[str], budget: Budget,
) -> Dict[str, Any]:
    import os
    import pyarrow.orc as orc

    class StripeReader:
        def __init__(self, path: str):
            self.reader = orc.ORCFile(path)
            if self.reader.metadata:
                raise UnsupportedFormat('ORC custom metadata has no preserving writer')

        @property
        def metadata(self) -> Any:
            return self.reader

        def iter_batches(self, **kwargs: Any) -> Iterator[Any]:
            for index in range(self.reader.nstripes):
                batch = self.reader.read_stripe(index)
                _account(batch, budget)
                yield batch

    original = StripeReader(source)
    if action == 'rewrite' and candidate is not None:
        with orc.ORCWriter(candidate, compression='zstd') as writer:
            for batch in original.iter_batches():
                writer.write(batch)
                budget.check()
        budget.consume(written=os.path.getsize(candidate))
        return {'changed': True}
    if action == 'compare' and candidate is not None:
        other = StripeReader(candidate)
        if not original.reader.schema.equals(other.reader.schema, check_metadata=True):
            return {'equal': False}
        # Reuse the existing batch alignment and exact floating-value comparison.
        from .parquet import _verify_column
        left, right = iter(original.iter_batches()), iter(other.iter_batches())
        a, b = next(left, None), next(right, None)
        while a is not None and b is not None:
            count = min(a.num_rows, b.num_rows)
            if any(not _verify_column(a.column(i).slice(0, count), b.column(i).slice(0, count))
                   for i in range(a.num_columns)):
                return {'equal': False}
            a = next(left, None) if count == a.num_rows else a.slice(count)
            b = next(right, None) if count == b.num_rows else b.slice(count)
        return {'equal': a is None and b is None}
    if action == 'inspect':
        for _batch in original.iter_batches():
            pass
        return {'details': {'stripes': original.reader.nstripes}}
    raise UnsupportedFormat('Unsupported ORC operation')


def operate(
    kind: str, action: str, source: str, candidate: Optional[str],
    options: Dict[str, Any], budget: Budget,
) -> Dict[str, Any]:
    if kind in ('arrow-native', 'feather-native'):
        return _ipc_operation(action, source, candidate, budget)
    if kind == 'orc-native':
        return _orc_operation(action, source, candidate, budget)
    raise UnsupportedFormat('Unsupported columnar format')
