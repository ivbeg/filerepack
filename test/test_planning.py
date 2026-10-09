import json
import os
import shutil
import sys
import zipfile

import pytest
from typer.testing import CliRunner

from filerepack import RepackOptions, inspect_file, options_for_profile
from filerepack.__main__ import app
from filerepack.repack import _normalize_options
from filerepack.tools import resolve_tool


@pytest.mark.parametrize('profile,level,ultra,meta', [
    ('fast', 3, False, False), ('balanced', 6, False, False),
    ('maximum', 9, True, False), ('preserve', 6, False, True),
])
def test_profiles_exact_defaults_and_explicit_false(profile, level, ultra, meta):
    value = options_for_profile(profile)
    assert (value.compression_level, value.ultra, value.keep_meta) == (level, ultra, meta)
    assert not value.lossy
    assert value.jpeg_quality is None and value.png_quality is None and value.pdf_profile is None
    override = options_for_profile(profile, compression_level=9, ultra=False, keep_meta=False)
    assert override.compression_level == 9 and not override.ultra and not override.keep_meta
    assert _normalize_options({'profile': profile})['compression_level'] == level
    direct = RepackOptions(profile=profile)
    assert direct.to_dict() == value.to_dict()
    explicit = RepackOptions(profile=profile, compression_level=9, ultra=False, keep_meta=False)
    assert explicit.compression_level == 9 and not explicit.ultra and not explicit.keep_meta
    assert explicit.profile_version == 1
    with pytest.raises(ValueError, match='profile version'):
        options_for_profile(profile, profile_version=999)


def test_cli_explicit_default_value_preserved(tmp_path):
    source = tmp_path / 'a.json'
    source.write_text(' {"value": 1} ')
    result = CliRunner().invoke(app, ['repack', str(source), '--dryrun', '--json',
                                     '--profile', 'fast', '--compression-level', '9'])
    assert result.exit_code == 0, result.output
    options = json.loads(result.stdout)['details']['effective_options']
    assert options['profile'] == 'fast' and options['compression_level'] == 9


def test_inspection_no_candidate_or_destination_mutation(tmp_path, monkeypatch):
    source = tmp_path / 'signed.docx'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('_xmlsignatures/sig1.xml', '<signature/>')
        archive.writestr('word/document.xml', '<document/>')
    before = source.read_bytes()
    destination = tmp_path / 'out' / 'signed.docx'
    monkeypatch.setattr('filerepack.transactions.make_temp', lambda *a, **k: pytest.fail('scratch'))
    monkeypatch.setattr('filerepack.dispatch.dispatch_packer',
                        lambda *a, **k: pytest.fail('encoder'))
    result = inspect_file(str(source), str(destination), {'backup': True})
    assert result.protection == 'protected' and result.eligibility == 'blocked'
    assert result.estimates['candidate_savings']['value'] is None
    assert source.read_bytes() == before and not destination.parent.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ['signed.docx']


def test_directory_inspection_jsonl(tmp_path):
    (tmp_path / 'first.json').write_text('{}')
    (tmp_path / 'second.xml').write_text('<root/>')
    result = CliRunner().invoke(app, ['inspect', str(tmp_path), '--json'])
    assert result.exit_code == 0, result.output
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert [x['record_type'] for x in records] == ['item', 'item', 'summary']
    assert records[-1]['scan_complete']


def test_interrupted_directory_inspection_keeps_parseable_completion_state(tmp_path, monkeypatch):
    source = tmp_path / 'item.json'
    source.write_text('{}')

    def discovery(*args, **kwargs):
        yield str(source)
        raise KeyboardInterrupt

    monkeypatch.setattr('filerepack.__main__._collect_bulk_files', discovery)
    result = CliRunner().invoke(app, ['inspect', str(tmp_path), '--json'])
    assert result.exit_code == 130
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert records[0]['record_type'] == 'item'
    assert records[-1]['record_type'] == 'summary' and not records[-1]['scan_complete']


def test_inspection_unknown_protection_and_occupied_target_are_independent(tmp_path):
    source, destination = tmp_path / 'ambiguous.zip', tmp_path / 'occupied.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('member.json', '{}')
    destination.write_bytes(b'unrelated')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = inspect_file(str(source), str(destination))
    assert result.protection == 'unknown' and result.eligibility == 'blocked'
    assert any('Destination conflict' in blocker for blocker in result.blockers)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_override_executable_and_config_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv('FILEREPACK_FFMPEG', str(tmp_path / 'missing'))
    assert resolve_tool('ffmpeg') is None
    executable = tmp_path / ('fake.exe' if os.name == 'nt' else 'fake')
    if os.name == 'nt':
        shutil.copyfile(sys.executable, executable)
    else:
        executable.write_text('#!/bin/sh\nprintf "example version 1\\n"\n')
    assert resolve_tool('ffmpeg') is None
    executable.chmod(0o755)
    monkeypatch.setenv('FILEREPACK_FFMPEG', str(executable))
    assert resolve_tool('ffmpeg') == str(executable)
    monkeypatch.delenv('FILEREPACK_FFMPEG')
    config = tmp_path / 'config.toml'
    monkeypatch.setattr('filerepack.tools._config_paths', lambda: [str(config)])
    config.write_text('[tools]\nffmpeg=' + json.dumps(str(executable)) + '\n')
    assert resolve_tool('ffmpeg') == str(executable)
    config.write_text('[tools]\nffmpeg=' + json.dumps(str(tmp_path / 'missing')) + '\n')
    assert resolve_tool('ffmpeg') is None
