"""Offline integrity, comparison and accounting regressions for the research harness."""

import hashlib
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import GitHub, download_samples, extension, git_blob_sha  # noqa: E402
from collect import inventory_statistics, select_samples  # noqa: E402
from run import execute_sample, snapshot_runtime, summarize  # noqa: E402
from verify import Unavailable, compare, json_tokens  # noqa: E402
from inspect_inputs import inspect  # noqa: E402


def row(blob='a', size=100, repo='a/a', kind='json', path='sample.json'):
    return {'repository': repo, 'path': path, 'blob_sha': blob, 'size': size,
            'format': kind, 'size_bucket': 'tiny', 'commit_sha': '0' * 40}


@pytest.mark.parametrize('name,kind', [('image.JPEG', 'jpg'), ('file.tar.gz', 'tar.gz'),
                                      ('.config.json', 'json'), ('.gitignore', ''),
                                      ('README', '')])
def test_extension(name, kind):
    assert extension(name) == kind


def test_unique_content_statistics_keep_occurrences():
    result = inventory_statistics([row(), row(repo='b/b'), row(blob='b', size=50)])[0]
    assert result['files'] == 3
    assert result['repositories'] == 2
    assert result['bytes'] == 250
    assert result['unique_blob_bytes'] == 150


def test_sampling_is_order_independent_and_deduplicates():
    rows = [row('a'), row('a', repo='b/b'), row('b', repo='b/b'), row('c', size=1000)]
    config = {'formats': ['json'], 'max_file_bytes': 500, 'seed': 's', 'per_format': 10}
    assert select_samples(rows, config) == select_samples(list(reversed(rows)), config)
    assert {x['blob_sha'] for x in select_samples(rows, config)} == {'a', 'b'}


def test_truncated_tree_is_fetched_by_subtree(tmp_path, monkeypatch):
    github = GitHub(tmp_path)
    responses = {
        'repos/a/a/git/trees/root?recursive=1': {'truncated': True, 'tree': []},
        'repos/a/a/git/trees/root': {'tree': [
            {'path': 'dir', 'type': 'tree', 'sha': 'child'}]},
        'repos/a/a/git/trees/child': {'tree': [
            {'path': 'x.json', 'type': 'blob', 'sha': 'blob'}]},
    }
    monkeypatch.setattr(github, 'get', responses.__getitem__)
    assert github.tree('a/a', 'root')[-1]['path'] == 'dir/x.json'


def test_download_rejects_wrong_frozen_blob(tmp_path, monkeypatch):
    import collect
    monkeypatch.setattr(collect, 'request_bytes', lambda *args: b'changed')
    config = {'max_file_bytes': 100, 'max_download_bytes': 100}
    samples = download_samples([row(size=7)], config, tmp_path)
    assert samples[0]['download_status'] == 'download_failed'
    assert not (tmp_path / 'inputs' / 'a.json').exists()


def test_lfs_pointer_is_not_benchmarked(tmp_path, monkeypatch):
    import collect
    data = b'version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1000\n'
    monkeypatch.setattr(collect, 'request_bytes', lambda *args: data)
    config = {'max_file_bytes': 1000, 'max_download_bytes': 1000}
    samples = download_samples([row(git_blob_sha(data), len(data))], config, tmp_path)
    assert samples[0]['download_status'] == 'lfs_pointer'
    assert not list((tmp_path / 'inputs').glob('*')) if (tmp_path / 'inputs').exists() else True


def test_json_keeps_numeric_spelling_duplicates_strings_and_bom():
    original = b'{ "n": 1.000, "n": 2e+3, "s": "a b" }'
    assert json_tokens(original) == json_tokens(b'{"n":1.000,"n":2e+3,"s":"a b"}')
    assert json_tokens(original) != json_tokens(b'{"n":1,"n":2e+3,"s":"a b"}')
    assert json_tokens(original) != json_tokens(b'{"n":1.000,"n":2e+3,"s":"ab"}')
    assert json_tokens(original) != json_tokens(b'\xef\xbb\xbf' + original)
    with pytest.raises(ValueError):
        json_tokens(b'{"n":NaN}')


def archive(path, payloads, compression=zipfile.ZIP_STORED):
    with zipfile.ZipFile(path, 'w', compression=compression) as out:
        for name, data in payloads:
            out.writestr(name, data)


def test_zip_rejects_dropped_member_and_deep_checks_payload(tmp_path):
    before, after = tmp_path / 'before.zip', tmp_path / 'after.zip'
    archive(before, [('x.json', b'{ "n": 1.0 }'), ('empty/', b'')])
    archive(after, [('x.json', b'{"n":1.0}')], zipfile.ZIP_DEFLATED)
    with pytest.raises(ValueError, match='member count'):
        compare(before, after, 'zip', deep=True)
    archive(after, [('x.json', b'{"n":1.0}'), ('empty/', b'')], zipfile.ZIP_DEFLATED)
    assert compare(before, after, 'zip', deep=True) == 'zip_members_order_metadata_recursive'
    with pytest.raises(ValueError, match='Shallow ZIP'):
        compare(before, after, 'zip')
    archive(after, [('x.json', b'{"n":2.0}'), ('empty/', b'')], zipfile.ZIP_DEFLATED)
    with pytest.raises(ValueError, match='JSON exact'):
        compare(before, after, 'zip', deep=True)


def test_raster_compares_pixels_and_metadata(tmp_path):
    from PIL import Image, PngImagePlugin
    before, after = tmp_path / 'before.png', tmp_path / 'after.png'
    image = Image.new('RGBA', (3, 3), (1, 2, 3, 4))
    info = PngImagePlugin.PngInfo()
    info.add_text('Author', 'original')
    image.save(before, pnginfo=info)
    image.save(after)
    with pytest.raises(ValueError, match='metadata'):
        compare(before, after, 'png')
    Image.new('RGBA', (3, 3), (1, 2, 4, 4)).save(after, pnginfo=info)
    with pytest.raises(ValueError, match='raster'):
        compare(before, after, 'png')


def test_unknown_changed_format_cannot_claim_preservation(tmp_path):
    before, after = tmp_path / 'before.bin', tmp_path / 'after.bin'
    before.write_bytes(b'original')
    after.write_bytes(b'changed')
    with pytest.raises(Unavailable):
        compare(before, after, 'bin')


def test_zero_and_failed_cases_remain_in_savings_denominator():
    results = [dict(row(size=100), profile='preserve', status='verified_shrink',
                    verified_saved_bytes=50),
               dict(row(size=900), profile='preserve', status='unchanged',
                    verified_saved_bytes=0),
               dict(row(size=1000), profile='preserve', status='preservation_failed',
                    verified_saved_bytes=0)]
    summary = summarize(results)[0]
    assert summary['weighted_savings_pct'] == 2.5
    assert summary['preservation_failures'] == 1


def test_worker_preserves_input_and_runs_snapshot(tmp_path):
    data = b'{ "value": [ 1, 2, 3 ] }\n'
    path = tmp_path / 'inputs' / 'sample.json'
    path.parent.mkdir()
    path.write_bytes(data)
    sample = dict(row(git_blob_sha(data), len(data)), download_status='downloaded',
                  local_path='inputs/sample.json', sha256=hashlib.sha256(data).hexdigest())
    config = {'decoded_byte_limit': 64 * 1024**2, 'timeout_seconds': 10}
    snapshot_runtime(tmp_path)
    result = execute_sample(sample, 'preserve', config, tmp_path)
    assert result['status'] == 'verified_shrink'
    assert result['source_unchanged']
    assert path.read_bytes() == data
    assert result['verified_saved_bytes'] > 0
    assert execute_sample(sample, 'preserve', config, tmp_path)['output_sha256'] == (
        result['output_sha256']
    )
    path.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='input bytes'):
        execute_sample(sample, 'preserve', config, tmp_path)


def test_worker_requests_cli_size_policy_and_detects_growth(tmp_path):
    data = b'{"x":1}'
    source = tmp_path / 'input.json'
    source.write_bytes(data)
    runtime = tmp_path / 'runtime' / 'filerepack'
    runtime.mkdir(parents=True)
    # Deliberately defective encoder: the external harness must detect final growth.
    (runtime / '__init__.py').write_text('''
from dataclasses import dataclass
from pathlib import Path
class RepackOptions:
    def __init__(self, **kw):
        assert kw['keep_if_larger'] is True
class FileRepacker:
    def __init__(self, **kw): pass
    def repack(self, source, outfile, options):
        Path(outfile).write_bytes(b'{ "x": 1 }')
        return Summary()
@dataclass
class Summary:
    total_outsize: int = 10
''')
    sample = dict(row(git_blob_sha(data), len(data)), local_path='input.json',
                  sha256=hashlib.sha256(data).hexdigest())
    config = {'decoded_byte_limit': 1000, 'timeout_seconds': 10}
    result = execute_sample(sample, 'preserve', config, tmp_path)
    assert result['status'] == 'unexpected_growth'
    assert result['verified_saved_bytes'] == 0
    assert source.read_bytes() == data


def test_worker_timeout_leaves_source_unchanged(tmp_path):
    data = b'{"x":1}'
    source = tmp_path / 'input.json'
    source.write_bytes(data)
    snapshot_runtime(tmp_path)
    sample = dict(row(git_blob_sha(data), len(data)), local_path='input.json',
                  sha256=hashlib.sha256(data).hexdigest())
    result = execute_sample(sample, 'preserve',
                            {'decoded_byte_limit': 1000, 'timeout_seconds': 0}, tmp_path)
    assert result['status'] == 'timeout'
    assert result['source_unchanged']
    assert source.read_bytes() == data


def test_parquet_allows_new_arrow_schema_but_retains_original_metadata(tmp_path):
    arrow = pytest.importorskip('pyarrow')
    parquet = pytest.importorskip('pyarrow.parquet')
    before, after = tmp_path / 'before.parquet', tmp_path / 'after.parquet'
    table = arrow.table({'value': [1, 2, 3]})
    with parquet.ParquetWriter(before, table.schema, store_schema=False) as writer:
        writer.add_key_value_metadata({'owner': 'retained'})
        writer.write_table(table)
    read = parquet.read_table(before)
    parquet.write_table(read, after)
    assert compare(before, after, 'parquet') == 'parquet_arrow_schema_metadata_values'
    parquet.write_table(read.replace_schema_metadata(None), after)
    with pytest.raises(ValueError, match='metadata'):
        compare(before, after, 'parquet')


def test_input_inspector_rejects_misleading_extension(tmp_path):
    path = tmp_path / 'fake.png'
    path.write_bytes(b'{"not":"PNG"}')
    with pytest.raises(ValueError, match='signature'):
        inspect(path, 'png', 1000)
