"""Conservative offline DuckDB compaction with catalog/value verification."""

import hashlib
import json
import logging
import os
from typing import Any, Iterator, Optional

from . import candidates as tx
from .models import PackResult
from .native import MAX_NATIVE_BYTES
from .transactions import guard_packer

MAX_ROWS = 1_000_000
MAX_VALUE_BYTES = 256 * 1024 * 1024


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _check_file(path: str) -> None:
    if os.path.getsize(path) > MAX_NATIVE_BYTES:
        raise ValueError('DuckDB exceeds the supported 256 MiB limit')
    if os.path.lexists(path + '.wal'):
        raise ValueError('DuckDB has a pending transaction WAL')
    with open(path, 'rb') as source:
        if source.read(12)[8:12] != b'DUCK':
            raise ValueError('Not a DuckDB database')


def _connect(path: str, candidate: Optional[str] = None) -> Any:
    import duckdb
    _check_file(path)
    connection = duckdb.connect(':memory:', config={
        'autoinstall_known_extensions': 'false', 'autoload_known_extensions': 'false',
        'threads': '1', 'memory_limit': '256MB', 'temp_directory': '',
    })
    try:
        connection.execute('ATTACH ' + _literal(os.path.abspath(path)) +
                           ' AS checked (READ_ONLY)')
        if candidate is not None:
            connection.execute('ATTACH ' + _literal(os.path.abspath(candidate)) + ' AS candidate')
        # No database-supplied expressions are evaluated before this setting.
        connection.execute('SET enable_external_access=false')
        return connection
    except Exception:
        connection.close()
        raise


def _catalog(connection: Any, function: str, columns: str, order: str) -> list:
    return list(connection.execute('SELECT ' + columns + ' FROM ' + function +
                                   "() WHERE database_name='checked' ORDER BY " + order).fetchall())


def _records(connection: Any) -> list:
    for function in ('duckdb_views', 'duckdb_sequences', 'duckdb_functions'):
        condition = '' if function == 'duckdb_sequences' else ' AND NOT internal'
        if connection.execute('SELECT count(*) FROM ' + function +
                              "() WHERE database_name='checked'" + condition).fetchone()[0]:
            raise ValueError('Unsupported DuckDB views, sequences or functions')
    if connection.execute("SELECT count(*) FROM duckdb_types() "
                          "WHERE database_name='checked' AND NOT internal").fetchone()[0]:
        raise ValueError('Unsupported DuckDB custom types')
    catalogs = [
        ('duckdb_schemas', 'schema_name, comment, tags', 'schema_name'),
        ('duckdb_tables', 'schema_name, table_name, sql, comment, tags', 'schema_name, table_name'),
        ('duckdb_indexes', 'schema_name, index_name, sql, comment, tags',
         'schema_name, index_name'),
        ('duckdb_columns', 'schema_name, table_name, column_name, column_index, comment, '
         'column_default, is_nullable, data_type', 'schema_name, table_name, column_index'),
    ]
    records = [_catalog(connection, *catalog) for catalog in catalogs]
    encoded = json.dumps(records, ensure_ascii=True, sort_keys=True).encode('ascii')
    if len(encoded) > 4 * 1024 * 1024:
        raise ValueError('DuckDB catalog exceeds supported bounds')
    return records


def _arrow_type(dtype: Any) -> bool:
    import pyarrow as pa
    if (pa.types.is_list(dtype) or pa.types.is_large_list(dtype)
            or pa.types.is_fixed_size_list(dtype)):
        return _arrow_type(dtype.value_type)
    if pa.types.is_struct(dtype):
        return all(_arrow_type(field.type) for field in dtype)
    if pa.types.is_map(dtype):
        return _arrow_type(dtype.key_type) and _arrow_type(dtype.item_type)
    return any(check(dtype) for check in (
        pa.types.is_boolean, pa.types.is_integer, pa.types.is_floating, pa.types.is_decimal,
        pa.types.is_string, pa.types.is_large_string, pa.types.is_binary,
        pa.types.is_large_binary, pa.types.is_date, pa.types.is_time, pa.types.is_timestamp,
        pa.types.is_null,
    ))


def _batches(connection: Any, schema: str, table: str) -> Iterator[Any]:
    cursor = connection.execute('SELECT * FROM checked.' + _quote(schema) + '.' + _quote(table))
    reader = (cursor.to_arrow_reader(1024) if hasattr(cursor, 'to_arrow_reader')
              else cursor.fetch_record_batch(1024))
    if not all(_arrow_type(field.type) for field in reader.schema):
        raise ValueError('Unsupported DuckDB Arrow column type')
    yield from reader


def _compare_batches(left: Iterator[Any], right: Iterator[Any], usage: list) -> bool:
    from .parquet import _verify_column
    original, output = next(left, None), next(right, None)
    while original is not None and output is not None:
        if not original.schema.equals(output.schema):
            return False
        length = min(original.num_rows, output.num_rows)
        before, after = original.slice(0, length), output.slice(0, length)
        usage[0] += length
        usage[1] += before.nbytes + after.nbytes
        if usage[0] > MAX_ROWS or usage[1] > 2 * MAX_VALUE_BYTES:
            raise ValueError('DuckDB typed verification exceeds supported bounds')
        if not all(_verify_column(before.column(i), after.column(i))
                   for i in range(before.num_columns)):
            return False
        original = (next(left, None) if length == original.num_rows
                    else original.slice(length))
        output = next(right, None) if length == output.num_rows else output.slice(length)
    return original is None and output is None


def _fingerprint(connection: Any) -> str:
    records = _records(connection)
    checksum = hashlib.sha256()
    encoded = json.dumps(records, ensure_ascii=True, sort_keys=True).encode('ascii')
    checksum.update(encoded)
    columns = records[3]
    total, count = 0, 0
    for schema, table, _sql, _comment, _tags in records[1]:
        for batch in _batches(connection, schema, table):
            batch.validate(full=True)
            total += batch.nbytes
            if total > MAX_VALUE_BYTES:
                raise ValueError('DuckDB decoded Arrow values exceed supported bounds')
        # Engine VARCHAR casts retain decimal precision and nanosecond timestamps;
        # Python datetime conversion would silently discard timestamp precision.
        projection = ','.join('CAST(' + _quote(column[2]) + ' AS VARCHAR)'
                              for column in columns if column[:2] == (schema, table))
        cursor = connection.execute('SELECT ' + projection + ' FROM checked.' +
                                    _quote(schema) + '.' + _quote(table))
        rows = []
        while True:
            batch = cursor.fetchmany(128)
            if not batch:
                break
            for row in batch:
                encoded = json.dumps(row, ensure_ascii=True).encode('ascii')
                total += len(encoded)
                count += 1
                if total > MAX_VALUE_BYTES or count > MAX_ROWS:
                    raise ValueError('DuckDB logical data exceeds supported verification bounds')
                rows.append(hashlib.sha256(encoded).digest())
        checksum.update(len(rows).to_bytes(8, 'little'))
        for value in sorted(rows):
            checksum.update(value)
    return checksum.hexdigest()


def duckdb_fingerprint(path: str) -> str:
    connection = _connect(path)
    try:
        return _fingerprint(connection)
    finally:
        connection.close()


def verify_duckdb(source: str, candidate: str) -> bool:
    """Compare typed ordered batches, including nested float bits and nulls."""
    left_connection = _connect(source)
    try:
        right_connection = _connect(candidate)
        try:
            records = _records(left_connection)
            if records != _records(right_connection):
                return False
            usage = [0, 0]
            for schema, table, _sql, _comment, _tags in records[1]:
                left = iter(_batches(left_connection, schema, table))
                right = iter(_batches(right_connection, schema, table))
                if not _compare_batches(left, right, usage):
                    return False
            return True
        finally:
            right_connection.close()
    finally:
        left_connection.close()


def _rewrite(path: str, candidate: str) -> None:
    connection = _connect(path, candidate)
    try:
        _fingerprint(connection)  # Reject unsupported source objects before copying.
        connection.execute('COPY FROM DATABASE checked TO candidate')
        connection.execute('CHECKPOINT candidate')
    finally:
        connection.close()


@guard_packer
def pack_duckdb(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    temporary = tx.make_temp('.duckdb')
    try:
        expected = duckdb_fingerprint(filepath)
        tx.remove_quietly(temporary)
        tx.own_sidecar(temporary + '.wal')
        _rewrite(filepath, temporary)
        if duckdb_fingerprint(temporary) != expected:
            return None
        return tx.commit_output(
            temporary, filepath, os.path.getsize(filepath), verify='duckdb', lossless=True,
            **tx.commit_kwargs(**commit),
        )
    except Exception as error:
        logging.debug('DuckDB optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(temporary)
