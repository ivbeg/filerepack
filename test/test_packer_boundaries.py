"""Public compatibility and tool-owned scratch survive family relocation."""

import importlib
import inspect
import json
import os
import sqlite3
import struct
import subprocess
import sys
import zlib
import zipfile
from pathlib import Path

import pytest

import filerepack
from filerepack import candidates, data, images, media
from filerepack import archives
from filerepack.dispatch import _PACKERS
from filerepack.repack import FileRepacker, pack_png


# Captured before the family moves, including legacy keyword defaults/routes.
_BASELINE = json.loads(Path(__file__).with_name('packer_api.json').read_text())
_HELPERS = [
    (module, name, signature)
    for module, helpers in _BASELINE.items() if module != 'registry'
    for name, signature in helpers.items()
]


@pytest.mark.parametrize('module,name,signature', _HELPERS)
def test_existing_helper_calling_contract(module, name, signature):
    helper = getattr(importlib.import_module(module), name)
    actual = inspect.signature(helper)
    actual = actual.replace(
        parameters=[parameter.replace(annotation=inspect.Parameter.empty)
                    for parameter in actual.parameters.values()],
        return_annotation=inspect.Signature.empty,
    )
    assert str(actual) == signature


def test_registry_retains_all_existing_routes_and_options():
    # New formats may add routes; every pre-existing route must remain intact.
    for key, (name, category, extra) in _BASELINE['registry'].items():
        spec = _PACKERS[key]
        assert (spec.func.__name__, spec.category) == (name, category)
        assert all(spec.extra.get(option) == argument for option, argument in extra.items())
    for spec in _PACKERS.values():
        owner = importlib.import_module(spec.func.__module__)
        assert getattr(owner, spec.func.__name__) is spec.func


@pytest.mark.parametrize('modules', [
    ('codecs', 'markup', 'repack'), ('repack', 'codecs', 'markup'),
    ('images', 'markup', 'documents'), ('medical', 'data', 'streams'),
    ('containers', 'dispatch', 'archives'), ('dispatch', 'containers', 'archives'),
])
def test_family_imports_in_fresh_process(tmp_path, modules):
    code = (
        'import importlib\n'
        f'modules = {modules!r}\n'
        'for name in modules: importlib.import_module("filerepack." + name)\n'
        'from filerepack.repack import FileRepacker, pack_png\n'
        'from filerepack.codecs import pack_json, pack_ai, pack_sqlite\n'
        'from filerepack.images import pack_png as implementation\n'
        'assert pack_png is implementation\n'
    )
    subprocess.run(
        [sys.executable, '-c', code], cwd=tmp_path, check=True, capture_output=True,
        env={**os.environ, 'PYTHONPATH': str(Path(filerepack.__file__).resolve().parent.parent)},
    )


def _png_bytes(padding=0):
    def chunk(kind, payload):
        return (struct.pack('>I', len(payload)) + kind + payload +
                struct.pack('>I', zlib.crc32(kind + payload)))
    return (
        b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
        chunk(b'tEXt', b'comment\x00' + b' ' * padding) +
        chunk(b'IDAT', zlib.compress(b'\x00\x10\x20\x30')) + chunk(b'IEND', b'')
    )


@pytest.mark.parametrize('outcome', ['failed', 'exception', 'accepted', 'dryrun', 'rejected',
                                     'invalid'])
def test_pngquant_sidecar_is_owned_for_every_outcome(tmp_path, monkeypatch, outcome):
    source = tmp_path / 'source.png'
    original = _png_bytes(1000)
    source.write_bytes(original)
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    monkeypatch.setattr(images, 'resolve_tool', lambda name: '/fake/pngquant')
    calls = []

    def encode(command, **kwargs):
        work = Path(command[-1])
        sidecar = work.with_name(work.stem + '-fs8.png')
        sidecar.write_bytes(b'invalid' if outcome == 'invalid' else _png_bytes())
        calls.append(sidecar)
        if outcome == 'exception':
            raise OSError('encoder interrupted')
        return None if outcome == 'failed' else subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(images, '_run_command', encode)
    if outcome == 'exception':
        with pytest.raises(OSError, match='encoder interrupted'):
            pack_png(str(source), lossy=True)
    else:
        result = pack_png(str(source), lossy=True, dryrun=outcome == 'dryrun',
                          min_savings=100 if outcome == 'rejected' else None)
        if outcome in ('failed', 'invalid'):
            assert result is None
        else:
            assert result.replaced == (outcome == 'accepted')
    assert calls and all(not sidecar.exists() for sidecar in calls)
    assert list(scratch.iterdir()) == []
    assert source.read_bytes() == (_png_bytes() if outcome == 'accepted' else original)


def test_preexisting_pngquant_sidecar_is_never_claimed(tmp_path, monkeypatch):
    source = tmp_path / 'source.png'
    source.write_bytes(_png_bytes(1000))
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    allocate = candidates.make_temp
    existing = []

    def allocate_with_collision(suffix):
        path = allocate(suffix)
        sidecar = Path(path).with_name(Path(path).stem + '-fs8.png')
        sidecar.write_bytes(b'another operation')
        existing.append(sidecar)
        return path

    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    monkeypatch.setattr(candidates, 'make_temp', allocate_with_collision)
    monkeypatch.setattr(images, 'resolve_tool', lambda name: '/fake/pngquant')
    monkeypatch.setattr(images, '_run_command', lambda *args, **kwargs: pytest.fail(
        'encoder must not overwrite an existing sidecar'))
    with pytest.raises(FileExistsError, match='sidecar already exists'):
        pack_png(str(source), lossy=True)
    assert source.read_bytes() == _png_bytes(1000)
    assert list(scratch.iterdir()) == existing
    assert existing[0].read_bytes() == b'another operation'


@pytest.mark.parametrize('phase', ['decode', 'encode'])
@pytest.mark.parametrize('raises', [False, True])
def test_woff2_tool_directory_cleans_unknown_sidecars(tmp_path, monkeypatch, phase, raises):
    source = tmp_path / 'source.woff2'
    original = b'wOF2' + b'original font'
    source.write_bytes(original)
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    monkeypatch.setattr(data, 'pack_woff', lambda *args, **kwargs: None)
    monkeypatch.setattr(data, 'resolve_tool', lambda name: name)
    commands = []

    def encode(command, **kwargs):
        directory = Path(command[1]).parent
        (directory / 'font.ttf').write_bytes(b'decoded font')
        (directory / 'tool.log').write_bytes(b'tool-owned scratch')
        commands.append(command)
        failed = ('decode' if command[0] == 'woff2_decompress' else 'encode') == phase
        if failed and raises:
            raise OSError('font encoder interrupted')
        return None if failed else subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(data, '_run_command', encode)
    if raises:
        with pytest.raises(OSError, match='font encoder interrupted'):
            data.pack_woff2(str(source))
    else:
        assert data.pack_woff2(str(source)) is None
    assert len(commands) == (1 if phase == 'decode' else 2)
    assert source.read_bytes() == original
    assert list(scratch.iterdir()) == []


def test_failed_sqlite_candidate_cleans_only_its_journals(tmp_path, monkeypatch):
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(str(source)) as database:
        database.execute('CREATE TABLE preserved(value TEXT)')
        database.execute("INSERT INTO preserved VALUES ('keep')")
    original = source.read_bytes()
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    untouched = scratch / 'other.sqlite-journal'
    untouched.write_bytes(b'other transaction')
    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    candidates_seen = []

    class FailedDatabase:
        def execute(self, statement):
            destination = statement.split("'")[1]
            Path(destination).write_bytes(b'partial')
            candidates_seen.append(destination)
            for suffix in ('-journal', '-wal', '-shm'):
                Path(destination + suffix).write_bytes(b'partial journal')
            raise RuntimeError('database interrupted')

        def close(self):
            pass

    monkeypatch.setattr(sqlite3, 'connect', lambda *args, **kwargs: FailedDatabase())
    with pytest.raises(RuntimeError, match='database interrupted'):
        data.pack_sqlite(str(source), sqlite_offline=True)
    assert candidates_seen
    assert source.read_bytes() == original
    assert list(scratch.iterdir()) == [untouched]
    assert untouched.read_bytes() == b'other transaction'


def test_audio_probe_keeps_nonzero_diagnostics_in_shared_runner(tmp_path):
    probe = tmp_path / 'probe.py'
    probe.write_text('import os, sys\nprint("Audio: alac", file=sys.stderr, flush=True)\n'
                     'os._exit(1)\n')
    # Python's -i flag accepts the same argument vector as the ffmpeg probe.
    assert media._probe_audio_codec(str(probe), sys.executable, False) == 'alac'


@pytest.mark.parametrize('fault', ['encoder', 'validator', 'unexpected'])
def test_archive_fault_cleans_candidate_and_extraction(tmp_path, monkeypatch, fault):
    source = tmp_path / 'source.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('keep.txt', b'unchanged archive member' * 1000)
    original = source.read_bytes()
    scratch = tmp_path / 'scratch'
    scratch.mkdir()
    monkeypatch.setattr(candidates, 'TEMP_PATH', str(scratch))
    monkeypatch.setattr(archives, 'resolve_szip', lambda: '/fake/7zz')
    staged = []

    def extract(self, filename, directory, options):
        with zipfile.ZipFile(filename) as archive:
            archive.extractall(directory)
        return True

    def encode(command, **kwargs):
        candidate = Path(command[command.index('a') + 1])
        candidate.write_bytes(b'partial candidate')
        staged.append(candidate)
        if fault == 'unexpected':
            raise RuntimeError('unexpected encoder failure')
        if fault == 'encoder':
            raise OSError('encoder failure')
        return subprocess.CompletedProcess(command, 0)

    def validate(*args, **kwargs):
        raise OSError('validator failure')

    monkeypatch.setattr(FileRepacker, '_extract_7z', extract)
    monkeypatch.setattr(archives, '_run_command', encode)
    monkeypatch.setattr(FileRepacker, '_verify_archive_candidate', validate)
    repacker = FileRepacker(temppath=str(scratch))
    if fault == 'unexpected':
        with pytest.raises(RuntimeError, match='unexpected encoder failure'):
            repacker.repack(str(source))
    else:
        summary = repacker.repack(str(source))
        assert summary.total_outsize == len(original)
    assert staged and all(not path.exists() for path in staged)
    assert source.read_bytes() == original
    assert list(scratch.iterdir()) == []
