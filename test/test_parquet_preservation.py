"""Real Parquet fidelity regressions, independently read through Arrow and DuckDB."""

from decimal import Decimal

import pytest

from filerepack.repack import pack_parquet

pa = pytest.importorskip('pyarrow')
pq = pytest.importorskip('pyarrow.parquet')


def rich_table():
    schema = pa.schema([
        pa.field('id', pa.uint64(), nullable=False,
                 metadata={b'PARQUET:field_id': b'42', b'role': b'identifier'}),
        pa.field('amount', pa.decimal128(20, 4)),
        pa.field('time', pa.timestamp('ns', tz='Europe/Moscow')),
        pa.field('nested', pa.list_(pa.struct([
            pa.field('label', pa.string(), metadata={b'app-field': b'keep'}),
            pa.field('flag', pa.bool_()),
        ]))),
    ], metadata={b'app': b'preserve-me', b'binary': b'\xff\0\xfe',
                 b'pandas': b'{"index_columns": [], "columns": []}'})
    values = [
        pa.array([2**63 + 5, 7, 3], type=pa.uint64()),
        pa.array([Decimal('12.3400'), None, Decimal('-0.0001')], type=schema.field(1).type),
        pa.array([1710000000000000001, None, 1710000000000000002], type=schema.field(2).type),
        pa.array([[{'label': 'a', 'flag': True}], None, []], type=schema.field(3).type),
    ]
    return pa.Table.from_arrays(values, schema=schema)


@pytest.mark.parametrize('ultra', [False, True])
def test_metadata_types_identifiers_and_order(tmp_path, ultra):
    path = tmp_path / 'values.parquet'
    pq.write_table(rich_table(), path, compression='NONE')
    before = pq.ParquetFile(path)
    expected = before.read()
    expected_metadata = before.metadata.metadata
    expected_schema = before.schema
    before.close()
    result = pack_parquet(str(path), keep_if_larger=False, ultra=ultra)
    assert result is not None and result.replaced
    after = pq.ParquetFile(path)
    assert after.schema_arrow.equals(expected.schema, check_metadata=True)
    assert after.schema.equals(expected_schema)
    assert after.metadata.metadata == expected_metadata
    assert after.read().equals(expected, check_metadata=True)
    after.close()


@pytest.mark.parametrize('nested_names', [True, False])
@pytest.mark.parametrize('rows', [0, 1001])
def test_multiple_groups_empty_files_and_list_names(tmp_path, monkeypatch, nested_names, rows):
    import filerepack.parquet as preservation
    monkeypatch.setattr(preservation, '_BATCH_ROWS', 11)
    path = tmp_path / 'groups.parquet'
    table = rich_table().take(pa.array([i % 3 for i in range(rows)], type=pa.int64()))
    pq.write_table(table, path, compression='NONE', row_group_size=7,
                   use_compliant_nested_type=nested_names)
    with pq.ParquetFile(path) as source:
        expected = source.read()
        metadata = source.metadata.metadata
    result = pack_parquet(str(path), keep_if_larger=False)
    assert result is not None and result.replaced
    with pq.ParquetFile(path) as output:
        assert output.read().equals(expected, check_metadata=True)
        assert output.metadata.metadata == metadata


def test_floats_nan_signed_zero_maps_and_dictionary(tmp_path):
    import struct
    path = tmp_path / 'floats.parquet'
    nan = struct.unpack('>d', bytes.fromhex('7ff8000000000001'))[0]
    table = pa.table({
        'floats': pa.array([0.0, -0.0, nan, float('inf'), None]),
        'nested': pa.array([[nan, -0.0], None, [], [1.0], [float('-inf')]]),
        'maps': pa.array([[('a', -0.0)], None, [], [('b', nan)], []],
                         type=pa.map_(pa.string(), pa.float64())),
        'dict': pa.array(['b', None, 'a', 'b', 'a']).dictionary_encode(),
        'float32': pa.array([0.0, -0.0, nan, None, 4.0], type=pa.float32()),
        'float16': pa.Array.from_buffers(
            pa.float16(), 5, [pa.py_buffer(bytes([0b10111])),
                             pa.py_buffer(struct.pack('<5H', 0, 0x8000, 0x7e01, 0, 0x4400))],
        ),
    })
    pq.write_table(table, path, compression='NONE')
    expected = pq.read_table(path)
    result = pack_parquet(str(path), keep_if_larger=False)
    assert result is not None and result.replaced
    output = pq.read_table(path)
    assert output.schema.equals(expected.schema, check_metadata=True)
    for name in ['floats', 'float32', 'float16']:
        integer = {'floats': pa.int64(), 'float32': pa.int32(), 'float16': pa.int16()}[name]
        assert output[name].combine_chunks().view(integer).equals(
            expected[name].combine_chunks().view(integer))


@pytest.mark.parametrize('fault', ['value', 'order', 'rows', 'metadata', 'field_id', 'nullable'])
def test_candidate_corruption_never_publishes(tmp_path, monkeypatch, fault):
    path = tmp_path / 'original.parquet'
    candidate = tmp_path / 'candidate.parquet'
    pq.write_table(rich_table(), path, compression='NONE')
    before = path.read_bytes()
    real_writer = pq.ParquetWriter

    class CorruptingWriter:
        def __init__(self, output, *args, **kwargs):
            self.output = output
            self.writer = real_writer(output, *args, **kwargs)

        def __enter__(self):
            return self

        def __getattr__(self, key):
            return getattr(self.writer, key)

        def __exit__(self, *args):
            self.writer.close()
            table = pq.read_table(self.output)
            if fault == 'value':
                table = table.set_column(0, table.schema.field(0),
                                         pa.array([9, 7, 3], type=pa.uint64()))
            elif fault == 'order':
                table = table.take(pa.array([2, 1, 0]))
            elif fault == 'rows':
                table = table.slice(0, 2)
            elif fault == 'metadata':
                table = table.replace_schema_metadata({b'app': b'changed'})
            else:
                field = table.schema.field(0)
                field = (field.with_nullable(True) if fault == 'nullable' else
                         field.with_metadata({b'PARQUET:field_id': b'43'}))
                table = table.cast(table.schema.set(0, field))
            pq.write_table(table, self.output)

    monkeypatch.setattr(pq, 'ParquetWriter', CorruptingWriter)
    monkeypatch.setattr('filerepack.candidates.make_temp', lambda suffix: str(candidate))
    assert pack_parquet(str(path), keep_if_larger=False) is None
    assert path.read_bytes() == before
    assert not candidate.exists()


@pytest.mark.parametrize('unsupported', ['int96', 'sorting', 'integer_decimal', 'invalid'])
def test_unrepresentable_input_skips(tmp_path, unsupported, caplog):
    path = tmp_path / 'unsupported.parquet'
    if unsupported == 'invalid':
        path.write_bytes(b'PAR1not a complete footerPAR1')
    elif unsupported == 'integer_decimal':
        pq.write_table(pa.table({'d': pa.array([Decimal('1.00')], type=pa.decimal128(5, 2))}),
                       path, store_decimal_as_integer=True)
    else:
        options = ({'use_deprecated_int96_timestamps': True} if unsupported == 'int96' else
                   {'sorting_columns': [pq.SortingColumn(0)]})
        pq.write_table(rich_table(), path, **options)
    before = path.read_bytes()
    assert pack_parquet(str(path), keep_if_larger=False) is None
    assert path.read_bytes() == before
    assert 'Parquet preservation skipped' in caplog.text


def test_missing_arrow_skips_even_with_duckdb(tmp_path, monkeypatch, caplog):
    import builtins
    path = tmp_path / 'values.parquet'
    pq.write_table(rich_table(), path)
    before = path.read_bytes()
    real_import = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name.startswith('pyarrow'):
            raise ImportError('not installed')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', unavailable)
    assert pack_parquet(str(path)) is None
    assert path.read_bytes() == before
    assert 'install filerepack[parquet]' in caplog.text


def test_dry_run_and_distinct_library_destination(tmp_path):
    from filerepack import FileRepacker, RepackOptions
    source = tmp_path / 'input.parquet'
    output = tmp_path / 'output.parquet'
    table = rich_table().take(pa.array([i % 3 for i in range(3000)]))
    pq.write_table(table, source, compression='NONE')
    before = source.read_bytes()
    result = FileRepacker().repack(str(source), outfile=str(output),
                                  options=RepackOptions(dryrun=True))
    assert result.total_outsize < result.total_insize
    assert source.read_bytes() == before and not output.exists()
    result = FileRepacker().repack(str(source), outfile=str(output))
    assert result.total_outsize < result.total_insize
    assert source.read_bytes() == before
    assert pq.read_table(source).equals(pq.read_table(output), check_metadata=True)


def test_independent_duckdb_reader(tmp_path):
    duckdb = pytest.importorskip('duckdb')
    path = tmp_path / 'rows.parquet'
    table = pa.table({'id': pa.array([2**63 + 7, 3, 1], type=pa.uint64()),
                      'value': [None, 'last', 'first']})
    pq.write_table(table, path, compression='NONE')
    with duckdb.connect() as conn:
        expected = conn.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
        assert pack_parquet(str(path), keep_if_larger=False).replaced
        assert conn.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchall() == expected


def test_recompression_uses_batches_not_whole_table(tmp_path, monkeypatch):
    path = tmp_path / 'batches.parquet'
    pq.write_table(pa.table({'id': range(200000), 'text': ['payload'] * 200000}),
                   path, compression='NONE', row_group_size=20000)
    real_file = pq.ParquetFile
    batches = []

    class BatchOnlyFile:
        def __init__(self, *args, **kwargs):
            self.file = real_file(*args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def __getattr__(self, name):
            return getattr(self.file, name)

        def read(self, *args, **kwargs):
            pytest.fail('whole-table read in Parquet path')

        def iter_batches(self, **kwargs):
            for batch in self.file.iter_batches(**kwargs):
                batches.append(batch.num_rows)
                yield batch

    monkeypatch.setattr(pq, 'ParquetFile', BatchOnlyFile)
    result = pack_parquet(str(path))
    assert result is not None and result.replaced
    assert max(batches) <= 65536 and len(batches) >= 12


@pytest.mark.parametrize('store_schema', [False, True])
def test_footer_metadata_and_optional_arrow_schema(tmp_path, store_schema):
    path = tmp_path / 'footer.parquet'
    table = pa.table({'n': [3, None, 1]})
    with pq.ParquetWriter(path, table.schema, compression='NONE',
                          store_schema=store_schema) as writer:
        writer.write_table(table)
        writer.add_key_value_metadata({b'footer-only': b'\xff\0binary'})
    with pq.ParquetFile(path) as original:
        expected = original.read()
        metadata = original.metadata.metadata
    assert pack_parquet(str(path), keep_if_larger=False).replaced
    with pq.ParquetFile(path) as output:
        assert output.read().equals(expected, check_metadata=True)
        actual = dict(output.metadata.metadata)
        if not store_schema:
            actual.pop(b'ARROW:schema')
        assert actual == metadata


@pytest.mark.parametrize('fault', ['zero_sign', 'nan_payload'])
@pytest.mark.parametrize('width', [16, 32, 64])
def test_float_bit_changes_are_rejected(tmp_path, monkeypatch, fault, width):
    import struct
    path = tmp_path / 'bits.parquet'
    float_type, fmt, negative_zero, nan_bits = {
        16: (pa.float16(), '<3H', 0x8000, 0x7e01),
        32: (pa.float32(), '<3I', 0x80000000, 0x7fc00001),
        64: (pa.float64(), '<3Q', 0x8000000000000000, 0x7ff8000000000001),
    }[width]

    def bit_table(bits):
        data = pa.py_buffer(struct.pack(fmt, *bits))
        return pa.table({'v': pa.Array.from_buffers(float_type, 3, [None, data])})

    table = bit_table([0, negative_zero, nan_bits])
    pq.write_table(table, path, compression='NONE')
    before = path.read_bytes()
    real_writer = pq.ParquetWriter

    class BitChangingWriter:
        def __init__(self, output, *args, **kwargs):
            self.output = output
            self.writer = real_writer(output, *args, **kwargs)

        def __enter__(self):
            return self

        def __getattr__(self, key):
            return getattr(self.writer, key)

        def __exit__(self, *args):
            self.writer.close()
            bits = ([0, 0, nan_bits] if fault == 'zero_sign' else
                    [0, negative_zero, nan_bits + 1])
            pq.write_table(bit_table(bits), self.output)

    monkeypatch.setattr(pq, 'ParquetWriter', BitChangingWriter)
    assert pack_parquet(str(path), keep_if_larger=False) is None
    assert path.read_bytes() == before
