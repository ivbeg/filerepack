"""Content-preservation regressions using real archive writers."""

import gzip
import bz2
import io
import lzma
import os
import shutil
import subprocess
import tarfile
import zipfile
from unittest.mock import patch

import pytest

from filerepack import FileRepacker, RepackOptions
from filerepack.repack import _run_command


@pytest.fixture
def archive_tools():
    if not (shutil.which('7zz') or shutil.which('7z')):
        pytest.skip('7zz/7z required for archive integration')


@pytest.mark.parametrize('suffix', ['zip', 'docx'])
def test_zip_preserves_complete_members(tmp_path, archive_tools, suffix):
    if suffix == 'docx' and not shutil.which('zip'):
        pytest.skip('Info-ZIP required')
    path = tmp_path / ('members.' + suffix)
    entries = {
        '.hidden': b'private' * 1000,
        '.hidden-dir/data.txt': b'hidden' * 1000,
        'empty/': b'',
        'space name.txt': b'spaces' * 1000,
        'unicode-\u043f\u0440\u0438\u0432\u0435\u0442.txt': b'unicode' * 1000,
        '-sdel': b'option-like' * 1000,
        '@list.txt': b'list-like' * 1000,
        'literal*.txt': b'wildcard' * 1000,
    }
    if os.name == 'nt':
        entries.pop('literal*.txt')  # Windows cannot represent '*' as an extracted filename.
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    original_size = path.stat().st_size
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == list(entries)
        assert {name: archive.read(name) for name in archive.namelist()} == entries
    assert path.stat().st_size < original_size


@pytest.mark.parametrize('deep', [False, True])
def test_compressed_tar_retains_one_payload(tmp_path, archive_tools, deep):
    path = tmp_path / 'bundle.tar.gz'
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        for name in ['.hidden', 'nested/document.txt']:
            data = b'important content' * 2000
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        member = tarfile.TarInfo('empty')
        member.type = tarfile.DIRTYPE
        archive.addfile(member)
    path.write_bytes(gzip.compress(payload.getvalue(), compresslevel=0))
    original_size = path.stat().st_size
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=deep))
    with tarfile.open(path, 'r:gz') as archive:
        assert archive.getnames() == ['.hidden', 'nested/document.txt', 'empty']
        for member in archive:
            if member.isfile():
                assert archive.extractfile(member).read() == b'important content' * 2000
    assert path.stat().st_size < original_size


@pytest.mark.parametrize('names', [('same', 'same'), ('Case', 'case')])
def test_ambiguous_zip_members_are_not_rewritten(tmp_path, archive_tools, names, caplog):
    path = tmp_path / 'ambiguous.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        for name in names:
            if name in archive.namelist():
                with pytest.warns(UserWarning, match='Duplicate name'):
                    archive.writestr(name, b'preserve me' * 1000)
            else:
                archive.writestr(name, b'preserve me' * 1000)
    original = path.read_bytes()
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    assert path.read_bytes() == original
    assert 'ambiguous' in caplog.text.lower()


def test_zip_retains_metadata_and_original_names(tmp_path, archive_tools):
    path = tmp_path / 'metadata.zip'
    info = zipfile.ZipInfo('./nested/data.txt', (2022, 3, 4, 5, 6, 8))
    info.external_attr = (0o100640 << 16) | 0x20
    info.internal_attr = 1
    info.comment = b'member comment'
    info.extra = b'\x75\x78\x05\x00\x01\x01\x01\x01\x01'  # Unix UID/GID
    data = b'content' * 3000
    with zipfile.ZipFile(path, 'w') as archive:
        archive.comment = b'archive comment'
        archive.writestr(info, data)
    before = path.stat().st_size
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    assert path.stat().st_size < before
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == [info.filename]
        assert archive.comment == b'archive comment'
        actual = archive.infolist()[0]
        for attribute in ['date_time', 'external_attr', 'internal_attr',
                          'create_system', 'comment', 'extra']:
            assert getattr(actual, attribute) == getattr(info, attribute)
        assert archive.read(actual) == data


def test_7z_preserves_members_and_contents(tmp_path, archive_tools):
    tool = shutil.which('7zz') or shutil.which('7z')
    source = tmp_path / 'source'
    source.mkdir()
    (source / '.hidden').write_bytes(b'important' * 2000)
    (source / '-sdel').write_bytes(b'literal option' * 1000)
    (source / 'empty').mkdir()
    path = tmp_path / 'members.7z'
    subprocess.run([tool, 'a', '-mx0', str(path), '--', './.hidden', './-sdel', './empty'],
                   cwd=source, capture_output=True, check=True)
    before = path.stat().st_size
    FileRepacker().repack(str(path), options=RepackOptions(deep_walking=False))
    assert path.stat().st_size < before
    output = tmp_path / 'verified'
    subprocess.run([tool, 'x', '-y', f'-o{output}', str(path)], capture_output=True, check=True)
    assert {member.name for member in output.iterdir()} == {'.hidden', '-sdel', 'empty'}
    assert (output / 'empty').is_dir()
    for name in ['.hidden', '-sdel']:
        assert (output / name).read_bytes() == (source / name).read_bytes()


def _tar_bytes():
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w', format=tarfile.PAX_FORMAT) as archive:
        root = tarfile.TarInfo('.')
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        empty = tarfile.TarInfo('./empty')
        empty.type = tarfile.DIRTYPE
        archive.addfile(empty)
        info = tarfile.TarInfo('./nested/.hidden.txt')
        info.size = 10000
        info.mode = 0o640
        info.uid, info.gid = 123, 456
        info.uname, info.gname = 'owner', 'group'
        info.mtime = 1234567890.25
        info.pax_headers = {'comment': 'retain this'}
        archive.addfile(info, io.BytesIO(b'important!' * 1000))
    return payload.getvalue()


_TOOLS = {'zst': 'zstd', 'br': 'brotli', 'lz4': 'lz4', 'lz': 'lzip',
          'lzo': 'lzop', 'z': 'compress'}


def _encode_payload(data, codec, tmp_path):
    if codec == 'gz':
        return gzip.compress(data, compresslevel=0)
    if codec == 'bz2':
        return bz2.compress(data, compresslevel=1)
    if codec in ('xz', 'lzma'):
        fmt = lzma.FORMAT_XZ if codec == 'xz' else lzma.FORMAT_ALONE
        return lzma.compress(data, format=fmt, preset=0)
    tool = shutil.which(_TOOLS[codec])
    if not tool:
        pytest.skip(f'{_TOOLS[codec]} required for {codec} integration')
    payload = tmp_path / 'original.tar'
    payload.write_bytes(data)
    return subprocess.run([tool, '-c', str(payload)], capture_output=True, check=True).stdout


def _decode_payload(path, codec):
    if codec == 'gz':
        return gzip.decompress(path.read_bytes())
    if codec == 'bz2':
        return bz2.decompress(path.read_bytes())
    if codec in ('xz', 'lzma'):
        return lzma.decompress(path.read_bytes())
    with path.open('rb') as source:
        return subprocess.run([shutil.which(_TOOLS[codec]), '-d', '-c'], stdin=source,
                              capture_output=True, check=True).stdout


@pytest.mark.parametrize('deep', [False, True])
@pytest.mark.parametrize('suffix,codec', [
    ('tar.gz', 'gz'), ('tgz', 'gz'), ('tar.bz2', 'bz2'), ('tbz2', 'bz2'),
    ('tar.xz', 'xz'), ('txz', 'xz'), ('tar.lzma', 'lzma'), ('tar.zst', 'zst'),
    ('tzst', 'zst'), ('tar.br', 'br'), ('tar.lz4', 'lz4'), ('tar.lz', 'lz'),
    ('tlz', 'lz'), ('tar.lzo', 'lzo'), ('tzo', 'lzo'), ('tar.Z', 'z'), ('taz', 'z'),
    ('crate', 'gz'), ('unitypackage', 'gz'),
])
def test_tar_wrappers_preserve_structure_and_metadata(tmp_path, archive_tools, suffix, codec, deep):
    path = tmp_path / ('bundle.' + suffix)
    path.write_bytes(_encode_payload(_tar_bytes(), codec, tmp_path))
    output = tmp_path / ('result.' + suffix)
    summary = FileRepacker().repack(str(path), outfile=str(output), options=RepackOptions(
        deep_walking=deep, keep_if_larger=False, max_extract_ratio=0,
    ))
    assert output.exists()  # Prove the new writer ran rather than silently skipping.
    assert summary.total_outsize == output.stat().st_size
    with tarfile.open(fileobj=io.BytesIO(_decode_payload(output, codec))) as archive:
        assert archive.getnames() == ['.', './empty', './nested/.hidden.txt']
        info = archive.getmember('./nested/.hidden.txt')
        assert (info.mode, info.uid, info.gid, info.uname, info.gname, info.mtime) == (
            0o640, 123, 456, 'owner', 'group', 1234567890.25,
        )
        assert info.pax_headers['comment'] == 'retain this'
        assert archive.extractfile(info).read() == b'important!' * 1000


@pytest.mark.parametrize('problem', ['missing', 'extra', 'changed', 'failed'])
def test_bad_writer_never_publishes(tmp_path, archive_tools, problem, caplog):
    path = tmp_path / 'input.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('.hidden', b'private' * 1000)
        archive.writestr('visible', b'visible' * 1000)
    original = path.read_bytes()
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def broken_writer(cmd, **kwargs):
        if 'a' not in cmd:
            return _run_command(cmd, **kwargs)
        candidate = cmd[cmd.index('a') + 1]
        if problem == 'failed':
            return None
        with zipfile.ZipFile(candidate, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            if problem != 'missing':
                archive.writestr('.hidden', b'private' * 1000)
            archive.writestr('visible', b'wrong' if problem == 'changed' else b'visible' * 1000)
            if problem == 'extra':
                archive.writestr('unexpected', b'extra')
        return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')

    with patch('filerepack.candidates.TEMP_PATH', str(scratch)):
        with patch('filerepack.archives._run_command', side_effect=broken_writer):
            FileRepacker(temppath=str(scratch)).repack(
                str(path), options=RepackOptions(deep_walking=False),
            )
    assert path.read_bytes() == original
    assert not list(scratch.iterdir())
    if problem != 'failed':
        assert 'candidate rejected' in caplog.text


def test_unreported_nested_change_is_rejected(tmp_path, archive_tools, caplog):
    path = tmp_path / 'input.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('data.txt', b'important' * 1000)
    original = path.read_bytes()

    def unreported_change(root, options, summary, **kwargs):
        with open(os.path.join(root, 'data.txt'), 'wb') as stream:
            stream.write(b'changed')

    with patch.object(FileRepacker, '_deep_walk', side_effect=unreported_change):
        FileRepacker().repack(str(path))
    assert path.read_bytes() == original
    assert 'unauthorized' in caplog.text


def test_dryrun_measures_preserving_candidate(tmp_path, archive_tools):
    path = tmp_path / 'input.tgz'
    path.write_bytes(gzip.compress(_tar_bytes(), compresslevel=0))
    original = path.read_bytes()
    predicted = FileRepacker().repack(str(path), options=RepackOptions(dryrun=True))
    assert path.read_bytes() == original
    actual = FileRepacker().repack(str(path))
    assert predicted.total_outsize == actual.total_outsize < len(original)


def test_link_members_skip_safely(tmp_path, archive_tools, caplog):
    path = tmp_path / 'links.tar'
    with tarfile.open(path, 'w') as archive:
        info = tarfile.TarInfo('link')
        info.type, info.linkname = tarfile.SYMTYPE, 'target'
        archive.addfile(info)
    original = path.read_bytes()
    FileRepacker().repack(str(path), options=RepackOptions(keep_if_larger=False))
    assert path.read_bytes() == original
    assert 'unsupported member type' in caplog.text


def test_authorized_nested_payload_change_preserves_other_members(tmp_path, archive_tools):
    path = tmp_path / 'nested.zip'
    data = bytes(range(256)) * 1000
    inner = gzip.compress(data, compresslevel=0)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('payload.gz', inner)
        archive.writestr('.untouched', b'important data')
    summary = FileRepacker().repack(str(path))
    assert summary.inner_count == 1
    assert summary.results[0].replaced
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist() == ['payload.gz', '.untouched']
        assert archive.read('.untouched') == b'important data'
        result = archive.read('payload.gz')
        assert len(result) < len(inner)
        assert gzip.decompress(result) == data


@pytest.mark.parametrize('failure', ['decode', 'extract', 'encode', 'corrupt', 'larger'])
def test_tar_failed_stages_keep_original_and_clean_scratch(tmp_path, archive_tools, failure):
    path = tmp_path / 'input.tar.gz'
    path.write_bytes(gzip.compress(_tar_bytes(), compresslevel=0))
    original = path.read_bytes()
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def corrupt_encoder(source, destination, codec, debug):
        with open(destination, 'wb') as stream:
            stream.write(gzip.compress(b'not a tar payload'))
        return True

    from contextlib import ExitStack
    with ExitStack() as patches:
        patches.enter_context(patch('filerepack.candidates.TEMP_PATH', str(scratch)))
        if failure == 'decode':
            patches.enter_context(patch('filerepack.archives._decode_tar_payload',
                                        return_value=False))
        elif failure == 'extract':
            patches.enter_context(patch.object(FileRepacker, '_extract_7z', return_value=False))
        elif failure == 'encode':
            patches.enter_context(patch('filerepack.archives._compress_file', return_value=False))
        elif failure == 'corrupt':
            patches.enter_context(patch('filerepack.archives._compress_file',
                                        side_effect=corrupt_encoder))
        options = RepackOptions(
            deep_walking=False, min_savings=100 if failure == 'larger' else None,
        )
        summary = FileRepacker(temppath=str(scratch)).repack(str(path), options=options)
    assert path.read_bytes() == original
    assert summary.total_outsize == len(original)
    assert not list(scratch.iterdir())


def test_mismatched_compressed_tar_alias_is_skipped(tmp_path, archive_tools, caplog):
    path = tmp_path / 'mismatched.tar.gz'
    path.write_bytes(_tar_bytes())  # Suffix promises gzip but content is plain tar.
    original = path.read_bytes()
    FileRepacker().repack(str(path))
    assert path.read_bytes() == original
    assert 'preservation skipped' in caplog.text


def test_real_rubygem_is_plain_tar_and_keeps_checksummed_payloads(tmp_path, archive_tools):
    gem = shutil.which('gem')
    if not gem:
        pytest.skip('RubyGems required for actual .gem format fixture')
    (tmp_path / 'data.txt').write_text('important content\n' * 1000)
    spec = tmp_path / 'preservation.gemspec'
    spec.write_text("""Gem::Specification.new do |s|
  s.name = 'preservation-fixture'
  s.version = '0.0.1'
  s.summary = 'Archive preservation fixture'
  s.authors = ['Fixture']
  s.files = ['data.txt']
  s.license = 'BSD-3-Clause'
end
""")
    subprocess.run([gem, 'build', str(spec)], cwd=tmp_path,
                   capture_output=True, check=True, timeout=60)
    path = tmp_path / 'preservation-fixture-0.0.1.gem'
    with tarfile.open(path, 'r:') as archive:
        original = {member.name: archive.extractfile(member).read() for member in archive}
    output = tmp_path / 'repacked.gem'
    FileRepacker().repack(str(path), outfile=str(output), options=RepackOptions(
        deep_walking=True, keep_if_larger=False,
    ))
    assert output.exists()
    with tarfile.open(output, 'r:') as archive:
        actual = {member.name: archive.extractfile(member).read() for member in archive}
    assert actual == original
    assert {'metadata.gz', 'data.tar.gz', 'checksums.yaml.gz'} <= set(actual)


def test_prepended_zip_wrapper_is_not_stripped(tmp_path, archive_tools, caplog):
    path = tmp_path / 'wrapped.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('file', b'important' * 1000)
    path.write_bytes(b'wrapper metadata' + path.read_bytes())
    original = path.read_bytes()
    FileRepacker().repack(str(path))
    assert path.read_bytes() == original
    assert 'prepended ZIP wrapper' in caplog.text


def test_tool_archive_comment_is_not_discarded(tmp_path, archive_tools, caplog):
    path = tmp_path / 'comment.rar'
    path.write_bytes(b'placeholder input')
    original = path.read_bytes()
    listing = ('Type = Rar5\nComment = important archive metadata\n\n----------\n'
               'Path = file\nSize = 1\nCRC = 00000000\nAttributes = A\n')
    with patch('filerepack.archives._run_command', return_value=subprocess.CompletedProcess(
        [], 0, stdout=listing, stderr='',
    )):
        FileRepacker().repack(str(path))
    assert path.read_bytes() == original
    assert 'wrapper/comment metadata' in caplog.text
