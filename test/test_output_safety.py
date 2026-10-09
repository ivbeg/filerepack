"""Source/destination preservation at CLI and library publication boundaries."""

import gzip
import multiprocessing
import os
import shutil
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from filerepack import FileRepacker, RepackOptions
from filerepack.__main__ import app
from filerepack.destinations import PathReservation
from filerepack.jobs import process_file_job
from filerepack.repack import pack_wmv
from filerepack.utils import create_backup, parse_jobs, parse_size


def write_input(path, kind):
    if kind == 'json':
        path.write_bytes(b' { "n": 1.234567890123456789 } \n')
    elif kind == 'gz':
        path.write_bytes(gzip.compress(b'preserved payload' * 1000, compresslevel=0))
    else:
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('payload.txt', b'preserved payload' * 1000)


@pytest.mark.parametrize('kind', ['json', 'gz', 'zip'])
def test_distinct_outfile_preserves_source(tmp_path, kind):
    if kind == 'zip' and not (shutil.which('7zz') or shutil.which('7z')):
        pytest.skip('7zz/7z required for archive rewriting')
    source = tmp_path / ('source.' + kind)
    output = tmp_path / 'out' / ('requested.' + kind)
    write_input(source, kind)
    original = source.read_bytes()
    summary = FileRepacker().repack(str(source), outfile=str(output))
    assert source.read_bytes() == original
    assert output.is_file()
    assert output.stat().st_size < len(original)
    assert summary.filepath == str(output)
    if kind == 'json':
        assert output.read_bytes() == b'{"n":1.234567890123456789}'
    elif kind == 'gz':
        assert gzip.decompress(output.read_bytes()) == gzip.decompress(original)
    else:
        with zipfile.ZipFile(output) as archive:
            assert archive.read('payload.txt') == b'preserved payload' * 1000


@pytest.mark.parametrize('data', [b'{"already":"compact"}', b'unchanged unsupported text'])
def test_no_improvement_publishes_unchanged_copy(tmp_path, data):
    source = tmp_path / ('source.json' if data.startswith(b'{') else 'source.txt')
    output = tmp_path / ('out' + source.suffix)
    source.write_bytes(data)
    summary = FileRepacker().repack(str(source), outfile=str(output))
    if source.suffix == '.txt':
        assert summary.outcome.status == 'unsupported'
        assert not output.exists() and source.read_bytes() == data
        return
    assert source.read_bytes() == output.read_bytes() == data
    assert summary.filepath == str(output)
    assert summary.total_insize == summary.total_outsize == len(data)


@pytest.mark.parametrize('options', [
    {'compression_level': 99}, {'compression_level': 0}, {'jpeg_quality': 500},
    {'jpeg_quality': 0}, {'png_quality': 'typo'}, {'pdf_profile': 'ultra'},
    {'min_savings': float('nan')}, {'min_savings': float('inf')},
    {'min_savings': -1}, {'min_savings': 101}, {'max_extract_bytes': -1},
    {'max_extract_ratio': float('inf')}, {'max_extract_ratio': -1},
    {'compression_level': None}, {'compression_level': 1.5},
    {'max_extract_bytes': 1.5}, {'overwrite': 'yes'},
])
@pytest.mark.parametrize('model', [False, True])
def test_invalid_library_options_write_nothing(tmp_path, options, model):
    source = tmp_path / 'source.json'
    output = tmp_path / 'out' / 'existing.json'
    source.write_bytes(b' { "keep": 123 } ')
    output.parent.mkdir()
    output.write_bytes(b'existing unrelated file')
    original = source.read_bytes()
    with pytest.raises(ValueError):
        if model:
            options = RepackOptions(**options)
        FileRepacker().repack(str(source), outfile=str(output), options=options)
    assert source.read_bytes() == original
    assert output.read_bytes() == b'existing unrelated file'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['out', 'source.json']


def test_cli_invalid_options_do_not_copy_or_backup_or_log(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'
    output_dir.mkdir()
    output = output_dir / source.name
    output.write_bytes(b'unrelated output')
    original = source.read_bytes()
    log = tmp_path / 'invalid.log'
    result = CliRunner().invoke(app, [
        'repack', str(source), '--output-dir', str(output_dir), '--backup',
        '--pdf-profile', 'ultra', '--log-file', str(log),
    ])
    assert result.exit_code == 1
    assert 'Unknown PDF profile' in result.output
    assert source.read_bytes() == original
    assert output.read_bytes() == b'unrelated output'
    assert not (tmp_path / 'source.json.bak').exists()
    assert not log.exists()


@pytest.mark.parametrize('api', ['library', 'cli', 'job'])
def test_existing_output_is_refused(tmp_path, api):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'
    output_dir.mkdir()
    output = output_dir / source.name
    output.write_bytes(b'unrelated output')
    original = source.read_bytes()
    if api == 'library':
        with pytest.raises(FileExistsError):
            FileRepacker().repack(str(source), outfile=str(output))
    elif api == 'cli':
        result = CliRunner().invoke(app, [
            'repack', str(source), '--output-dir', str(output_dir), '--backup',
        ])
        assert result.exit_code == 1
        assert 'exist' in result.output.lower()
    else:
        result = process_file_job({'filepath': str(source), 'output_dir': str(output_dir)})
        assert result['status'] == 'failed'
        assert 'exist' in result['error'].lower()
    assert source.read_bytes() == original
    assert output.read_bytes() == b'unrelated output'
    assert not (tmp_path / 'source.json.bak').exists()


@pytest.mark.parametrize('api', ['library', 'direct'])
def test_video_conversion_collision_before_encoder(tmp_path, monkeypatch, api):
    source = tmp_path / 'movie.wmv'
    source.write_bytes(b'source video' * 100)
    target = tmp_path / 'movie.mp4'
    target.write_bytes(b'unrelated existing movie')

    def forbidden(*args, **kwargs):
        pytest.fail('encoder ran before conversion collision was rejected')

    monkeypatch.setattr('filerepack.media.resolve_tool', lambda name: '/fake/ffmpeg')
    monkeypatch.setattr('filerepack.media._encode_video', forbidden)
    with pytest.raises(FileExistsError):
        if api == 'direct':
            pack_wmv(str(source))
        else:
            FileRepacker().repack(str(source))
    assert source.read_bytes() == b'source video' * 100
    assert target.read_bytes() == b'unrelated existing movie'


def test_rar_conversion_collision_before_extraction(tmp_path, monkeypatch):
    source = tmp_path / 'bundle.rar'
    source.write_bytes(b'Rar!\x1a\x07\x00' + b'source archive' * 100)
    target = tmp_path / 'bundle.7z'
    target.write_bytes(b'unrelated existing archive')
    monkeypatch.setattr('filerepack.repack.resolve_tool', lambda name: None)

    def forbidden(*args, **kwargs):
        pytest.fail('archive extracted before conversion collision was rejected')

    monkeypatch.setattr(FileRepacker, '_extract_rar', forbidden)
    with pytest.raises(FileExistsError):
        FileRepacker().repack(str(source))
    assert source.read_bytes().startswith(b'Rar!')
    assert target.read_bytes() == b'unrelated existing archive'


def test_existing_required_backup_is_not_overwritten(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    backup = tmp_path / 'source.json.bak'
    backup.write_bytes(b'older backup')
    assert create_backup(str(source)) is None
    assert backup.read_bytes() == b'older backup'


@pytest.mark.parametrize(('size', 'expected'), [
    ('1K', 1024), ('1M', 1024 ** 2), ('1G', 1024 ** 3), ('1T', 1024 ** 4),
    ('1.5G', int(1.5 * 1024 ** 3)), (' 2 kb ', 2048),
])
def test_size_suffixes(size, expected):
    assert parse_size(size) == expected


@pytest.mark.parametrize('value', ['-1', '-1G', 'NaN', 'Infinity'])
def test_invalid_size_is_rejected(value):
    with pytest.raises(ValueError):
        parse_size(value)


@pytest.mark.parametrize('value', ['0', '-1', 0, -2])
def test_jobs_must_be_positive(value):
    with pytest.raises(ValueError):
        parse_jobs(value)


@pytest.mark.parametrize('api', ['library', 'cli', 'job'])
def test_explicit_overwrite_only_replaces_requested_output(tmp_path, api):
    source = tmp_path / 'source.json'
    output_dir = tmp_path / 'out'
    output_dir.mkdir()
    output = output_dir / source.name
    source.write_bytes(b' { "keep": 1 } ')
    output.write_bytes(b'unrelated old output')
    original = source.read_bytes()
    if api == 'library':
        FileRepacker().repack(
            str(source), outfile=str(output), options=RepackOptions(overwrite=True),
        )
    elif api == 'cli':
        result = CliRunner().invoke(app, [
            'repack', str(source), '--output-dir', str(output_dir), '--overwrite', '--json',
        ])
        assert result.exit_code == 0, result.output
        assert '"output_file"' in result.output
    else:
        result = process_file_job({
            'filepath': str(source), 'output_dir': str(output_dir), 'overwrite': True,
        })
        assert result['status'] == 'replaced'
        assert result['output_file'] == str(output)
    assert source.read_bytes() == original
    assert output.read_bytes() == b'{"keep":1}'


@pytest.mark.parametrize('api', ['library', 'cli', 'job'])
def test_required_backup_failure_prevents_encoding(tmp_path, monkeypatch, api):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'

    def failed_backup(*args, **kwargs):
        raise OSError('Required backup unavailable')

    def forbidden(*args, **kwargs):
        pytest.fail('encoding ran after required backup failed')

    monkeypatch.setattr(PathReservation, 'publish_copy', failed_backup)
    monkeypatch.setattr('filerepack.repack._dispatch_packer', forbidden)
    if api == 'library':
        with pytest.raises(OSError, match='Required backup unavailable'):
            FileRepacker().repack(
                str(source), outfile=str(output_dir / source.name),
                options=RepackOptions(backup=True),
            )
    elif api == 'cli':
        result = CliRunner().invoke(app, [
            'repack', str(source), '--output-dir', str(output_dir), '--backup',
        ])
        assert result.exit_code == 1
        assert 'Required backup unavailable' in result.output
    else:
        result = process_file_job({
            'filepath': str(source), 'output_dir': str(output_dir), 'backup': True,
        })
        assert result['status'] == 'failed'
        assert 'Required backup unavailable' in result['error']
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not output_dir.exists()
    assert not (tmp_path / 'source.json.bak').exists()


def test_overwrite_never_authorizes_replacing_required_backup(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    backup = tmp_path / 'source.json.bak'
    backup.write_bytes(b'older backup')
    with pytest.raises(FileExistsError, match='backup already exists'):
        FileRepacker().repack(str(source), options=RepackOptions(backup=True, overwrite=True))
    assert source.read_bytes() == b' { "keep": 1 } '
    assert backup.read_bytes() == b'older backup'


def test_backup_and_output_cannot_share_one_path(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'
    with pytest.raises(FileExistsError, match='Backup conflicts'):
        FileRepacker().repack(
            str(source), outfile=str(output_dir / source.name),
            options=RepackOptions(backup=True, backup_dir=str(output_dir)),
        )
    assert not output_dir.exists()
    assert source.read_bytes() == b' { "keep": 1 } '


def test_custom_backups_get_new_names_and_backup_dir_is_only_a_selector(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    directory = tmp_path / 'backups'
    first = create_backup(str(source), str(directory))
    second = create_backup(str(source), str(directory))
    assert first != second and first is not None and second is not None
    assert Path(first).read_bytes() == Path(second).read_bytes() == source.read_bytes()
    unused = tmp_path / 'unused-backups'
    FileRepacker().repack(str(source), options=RepackOptions(backup_dir=str(unused)))
    assert not unused.exists()


@pytest.mark.parametrize('api', ['library', 'cli', 'job'])
def test_dryrun_creates_no_output_or_backup_artifacts(tmp_path, api):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'
    backup_dir = tmp_path / 'backups'
    if api == 'library':
        summary = FileRepacker().repack(
            str(source), outfile=str(output_dir / source.name),
            options=RepackOptions(dryrun=True, backup=True, backup_dir=str(backup_dir)),
        )
        assert summary.total_outsize < summary.total_insize
        assert summary.filepath == str(output_dir / source.name)
        assert all(not result.replaced for result in summary.results)
    elif api == 'cli':
        result = CliRunner().invoke(app, [
            'repack', str(source), '--output-dir', str(output_dir), '--backup',
            '--backup-dir', str(backup_dir), '--dryrun',
        ])
        assert result.exit_code == 0, result.output
    else:
        result = process_file_job({
            'filepath': str(source), 'output_dir': str(output_dir),
            'backup_dir': str(backup_dir), 'backup': True, 'dryrun': True,
        })
        assert result['status'] == 'predicted'
        assert result['final_size'] < result['original_size']
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not output_dir.exists() and not backup_dir.exists()


@pytest.mark.parametrize('alias', ['relative', 'symlink', 'hardlink', 'directory-symlink'])
def test_source_alias_outfile_is_treated_as_inplace(tmp_path, monkeypatch, alias):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    if alias == 'relative':
        monkeypatch.chdir(tmp_path)
        outfile = './source.json'
    elif alias == 'directory-symlink':
        directory = tmp_path / 'linked-dir'
        try:
            directory.symlink_to(tmp_path, target_is_directory=True)
        except OSError:
            pytest.skip('Directory symlink unavailable')
        outfile = str(directory / source.name)
    else:
        path = tmp_path / 'alias.json'
        try:
            if alias == 'symlink':
                path.symlink_to(source)
            else:
                os.link(source, path)
        except OSError:
            pytest.skip('Filesystem link unavailable')
        outfile = str(path)
    if alias == 'hardlink':
        with pytest.raises(ValueError, match='hard links'):
            FileRepacker().repack(str(source), outfile=outfile)
        assert source.read_bytes() == path.read_bytes() == b' { "keep": 1 } '
        return
    summary = FileRepacker().repack(str(source), outfile=outfile)
    assert source.read_bytes() == b'{"keep":1}'
    assert summary.filepath == str(source)


def test_late_destination_collision_preserves_both_files_and_cleans_scratch(tmp_path, monkeypatch):
    from filerepack.repack import _dispatch_packer

    source = tmp_path / 'source.json'
    output = tmp_path / 'output.json'
    source.write_bytes(b' { "keep": 1 } ')
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def encode_then_race(*args, **kwargs):
        result = _dispatch_packer(*args, **kwargs)
        output.write_bytes(b'late unrelated writer')
        return result

    monkeypatch.setattr('filerepack.repack._dispatch_packer', encode_then_race)
    with pytest.raises(FileExistsError):
        FileRepacker(temppath=str(scratch)).repack(str(source), outfile=str(output))
    assert source.read_bytes() == b' { "keep": 1 } '
    assert output.read_bytes() == b'late unrelated writer'
    assert list(scratch.iterdir()) == []
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('distinct', [False, True])
@pytest.mark.parametrize('dryrun', [False, True])
def test_video_conversion_reports_effective_destination(tmp_path, monkeypatch, distinct, dryrun):
    source = tmp_path / 'movie.wmv'
    source.write_bytes(b'original video' * 100)
    requested = tmp_path / 'out' / 'requested.wmv' if distinct else source
    effective = requested.with_suffix('.mp4')
    payload = b'\x00\x00\x00\x18ftypmp42' + b'encoded video' * 4

    def encode(ffmpeg, filepath, output, *args, **kwargs):
        Path(output).write_bytes(payload)
        return True

    monkeypatch.setattr('filerepack.media.resolve_tool', lambda name: '/fake/ffmpeg')
    monkeypatch.setattr('filerepack.media._encode_video', encode)
    monkeypatch.setattr('filerepack.media_verify.verify_media_preservation',
                        lambda *a, **k: True)
    # This test isolates destination publication; real decoder coverage is separate.
    monkeypatch.setattr('filerepack.candidates.verify_output', lambda *a, **k: True)
    summary = FileRepacker().repack(
        str(source), outfile=str(requested) if distinct else None,
        options=RepackOptions(dryrun=dryrun),
    )
    assert summary.filepath == str(effective)
    assert summary.results[0].filepath == str(effective)
    assert summary.results[0].replaced is not dryrun
    if dryrun:
        assert source.read_bytes() == b'original video' * 100
        assert not effective.exists()
    elif distinct:
        assert source.read_bytes() == b'original video' * 100
        assert effective.read_bytes() == payload
        assert not requested.exists()
    else:
        assert not source.exists()
        assert effective.read_bytes() == payload


@pytest.mark.parametrize('command', ['repack', 'bulk'])
@pytest.mark.parametrize('flags', [
    ['--compression-level', '99'], ['--jpeg-quality', '500'],
    ['--png-quality', 'typo'], ['--min-savings', 'nan'],
    ['--min-size', '-1'], ['--max-extract-size', '-1G'],
    ['--min-size', '2G', '--max-size', '1G'], ['--progress-interval', '0'],
])
def test_invalid_cli_ranges_write_nothing(tmp_path, command, flags):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output_dir = tmp_path / 'out'
    log = tmp_path / 'invalid.log'
    result = CliRunner().invoke(app, [
        command, str(source if command == 'repack' else tmp_path), *flags,
        '--output-dir', str(output_dir), '--backup', '--log-file', str(log),
    ])
    assert result.exit_code != 0
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not output_dir.exists() and not log.exists()
    assert not (tmp_path / 'source.json.bak').exists()


@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_log_cannot_alias_a_source(tmp_path, command):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    result = CliRunner().invoke(app, [
        command, str(source if command == 'repack' else tmp_path), '--log-file', str(source),
    ])
    assert result.exit_code == 1
    assert 'Log file conflicts' in result.output
    assert source.read_bytes() == b' { "keep": 1 } '


def _hold_reservation(paths, ready, release):
    with PathReservation(paths):
        ready.put('reserved')
        release.wait(10)


def test_cross_process_reservation_refuses_competing_target(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output = tmp_path / 'out.json'
    context = multiprocessing.get_context('spawn')
    ready, release = context.Queue(), context.Event()
    process = context.Process(target=_hold_reservation, args=([str(output)], ready, release))
    process.start()
    try:
        assert ready.get(timeout=10) == 'reserved'
        with pytest.raises(FileExistsError, match='reserved by another operation'):
            FileRepacker().repack(str(source), outfile=str(output))
        assert source.read_bytes() == b' { "keep": 1 } ' and not output.exists()
    finally:
        release.set()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0
    # The owner released every claim; a later operation can publish normally.
    FileRepacker().repack(str(source), outfile=str(output))
    assert output.read_bytes() == b'{"keep":1}'


def test_source_hardlink_aliases_share_a_reservation(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    alias = tmp_path / 'alias.json'
    os.link(source, alias)
    with PathReservation([str(source)]):
        with pytest.raises(FileExistsError, match='reserved by another operation'):
            with PathReservation([str(alias)]):
                pytest.fail('Hardlink identity must share the existing reservation')
    assert source.read_bytes() == alias.read_bytes() == b' { "keep": 1 } '


@pytest.mark.parametrize('kind', ['gz', 'zip'])
def test_cli_distinct_output_for_stream_and_archive(tmp_path, kind):
    if kind == 'zip' and not (shutil.which('7zz') or shutil.which('7z')):
        pytest.skip('7zz/7z required')
    source = tmp_path / ('source.' + kind)
    write_input(source, kind)
    original = source.read_bytes()
    directory = tmp_path / 'out'
    result = CliRunner().invoke(app, [
        'repack', str(source), '--output-dir', str(directory), '--json',
    ])
    assert result.exit_code == 0, result.output
    assert source.read_bytes() == original
    assert (directory / source.name).stat().st_size < len(original)


def test_publication_io_failure_cleans_candidate_and_keeps_source(tmp_path, monkeypatch):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output = tmp_path / 'out.json'
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def fail_link(*args, **kwargs):
        raise OSError('Publication unavailable')

    monkeypatch.setattr('filerepack.destinations.os.link', fail_link)
    with pytest.raises(OSError, match='Publication unavailable'):
        FileRepacker(temppath=str(scratch)).repack(str(source), outfile=str(output))
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not output.exists()
    assert list(scratch.iterdir()) == []
    assert not list(tmp_path.glob('.filerepack-publish-*'))


@pytest.mark.parametrize('keep_if_larger', [False, True])
def test_direct_equal_size_video_dryrun_reports_acceptance(tmp_path, monkeypatch, keep_if_larger):
    source = tmp_path / 'movie.wmv'
    source.write_bytes(b'original' * 20)
    target = source.with_suffix('.mp4')
    payload = b'\x00\x00\x00\x18ftypmp42' + b'x' * (source.stat().st_size - 12)

    def encode(ffmpeg, filepath, output, *args, **kwargs):
        Path(output).write_bytes(payload)
        return True

    monkeypatch.setattr('filerepack.media.resolve_tool', lambda name: '/fake/ffmpeg')
    monkeypatch.setattr('filerepack.media._encode_video', encode)
    monkeypatch.setattr('filerepack.media_verify.verify_media_preservation',
                        lambda *a, **k: True)
    # This test isolates destination publication; real decoder coverage is separate.
    monkeypatch.setattr('filerepack.candidates.verify_output', lambda *a, **k: True)
    result = pack_wmv(str(source), dryrun=True, keep_if_larger=keep_if_larger)
    assert result is not None and not result.replaced
    assert result.filepath == str(source if keep_if_larger else target)
    assert not target.exists() and source.read_bytes() == b'original' * 20


@pytest.mark.parametrize('dryrun', [False, True])
def test_rar_conversion_publication_reports_target_and_preserves_distinct_source(
    tmp_path, monkeypatch, dryrun,
):
    from filerepack.archive_manifest import tree_manifest
    from filerepack.repack import _commit_output

    source = tmp_path / 'bundle.rar'
    source.write_bytes(b'Rar!\x1a\x07\x00' + b'opaque fixture' * 100)
    original = source.read_bytes()
    requested = tmp_path / 'out' / 'requested.rar'
    effective = requested.with_suffix('.7z')
    seed = tmp_path / 'seed'
    seed.mkdir()
    (seed / 'payload.txt').write_bytes(b'preserved payload')
    manifest = tree_manifest(str(seed))
    monkeypatch.setattr('filerepack.archives._source_archive', lambda *args: manifest)
    monkeypatch.setattr('filerepack.repack.resolve_tool', lambda name: None)
    monkeypatch.setattr('filerepack.archives.resolve_tool', lambda name: None)

    def extract(self, filename, output, options):
        shutil.copytree(seed, output, dirs_exist_ok=True)
        return True

    def writer(self, folder, dest, options, summary, insize, *args):
        # Stub the codec only; exercise real reservations/publication and equal-size acceptance.
        candidate = tmp_path / 'encoded.7z'
        candidate.write_bytes(b'7z\xbc\xaf\x27\x1c' + b'x' * (insize - 6))
        result = _commit_output(
            str(candidate), dest, insize, keep_if_larger=False, verify='7z',
            reservation=options['_publication_reservation'],
        )
        assert result is not None and result.replaced
        summary.filepath = result.filepath
        summary.total_outsize = result.outsize

    monkeypatch.setattr(FileRepacker, '_extract_rar', extract)
    monkeypatch.setattr(FileRepacker, '_write_archive', writer)
    # Isolate the RAR-to-7z reservation contract from the controlled encoder stub.
    monkeypatch.setattr('filerepack.candidates.verify_output', lambda *a, **k: True)
    summary = FileRepacker().repack(
        str(source), outfile=str(requested),
        options=RepackOptions(keep_if_larger=False, dryrun=dryrun),
    )
    assert summary.filepath == str(effective)
    assert source.read_bytes() == original
    assert not requested.exists()
    if dryrun:
        assert not effective.exists() and not requested.parent.exists()
    else:
        assert effective.read_bytes().startswith(b'7z\xbc\xaf\x27\x1c')


def test_invalid_job_policy_does_not_coerce_overwrite_to_true(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    result = process_file_job({'filepath': str(source), 'overwrite': 'no'})
    assert result['status'] == 'failed'
    assert 'overwrite must be a boolean' in result['error']
    assert source.read_bytes() == b' { "keep": 1 } '


def test_rejected_savings_candidate_publishes_original_bytes(tmp_path):
    source = tmp_path / 'source.json'
    original = b' { "keep": 1 } '
    source.write_bytes(original)
    output = tmp_path / 'out.json'
    summary = FileRepacker().repack(
        str(source), outfile=str(output), options=RepackOptions(min_savings=100),
    )
    assert output.read_bytes() == source.read_bytes() == original
    assert summary.total_outsize == len(original)


def test_dryrun_keeps_existing_output_even_with_overwrite_authorization(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output = tmp_path / 'out.json'
    output.write_bytes(b'unrelated output')
    FileRepacker().repack(
        str(source), outfile=str(output), options=RepackOptions(
            dryrun=True, overwrite=True, backup=True,
        ),
    )
    assert source.read_bytes() == b' { "keep": 1 } '
    assert output.read_bytes() == b'unrelated output'
    assert not (tmp_path / 'source.json.bak').exists()


def test_custom_scratch_directory_and_original_progress_identity(tmp_path):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    scratch = tmp_path / 'new-scratch'
    events = []
    FileRepacker(temppath=str(scratch)).repack(
        str(source), on_progress=lambda event, **kwargs: events.append(kwargs['name']),
    )
    assert events == [str(source)]
    assert scratch.is_dir() and not list(scratch.iterdir())
    assert source.read_bytes() == b'{"keep":1}'


def test_copy_verification_failure_keeps_source_and_no_output(tmp_path, monkeypatch):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    output = tmp_path / 'out.json'
    scratch = tmp_path / 'scratch'
    scratch.mkdir()

    def corrupt_copy(source, destination):
        Path(destination).write_bytes(b'corrupted copy')

    monkeypatch.setattr('filerepack.destinations.shutil.copy2', corrupt_copy)
    with pytest.raises(OSError, match='Source changed while copying'):
        FileRepacker(temppath=str(scratch)).repack(str(source), outfile=str(output))
    assert source.read_bytes() == b' { "keep": 1 } '
    assert not output.exists() and not list(scratch.iterdir())


@pytest.mark.parametrize('options', [{'jpeg_quality': 500}, {'backup': True}])
def test_directory_library_entry_uses_shared_safety(tmp_path, options):
    source = tmp_path / 'source.json'
    source.write_bytes(b' { "keep": 1 } ')
    backup = tmp_path / 'source.json.bak'
    backup.write_bytes(b'older backup')
    expected = ValueError if 'jpeg_quality' in options else FileExistsError
    with pytest.raises(expected):
        FileRepacker().pack_images(str(tmp_path), options=options)
    assert source.read_bytes() == b' { "keep": 1 } '
    assert backup.read_bytes() == b'older backup'
