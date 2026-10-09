"""Batch Parquet recompression with schema, metadata and value verification."""

import logging
from typing import Any, Iterator

_BATCH_ROWS = 65536
_LOG = logging.getLogger(__name__)


def _verify_column(left: Any, right: Any) -> bool:
    import pyarrow as pa
    if len(left) != len(right):
        return False
    dtype = left.type
    if pa.types.is_floating(dtype):
        integer = {16: pa.int16(), 32: pa.int32(), 64: pa.int64()}[dtype.bit_width]
        return bool(left.view(integer).equals(right.view(integer)))
    if (pa.types.is_list(dtype) or pa.types.is_large_list(dtype)
            or pa.types.is_fixed_size_list(dtype)):
        # Arrow equality handles null parents/offsets. Inspect visible scalar
        # children separately to retain floating-point bit patterns.
        return all(a.is_valid == b.is_valid and
                   (not a.is_valid or _verify_column(a.values, b.values))
                   for a, b in zip(left, right))
    if pa.types.is_struct(dtype):
        return bool(left.is_null().equals(right.is_null())) and all(
            _verify_column(left.field(i), right.field(i)) for i in range(dtype.num_fields)
        )
    if pa.types.is_dictionary(dtype):
        return _verify_column(left.dictionary_decode(), right.dictionary_decode())
    if pa.types.is_map(dtype):
        return all(a.is_valid == b.is_valid and
                   (not a.is_valid or _verify_column(a.values, b.values))
                   for a, b in zip(left, right))
    return bool(left.equals(right))


def _batches(source: Any) -> Iterator[Any]:
    # Reading all row groups in one call can retain column-chunk buffers for
    # the complete file. A row group can itself be large; this is not a byte cap.
    for group in range(source.metadata.num_row_groups):
        yield from source.iter_batches(batch_size=_BATCH_ROWS, row_groups=[group],
                                       use_threads=False)


def _verify_values(source: Any, output: Any) -> None:
    original, candidate = iter(_batches(source)), iter(_batches(output))
    left, right = next(original, None), next(candidate, None)
    while left is not None and right is not None:
        if not left.schema.equals(right.schema, check_metadata=True):
            raise ValueError('changed decoded Parquet schema/metadata')
        count = min(left.num_rows, right.num_rows)
        for i in range(left.num_columns):
            if not _verify_column(left.column(i).slice(0, count), right.column(i).slice(0, count)):
                raise ValueError('changed Parquet values')
        left = next(original, None) if count == left.num_rows else left.slice(count)
        right = next(candidate, None) if count == right.num_rows else right.slice(count)
    if left is not None or right is not None:
        raise ValueError('changed Parquet row count/order')


def rewrite_parquet(source_path: str, output_path: str, level: int) -> bool:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        _LOG.warning('Parquet verification unavailable: install filerepack[parquet]')
        return False
    try:
        with pq.ParquetFile(source_path, pre_buffer=False, memory_map=False) as source:
            metadata = source.metadata.metadata or {}
            schema = source.schema_arrow
            for group in range(source.metadata.num_row_groups):
                for column in range(source.metadata.num_columns):
                    info = source.metadata.row_group(group).column(column)
                    if info.file_path:
                        raise ValueError('external Parquet column chunks are unsupported')
                if getattr(source.metadata.row_group(group), 'sorting_columns', ()):
                    raise ValueError('Parquet sorting declarations are not yet supported')
            with pq.ParquetWriter(
                output_path, schema, compression='zstd', compression_level=level,
                version=source.metadata.format_version, store_schema=True,
                use_compliant_nested_type=False,
            ) as writer:
                for batch in _batches(source):
                    writer.write_batch(batch)
                writer.add_key_value_metadata(metadata)
            with pq.ParquetFile(output_path, pre_buffer=False, memory_map=False) as output:
                if not source.schema.equals(output.schema):
                    raise ValueError('changed Parquet physical schema/field identifiers')
                if not source.schema_arrow.equals(output.schema_arrow, check_metadata=True):
                    raise ValueError('changed Parquet logical schema/metadata')
                # ARROW:schema may be newly added to a source that did not contain it.
                actual = dict(output.metadata.metadata or {})
                if b'ARROW:schema' not in metadata:
                    actual.pop(b'ARROW:schema', None)
                if actual != metadata:
                    raise ValueError('changed Parquet file metadata')
                _verify_values(source, output)
        return True
    except Exception as exc:
        _LOG.warning('Parquet preservation skipped: %s', exc)
        return False
