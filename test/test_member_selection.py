"""Archive selection preserves decoded payloads and independent depth policy."""

import io
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.selection import excluded_member


@pytest.mark.parametrize('pattern,name,excluded', [
    ('*.json', 'a.json', True), ('*.json', 'dir/a.json', False),
    ('**/*.json', 'a.json', True), ('**/*.json', 'dir/a.json', True),
    ('assets/', 'assets/a/b.json', True), ('assets/**', 'other/assets/x', False),
    ('?.json', 'a.json', True), ('?.json', 'ab.json', False),
    ('A.json', 'a.json', False), ('**', '.hidden/файл.json', True),
])
def test_posix_member_glob_contract(pattern, name, excluded):
    assert excluded_member(name, {'exclude_members': [pattern]}) is excluded


def _zip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def test_excluded_members_retain_bytes_in_root_and_nested_archives(tmp_path):
    excluded = b' { "preserved": 1 } ' * 1
    included = b' { "optimized": 2 } '
    nested = _zip({'assets/keep.json': excluded, 'change.json': included})
    source = tmp_path / 'root.zip'
    source.write_bytes(_zip({'assets/keep.json': excluded, 'change.json': included,
                             'nested.zip': nested}))
    summary = FileRepacker().repack(str(source), options=RepackOptions(
        exclude_members=['assets/**'],
    ))
    with zipfile.ZipFile(source) as reader:
        assert reader.read('assets/keep.json') == excluded
        assert reader.read('change.json') == b'{"optimized":2}'
        with zipfile.ZipFile(io.BytesIO(reader.read('nested.zip'))) as child:
            assert child.read('assets/keep.json') == excluded
            assert child.read('change.json') == b'{"optimized":2}'
    skipped = [member for member in summary.member_outcomes if member.status == 'skipped']
    assert {member.member for member in skipped} == {
        'assets/keep.json', 'nested.zip!/assets/keep.json',
    }
    assert all(member.source.startswith(str(source) + '!/') for member in skipped)
    assert all('filerepack-work-' not in member.source for member in skipped)


def test_depth_limit_keeps_nested_payloads_while_root_can_shrink(tmp_path):
    original = b' { "child": 1 } '
    source = tmp_path / 'root.zip'
    source.write_bytes(_zip({'nested.zip': _zip({'child.json': original}),
                             'root.json': b' { "root": 2 } '}))
    summary = FileRepacker().repack(str(source), options=RepackOptions(max_depth=1))
    with zipfile.ZipFile(source) as reader:
        assert reader.read('root.json') == b'{"root":2}'
        with zipfile.ZipFile(io.BytesIO(reader.read('nested.zip'))) as child:
            assert child.read('child.json') == original
    assert any(member.member == 'nested.zip!/child.json' and member.status == 'skipped'
               for member in summary.member_outcomes)


def test_cli_selection_and_explicit_denial_preserve_source(tmp_path):
    source = tmp_path / 'a.json'
    original = b' { "kept": 1 } '
    source.write_bytes(original)
    result = CliRunner().invoke(app, ['repack', str(source), '--allow-category', 'document',
                                    '--skip-category', 'document', '--json'])
    assert result.exit_code == 0, result.output
    assert source.read_bytes() == original


@pytest.mark.parametrize('options', [
    {'exclude_members': ['']}, {'allow_categories': ['archive']}, {'max_depth': -1},
])
def test_invalid_selection_is_rejected_before_writes(options):
    with pytest.raises(ValueError):
        RepackOptions(**options)
