"""Publication faults exercise real packers and the shared filesystem boundary."""

import errno
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from filerepack.models import RepackOptions
from filerepack.repack import FileRepacker, _commit_output
from filerepack.markup import pack_json
from filerepack import xattrs


ORIGINAL = b' { "keep": 1 } '


def source_file(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(ORIGINAL)
    source.chmod(0o644)
    os.utime(source, ns=(1_600_000_000_000_000_000, 1_600_000_001_123_456_789))
    return source


@pytest.mark.parametrize('entry', ['helper', 'library', 'outfile', 'backup'])
def test_publication_retains_source_mode_and_mtime(tmp_path, entry):
    source = source_file(tmp_path)
    before = source.stat()
    output = tmp_path / 'output.json'
    if entry == 'helper':
        assert pack_json(str(source)).replaced
        target = source
    else:
        FileRepacker().repack(
            str(source), outfile=str(output) if entry == 'outfile' else None,
            options=RepackOptions(backup=entry == 'backup'),
        )
        target = output if entry == 'outfile' else source
    assert target.read_bytes() == b'{"keep":1}'
    assert stat.S_IMODE(target.stat().st_mode) == stat.S_IMODE(before.st_mode)
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    if entry == 'backup':
        backup = Path(str(source) + '.bak')
        assert backup.read_bytes() == ORIGINAL
        assert stat.S_IMODE(backup.stat().st_mode) == stat.S_IMODE(before.st_mode)
        assert backup.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize('entry', ['helper', 'library'])
def test_cross_device_scratch_never_replaces_directly(tmp_path, monkeypatch, entry):
    source = source_file(tmp_path)
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    replace = os.replace
    replacements = []

    def same_device_only(candidate, destination):
        replacements.append((Path(candidate), Path(destination)))
        if Path(candidate).parent != Path(destination).parent:
            raise OSError(errno.EXDEV, 'simulated cross-device rename')
        return replace(candidate, destination)

    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))
    monkeypatch.setattr(os, 'replace', same_device_only)
    if entry == 'helper':
        result = pack_json(str(source))
        assert result is not None and result.replaced
    else:
        FileRepacker(temppath=str(scratch)).repack(str(source))
    assert source.read_bytes() == b'{"keep":1}'
    assert replacements and all(a.parent == b.parent for a, b in replacements)
    assert list(scratch.iterdir()) == []
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('entry', ['helper', 'library'])
def test_real_cross_device_scratch_when_available(tmp_path, monkeypatch, entry):
    if not os.path.isdir('/dev/shm') or os.stat('/dev/shm').st_dev == tmp_path.stat().st_dev:
        pytest.skip('A writable second filesystem is unavailable')
    source = source_file(tmp_path)
    with tempfile.TemporaryDirectory(prefix='filerepack-test-', dir='/dev/shm') as scratch:
        monkeypatch.setattr('filerepack.candidates.TEMP_PATH', scratch)
        if entry == 'helper':
            assert pack_json(str(source)).replaced
        else:
            FileRepacker(temppath=scratch).repack(str(source))
        assert source.read_bytes() == b'{"keep":1}'
        assert list(Path(scratch).iterdir()) == []


@pytest.mark.parametrize('mutation', ['contents', 'inode', 'mode', 'mtime', 'hardlink'])
@pytest.mark.parametrize('distinct', [False, True])
def test_changed_source_is_a_conflict(tmp_path, monkeypatch, mutation, distinct):
    from filerepack.repack import _dispatch_packer

    source = source_file(tmp_path)
    output = tmp_path / 'output.json'
    output.write_bytes(b'old output')
    before = source.stat()

    def concurrent_writer(*args, **kwargs):
        result = _dispatch_packer(*args, **kwargs)
        if mutation == 'contents':
            source.write_bytes(b'concurrent bytes')
            os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        elif mutation == 'inode':
            new = tmp_path / 'replacement'
            new.write_bytes(ORIGINAL)
            os.replace(new, source)
        elif mutation == 'mode':
            source.chmod(0o444 if os.name == 'nt' else 0o600)
        elif mutation == 'mtime':
            os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        else:
            os.link(source, tmp_path / 'new-link')
        return result

    monkeypatch.setattr('filerepack.repack._dispatch_packer', concurrent_writer)
    with pytest.raises(OSError, match='changed'):
        FileRepacker().repack(
            str(source), outfile=str(output) if distinct else None,
            options=RepackOptions(overwrite=True),
        )
    assert source.read_bytes() == (b'concurrent bytes' if mutation == 'contents' else ORIGINAL)
    assert output.read_bytes() == b'old output'
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('entry', ['helper', 'library'])
@pytest.mark.parametrize('link_type', ['symlink', 'hardlink'])
def test_inplace_linked_sources_are_refused(tmp_path, entry, link_type):
    source = source_file(tmp_path)
    alias = tmp_path / 'alias.json'
    try:
        if link_type == 'symlink':
            alias.symlink_to(source)
            selected = alias
        else:
            os.link(source, alias)
            selected = source
    except OSError:
        pytest.skip('Filesystem links unavailable')
    with pytest.raises(ValueError, match='link'):
        (pack_json if entry == 'helper' else FileRepacker().repack)(str(selected))
    assert source.read_bytes() == alias.read_bytes() == ORIGINAL
    if link_type == 'symlink':
        assert alias.is_symlink()
    else:
        assert source.stat().st_ino == alias.stat().st_ino


@pytest.mark.parametrize('link_type', ['symlink', 'hardlink'])
def test_linked_source_can_be_copied_to_distinct_output(tmp_path, link_type):
    source = source_file(tmp_path)
    alias = tmp_path / 'alias.json'
    if link_type == 'symlink':
        alias.symlink_to(source)
    else:
        os.link(source, alias)
    output = tmp_path / 'output.json'
    FileRepacker().repack(str(alias), outfile=str(output))
    assert source.read_bytes() == alias.read_bytes() == ORIGINAL
    assert output.read_bytes() == b'{"keep":1}'


@pytest.mark.parametrize('fault', ['verify', 'metadata', 'replace', 'copy'])
def test_failed_commit_preserves_prior_bytes_and_cleans_stage(tmp_path, monkeypatch, fault):
    source = source_file(tmp_path)
    before = source.stat()
    candidate = tmp_path / 'candidate.json'
    candidate.write_bytes(b'{"keep":1}')
    if fault == 'verify':
        monkeypatch.setattr('filerepack.candidates.verify_output', lambda *args: False)
    elif fault == 'metadata':
        monkeypatch.setattr(os, 'chmod', lambda *args, **kwargs: (_ for _ in ()).throw(
            PermissionError('metadata denied')))
    elif fault == 'replace':
        monkeypatch.setattr(os, 'replace', lambda *args: (_ for _ in ()).throw(
            PermissionError('replacement denied')))
    else:
        monkeypatch.setattr(shutil, 'copyfile', lambda a, b: Path(b).write_bytes(b'bad'))
    if fault == 'verify':
        assert _commit_output(str(candidate), str(source), len(ORIGINAL), verify='json') is None
    else:
        with pytest.raises(OSError):
            _commit_output(str(candidate), str(source), len(ORIGINAL), verify='json')
    assert source.read_bytes() == ORIGINAL
    assert stat.S_IMODE(source.stat().st_mode) == stat.S_IMODE(before.st_mode)
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    assert not candidate.exists()
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('existing', [False, True])
def test_destination_changed_during_final_staging_is_not_overwritten(tmp_path, monkeypatch,
                                                                  existing):
    source = source_file(tmp_path)
    output = tmp_path / 'output.json'
    if existing:
        output.write_bytes(b'old output')
    copyfile = shutil.copyfile

    def racing_copy(src, dst, **kwargs):
        result = copyfile(src, dst, **kwargs)
        if Path(dst).name.startswith('.filerepack-publish-') and Path(dst).parent == tmp_path:
            output.write_bytes(b'late writer')
        return result

    monkeypatch.setattr(shutil, 'copyfile', racing_copy)
    with pytest.raises(OSError):
        FileRepacker().repack(str(source), outfile=str(output),
                             options=RepackOptions(overwrite=True))
    assert source.read_bytes() == ORIGINAL
    assert output.read_bytes() == b'late writer'
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('entry', ['helper', 'options', 'dictionary'])
def test_crash_durability_request_is_refused_before_writes(tmp_path, entry):
    source = source_file(tmp_path)
    output = tmp_path / 'new-dir' / 'output.json'
    with pytest.raises(ValueError, match='durability'):
        if entry == 'helper':
            pack_json(str(source), durability='crash')
        elif entry == 'options':
            RepackOptions(durability='crash')
        else:
            FileRepacker().repack(str(source), outfile=str(output),
                                 options={'durability': 'crash', 'backup': True})
    assert source.read_bytes() == ORIGINAL
    assert not output.parent.exists()
    assert not Path(str(source) + '.bak').exists()


@pytest.mark.parametrize('distinct', [False, True])
def test_supported_xattrs_survive_publication(tmp_path, distinct):
    if sys.platform != 'darwin' and not hasattr(os, 'setxattr'):
        pytest.skip('Python xattr APIs unavailable')
    source = source_file(tmp_path)
    name = 'user.filerepack-test'
    try:
        if sys.platform == 'darwin':
            subprocess.run(['/usr/bin/xattr', '-w', name, 'preserve me', str(source)], check=True)
        else:
            getattr(os, 'setxattr')(source, name, b'preserve me')
    except OSError:
        pytest.skip('Filesystem xattrs unavailable')
    output = tmp_path / 'output.json' if distinct else source
    FileRepacker().repack(str(source), outfile=str(output) if distinct else None)
    assert output.read_bytes() == b'{"keep":1}'
    if sys.platform == 'darwin':
        actual = subprocess.check_output(['/usr/bin/xattr', '-p', name, str(output)]).rstrip(b'\n')
    else:
        actual = getattr(os, 'getxattr')(output, name)
    assert actual == b'preserve me'


def test_helper_detects_source_change_after_reading(tmp_path, monkeypatch):
    from filerepack.repack import _make_temp

    source = source_file(tmp_path)
    before = source.stat()

    def concurrent_source_write(suffix):
        source.write_bytes(b'new user bytes')
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        return _make_temp(suffix)

    monkeypatch.setattr('filerepack.candidates.make_temp', concurrent_source_write)
    with pytest.raises(OSError, match='changed'):
        pack_json(str(source))
    assert source.read_bytes() == b'new user bytes'
    assert not list(tmp_path.glob('.filerepack-publish-*'))


def test_candidate_changed_during_verification_is_refused(tmp_path, monkeypatch):
    source = source_file(tmp_path)
    candidate = tmp_path / 'candidate.json'
    candidate.write_bytes(b'{"keep":1}')

    def stale_verification(path, kind):
        Path(path).write_bytes(b'{"bad":2}')
        return True

    monkeypatch.setattr('filerepack.candidates.verify_output', stale_verification)
    with pytest.raises(OSError, match='changed'):
        _commit_output(str(candidate), str(source), len(ORIGINAL), verify='json')
    assert source.read_bytes() == ORIGINAL
    assert not candidate.exists()
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('entry', ['helper', 'library'])
def test_metadata_failure_is_reported_and_keeps_original(tmp_path, monkeypatch, caplog, entry):
    source = source_file(tmp_path)

    def deny_metadata(*args):
        raise PermissionError('metadata denied')

    monkeypatch.setattr('filerepack.transactions.FileMetadata.apply', deny_metadata)
    if entry == 'helper':
        assert pack_json(str(source)) is None
    else:
        result = FileRepacker().repack(str(source))
        assert not result.results
    assert 'Publication refused' in caplog.text and 'metadata denied' in caplog.text
    assert source.read_bytes() == ORIGINAL
    assert not list(tmp_path.glob('.filerepack-publish-*'))


def test_xattr_write_failure_prevents_publication(tmp_path, monkeypatch):
    if not xattrs.supported():
        pytest.skip('Native extended attributes unavailable')
    source = source_file(tmp_path)
    name = 'user.filerepack-test'
    xattrs.write(str(source), name, b'value')
    candidate = tmp_path / 'candidate.json'
    candidate.write_bytes(b'{"keep":1}')

    def deny_attribute(*args):
        raise PermissionError('xattr denied')

    monkeypatch.setattr(xattrs, 'write', deny_attribute)
    with pytest.raises(OSError, match='xattr denied'):
        _commit_output(str(candidate), str(source), len(ORIGINAL), verify='json')
    assert source.read_bytes() == ORIGINAL
    assert xattrs.read(str(source))[name] == b'value'
    assert not candidate.exists()


@pytest.mark.parametrize('attribute', ['user.filerepack-binary', 'com.apple.ResourceFork'])
def test_native_binary_attributes_and_resource_fork_survive(tmp_path, attribute):
    if not xattrs.supported() or (
        attribute == 'com.apple.ResourceFork' and sys.platform != 'darwin'
    ):
        pytest.skip('Native attribute unavailable on this platform')
    source = source_file(tmp_path)
    value = b'\x00\xffbinary\x00\n' * 1024
    try:
        xattrs.write(str(source), attribute, value)
    except OSError:
        pytest.skip('Filesystem attribute unavailable')
    result = pack_json(str(source))
    assert result is not None and result.replaced
    assert xattrs.read(str(source))[attribute] == value


def test_linux_xattr_adapter_uses_all_names_and_values(monkeypatch):
    values = {'user.binary': b'\0\xff', 'user.empty': b''}
    monkeypatch.setattr(xattrs, '_libc', None)
    monkeypatch.setattr(os, 'listxattr', lambda path: list(values), raising=False)
    monkeypatch.setattr(os, 'getxattr', lambda path, name: values[name], raising=False)
    monkeypatch.setattr(os, 'setxattr', lambda path, name, value: values.update({name: value}),
                        raising=False)
    monkeypatch.setattr(os, 'removexattr', lambda path, name: values.pop(name), raising=False)
    assert xattrs.read('source') == values
    xattrs.write('source', 'user.new', b'new')
    xattrs.remove('source', 'user.empty')
    assert xattrs.read('source') == {'user.binary': b'\0\xff', 'user.new': b'new'}


@pytest.mark.parametrize('platform,case,accepted', [
    ('darwin', 'generated', True),
    ('darwin', 'source-same', True),
    ('darwin', 'source-different', False),
    ('darwin', 'late', False),
    ('darwin', 'other', False),
    ('darwin', 'changed', False),
    ('darwin', 'source-attribute', False),
    ('linux', 'generated', False),
    ('win32', 'generated', False),
])
def test_protected_stage_provenance_preserves_source_contract(tmp_path, monkeypatch,
                                                            platform, case, accepted):
    from types import SimpleNamespace
    from filerepack import transactions

    source = source_file(tmp_path)
    candidate, output = tmp_path / 'candidate', tmp_path / 'output'
    candidate.write_bytes(b'{"keep":1}')
    output.write_bytes(b'prior destination')
    name, label = 'com.apple.provenance', b'\x01\x02system-label'
    source_attrs = {'user.binary': b'\x00\xff', 'user.empty': b''}
    if case.startswith('source-') and case != 'source-attribute':
        source_attrs[name] = label if case == 'source-same' else b'original label'
    values = {str(source): dict(source_attrs)}
    initial = {} if case == 'late' else {name: label}
    if case == 'other':
        initial['user.other-protected'] = b'foreign'
    protected = {name, 'user.other-protected'}
    stage, removals = [], []

    def read(path):
        initial_value = initial if Path(path).name.startswith('.filerepack-publish-') else {}
        return dict(values.setdefault(str(path), dict(initial_value)))

    def write(path, attribute, value):
        if attribute not in protected and not (
            case == 'source-attribute' and attribute == 'user.binary'
        ):
            values[str(path)][attribute] = value

    def remove(path, attribute):
        removals.append(attribute)
        if attribute not in protected:
            values[str(path)].pop(attribute, None)

    def copy(src, dst):
        stage.append(dst)
        read(dst)
        if case in ('late', 'changed'):
            values[dst][name] = label if case == 'late' else b'changed label'
        return shutil.copyfile(src, dst)

    monkeypatch.setattr(transactions, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(xattrs, 'read', read)
    monkeypatch.setattr(xattrs, 'write', write)
    monkeypatch.setattr(xattrs, 'remove', remove)
    snapshot = transactions.FileSnapshot.capture(str(source))
    prior = transactions.FileSnapshot.capture(str(output))
    arguments = dict(metadata=snapshot.metadata, guards=[snapshot, prior], overwrite=True,
                     copy=copy)
    if accepted:
        transactions.publish_candidate(str(candidate), str(output), **arguments)
        assert output.read_bytes() == candidate.read_bytes()
        assert values[stage[0]] == {**source_attrs, name: label}
        assert name not in removals
        assert stat.S_IMODE(output.stat().st_mode) == snapshot.metadata.mode
        assert output.stat().st_mtime_ns == snapshot.metadata.mtime_ns
    else:
        with pytest.raises(OSError, match='metadata could not be preserved'):
            transactions.publish_candidate(str(candidate), str(output), **arguments)
        prior.require_unchanged()
    snapshot.require_unchanged()
    assert snapshot.metadata.xattrs == source_attrs
    assert read(str(source)) == source_attrs
    assert source.read_bytes() == ORIGINAL
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('entry', ['helper', 'library'])
def test_conversion_does_not_delete_a_new_source_generation(tmp_path, monkeypatch, entry):
    from filerepack.repack import pack_wmv
    from filerepack.transactions import publish_candidate

    source = tmp_path / 'movie.wmv'
    source.write_bytes(b'original' * 100)
    output = source.with_suffix('.mp4')
    payload = b'\x00\x00\x00\x18ftypmp42' + b'encoded' * 4

    def encode(ffmpeg, filepath, target, *args, **kwargs):
        Path(target).write_bytes(payload)
        return True

    def changed_after_publication(candidate, destination, **kwargs):
        publish_candidate(candidate, destination, **kwargs)
        if Path(destination) == output:
            source.write_bytes(b'new source after publication')

    monkeypatch.setattr('filerepack.media.resolve_tool', lambda name: '/fake/ffmpeg')
    monkeypatch.setattr('filerepack.media._encode_video', encode)
    monkeypatch.setattr('filerepack.media_verify.verify_media_preservation',
                        lambda *a, **k: True)
    # Isolate the post-publication race from the controlled video encoder stub.
    monkeypatch.setattr('filerepack.candidates.verify_output', lambda *a, **k: True)
    monkeypatch.setattr('filerepack.destinations.publish_candidate', changed_after_publication)
    with pytest.raises(OSError, match='changed'):
        (pack_wmv if entry == 'helper' else FileRepacker().repack)(str(source))
    assert source.read_bytes() == b'new source after publication'
    assert output.read_bytes() == payload


def test_source_changes_during_preflight_prevent_backup_and_encoding(tmp_path, monkeypatch):
    from filerepack.repack import prepare_destination_plan

    source = source_file(tmp_path)

    def changed_during_preflight(*args, **kwargs):
        plan = prepare_destination_plan(*args, **kwargs)
        source.write_bytes(b'new generation during preflight')
        return plan

    monkeypatch.setattr('filerepack.repack.prepare_destination_plan', changed_during_preflight)
    with pytest.raises(OSError, match='changed'):
        FileRepacker().repack(str(source), options=RepackOptions(backup=True))
    assert source.read_bytes() == b'new generation during preflight'
    assert not Path(str(source) + '.bak').exists()


def test_metadata_application_cannot_change_verified_candidate_bytes(tmp_path, monkeypatch):
    source = source_file(tmp_path)
    candidate = tmp_path / 'candidate.json'
    candidate.write_bytes(b'{"keep":1}')

    def bad_metadata(self, path):
        Path(path).write_bytes(b'changed by metadata')

    monkeypatch.setattr('filerepack.transactions.FileMetadata.apply', bad_metadata)
    with pytest.raises(OSError, match='changed candidate bytes'):
        _commit_output(str(candidate), str(source), len(ORIGINAL), verify='json')
    assert source.read_bytes() == ORIGINAL
    assert not candidate.exists()
    assert not list(tmp_path.glob('.filerepack-publish-*'))


def test_early_encoder_copy_failure_cleans_owned_scratch(tmp_path, monkeypatch):
    from filerepack.repack import pack_jpg

    source = tmp_path / 'image.jpg'
    source.write_bytes(b'original image')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def failed_copy(*args):
        raise OSError('early encoder copy failure')

    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))
    monkeypatch.setattr('filerepack.images.resolve_tool', lambda name: '/fake/jpegoptim')
    monkeypatch.setattr('filerepack.images.copyfile', failed_copy)
    with pytest.raises(OSError, match='early encoder copy failure'):
        pack_jpg(str(source))
    assert source.read_bytes() == b'original image'
    assert list(scratch.iterdir()) == []


def test_second_scratch_allocation_failure_cleans_first(tmp_path, monkeypatch):
    from filerepack.repack import pack_gzip
    import gzip

    source = tmp_path / 'source.gz'
    with gzip.open(source, 'wb') as stream:
        stream.write(b'original payload')
    original = source.read_bytes()
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    allocate = tempfile.mkstemp
    calls = []

    def second_allocation_fails(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise OSError('scratch allocation failure')
        return allocate(*args, **kwargs)

    monkeypatch.setattr('filerepack.candidates.TEMP_PATH', str(scratch))
    monkeypatch.setattr(tempfile, 'mkstemp', second_allocation_fails)
    with pytest.raises(OSError, match='scratch allocation failure'):
        pack_gzip(str(source))
    assert source.read_bytes() == original
    assert list(scratch.iterdir()) == []
