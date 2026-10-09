"""Native reader evidence for framing, batch metadata and SQLite WAL snapshots."""

import sqlite3

import pytest

from filerepack import FileRepacker


@pytest.mark.parametrize('framing', ['file', 'stream'])
def test_arrow_retains_framing_schema_and_batch_metadata(tmp_path, framing):
    pa = pytest.importorskip('pyarrow')
    source = tmp_path / 'table.arrow'
    schema = pa.schema([pa.field('value', pa.string(), nullable=False,
                                metadata={b'field': b'identifier'})],
                       metadata={b'app': b'custom'})
    create = pa.ipc.new_file if framing == 'file' else pa.ipc.new_stream
    batches = [pa.record_batch([pa.array(['repeated data' * 100] * 200)], schema=schema),
               pa.record_batch([pa.array(['more data' * 100] * 100)], schema=schema)]
    with pa.OSFile(str(source), 'wb') as sink, create(sink, schema) as writer:
        for index, batch in enumerate(batches):
            writer.write_batch(batch, custom_metadata={b'batch': str(index).encode()})
    original_size = source.stat().st_size
    summary = FileRepacker().repack(str(source))
    assert summary.outcome.status == 'replaced', summary.outcome
    assert source.stat().st_size < original_size
    with pa.memory_map(str(source), 'r') as raw:
        reader = pa.ipc.open_file(raw) if framing == 'file' else pa.ipc.open_stream(raw)
        assert reader.schema.equals(schema, check_metadata=True)
        for index, expected in enumerate(batches):
            actual, metadata = (reader.get_batch_with_custom_metadata(index)
                                if framing == 'file' else
                                reader.read_next_batch_with_custom_metadata())
            assert actual.equals(expected)
            assert metadata[b'batch'] == str(index).encode()


def test_live_sqlite_is_skipped_inplace_and_snapshot_includes_wal(tmp_path):
    source = tmp_path / 'live.sqlite'
    connection = sqlite3.connect(source)
    try:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE items (id INTEGER PRIMARY KEY, value BLOB)')
        connection.execute('INSERT INTO items VALUES (1, ?)', (b'committed WAL bytes',))
        connection.commit()
        original = source.read_bytes()
        refused = FileRepacker().repack(str(source), options={'sqlite_offline': True})
        assert refused.outcome.status == 'skipped'
        assert source.read_bytes() == original
        output = tmp_path / 'snapshot.sqlite'
        summary = FileRepacker().repack(str(source), outfile=str(output))
        assert summary.outcome.status in ('replaced', 'unchanged'), summary.outcome
        assert summary.outcome.published
        with sqlite3.connect(output) as reader:
            assert reader.execute('SELECT * FROM items').fetchall() == [(1, b'committed WAL bytes')]
            assert reader.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert source.read_bytes() == original
    finally:
        connection.close()


def test_sqlite_offline_is_explicit_and_retains_rowids_metadata_and_schema(tmp_path):
    source = tmp_path / 'offline.sqlite'
    with sqlite3.connect(source) as connection:
        connection.execute('PRAGMA user_version=41')
        connection.execute('PRAGMA application_id=1234')
        connection.execute('CREATE TABLE items (value TEXT)')
        connection.executemany('INSERT INTO items (rowid, value) VALUES (?, ?)',
                               [(3, 'kept'), (123, 'also kept')])
    original = source.read_bytes()
    refused = FileRepacker().repack(str(source))
    assert refused.outcome.status == 'skipped'
    assert source.read_bytes() == original
    result = FileRepacker().repack(str(source), options={'sqlite_offline': True})
    assert result.outcome.status in ('replaced', 'unchanged'), result.outcome
    with sqlite3.connect(source) as reader:
        assert reader.execute('SELECT rowid, value FROM items').fetchall() == [
            (3, 'kept'), (123, 'also kept'),
        ]
        assert reader.execute('PRAGMA user_version').fetchone() == (41,)
        assert reader.execute('PRAGMA application_id').fetchone() == (1234,)


def test_avro_preserves_encoded_union_choices_metadata_and_sync(tmp_path):
    fastavro = pytest.importorskip('fastavro')
    from filerepack.avro import _header, _read_operation
    from filerepack.format_support import Budget, FormatLimits
    source = tmp_path / 'records.avro'
    schema = {'type': 'record', 'name': 'Item', 'fields': [
        {'name': 'value', 'type': ['int', 'long']},
        {'name': 'text', 'type': 'string'},
    ]}
    records = [{'value': ('long', 1), 'text': 'repeated value' * 50} for _ in range(200)]
    sync = b'fixed sync bytes'
    with source.open('wb') as target:
        fastavro.writer(target, schema, records, codec='null',
                        metadata={'app': 'keep me'}, sync_marker=sync)
    before = _read_operation(str(source), None, Budget(FormatLimits()))
    summary = FileRepacker().repack(str(source))
    assert summary.outcome.status == 'replaced', summary.outcome
    after = _read_operation(str(source), None, Budget(FormatLimits()))
    assert before == after
    with source.open('rb') as reader:
        metadata, actual_sync = _header(reader)
    assert actual_sync == sync
    assert metadata[b'app'] == b'keep me'
    with source.open('rb') as reader:
        values = list(fastavro.reader(reader))
    assert len(values) == 200 and all(row['value'] == 1 for row in values)
