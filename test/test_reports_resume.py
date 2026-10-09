import json
import os

import pytest
from test.helpers import separated_cli_runner

from filerepack.__main__ import app
from filerepack.reports import AuditReport, ResultSpool
from filerepack.resume import ResumeManifest


@pytest.mark.parametrize('format', ['json', 'jsonl'])
@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_audit_stdout_and_completion(tmp_path, format, command):
    source_dir = tmp_path / 'input'
    source_dir.mkdir()
    source = source_dir / 'record.json'
    source.write_text(' { "record": [1,2,3] } ' * 1)
    report = tmp_path / ('audit.' + format)
    target = source if command == 'repack' else source_dir
    result = separated_cli_runner().invoke(
        app, [command, str(target), '--json', '--report', str(report)],
    )
    assert result.exit_code == 0, result.output
    stdout = json.loads(result.stdout)
    assert stdout['schema_version'] == 1
    events = (json.loads(report.read_text())['events'] if format == 'json' else
              [json.loads(line) for line in report.read_text().splitlines()])
    assert events[0]['record_type'] == 'run' and events[-1]['record_type'] == 'summary'
    assert events[-1]['complete']
    assert events[1]['status'] == 'replaced' and events[1]['published']
    checks = events[1]['details']['evidence']
    assert any(row['type'] == 'validation' and row['kind'] == 'json' and row['valid']
               for row in checks)


def test_redacted_report_scrubs_member_names_and_errors(tmp_path):
    report = tmp_path / 'private.jsonl'
    sink = AuditReport(str(report), root=str(tmp_path), paths='redacted',
                       options={'exclude_members': ['secret-project/*'],
                                'backup_dir': '/private/name'})
    sink.item({'file': '/private/secret.json', 'status': 'failed', 'reason_code': 'encoder_exit',
               'reason': 'failed /private/secret.json', 'details': {'argv': '/private/secret.json'},
               'members': [{'member': 'secret-member.json', 'reason': 'bad private name'}]})
    sink.finish({'complete': True})
    payload = report.read_text()
    assert 'secret' not in payload and '/private/' not in payload
    assert 'encoder_exit' in payload


def test_json_finalize_collision_keeps_partial(tmp_path):
    report = tmp_path / 'report.json'
    sink = AuditReport(str(report), root=str(tmp_path))
    sink.item({'status': 'unchanged', 'file': 'input.json'})
    report.write_text('unrelated content')
    with pytest.raises(FileExistsError):
        sink.finish({'complete': True})
    assert report.read_text() == 'unrelated content'
    assert os.path.exists(sink.partial)


def test_result_spool_bounded_memory():
    spool = ResultSpool()
    for index in range(10000):
        spool.append({'file': str(index), 'reason': 'x' * 200})
    assert spool.stream._rolled
    assert len(spool) == 10000
    assert sum(1 for _ in spool) == 10000
    spool.close()


def test_checkpoint_resume_and_same_size_edit(tmp_path):
    source = tmp_path / 'source.json'
    path = tmp_path / 'run.manifest'
    source.write_text('{"value":1}')
    state = ResumeManifest(str(path), root=str(tmp_path), fingerprint='execution-v1')
    job = {'filepath': str(source)}
    assert state.prepare(job) is None
    row = {'file': str(source), 'output_file': str(source), 'status': 'unchanged',
           'original_size': source.stat().st_size, 'final_size': source.stat().st_size}
    state.record(row, job)
    with pytest.raises(FileExistsError):
        ResumeManifest(str(path), root=str(tmp_path), fingerprint='execution-v1', resume=True)
    state.close()
    state = ResumeManifest(str(path), root=str(tmp_path), fingerprint='execution-v1', resume=True)
    reused = state.prepare({'filepath': str(source)})
    assert reused['reused'] and reused['savings_bytes'] == 0 and not reused['published']
    original_stat = source.stat()
    source.write_text('{"value":2}')
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert state.prepare({'filepath': str(source)}) is None
    state.close()


def test_cli_bulk_resume_no_encoder(tmp_path, monkeypatch):
    inputs = tmp_path / 'input'
    inputs.mkdir()
    source = inputs / 'a.json'
    source.write_text(' {"value":1} ')
    manifest = tmp_path / 'run.manifest'
    monkeypatch.setattr('filerepack.__main__.execution_fingerprint', lambda *a: 'test-execution')
    args = ['bulk', str(inputs), '--json', '--manifest', str(manifest)]
    result = separated_cli_runner().invoke(app, args)
    assert result.exit_code == 0, result.output
    monkeypatch.setattr('filerepack.__main__.process_file_job',
                        lambda *a: pytest.fail('Completed input re-encoded'))
    resumed = separated_cli_runner().invoke(app, args + ['--resume'])
    assert resumed.exit_code == 0, resumed.output
    row = json.loads(resumed.stdout)['files'][0]
    assert row['reused'] and row['savings_bytes'] == 0
    assert json.loads(resumed.stdout)['summary']['actual_saved'] == 0


def test_checkpoint_failure_preserves_prior_file(tmp_path, monkeypatch):
    path = tmp_path / 'run.manifest'
    source = tmp_path / 'source.json'
    source.write_text('{}')
    state = ResumeManifest(str(path), root=str(tmp_path), fingerprint='same')
    before = path.read_bytes()
    monkeypatch.setattr('filerepack.resume.os.replace',
                        lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        state.record({'status': 'unchanged', 'output_file': str(source)}, {'filepath': str(source)})
    assert path.read_bytes() == before
    state.close()


@pytest.mark.parametrize('change', ['delete', 'edit', 'fingerprint', 'reappeared-source'])
def test_converted_output_reuse_requires_both_generation_and_content(tmp_path, change):
    source, output = tmp_path / 'source.avi', tmp_path / 'source.mp4'
    path = tmp_path / 'run.manifest'
    source.write_bytes(b'original media')
    state = ResumeManifest(str(path), root=str(tmp_path), fingerprint='same')
    job = {'filepath': str(source)}
    state.prepare(job)
    source.unlink()
    output.write_bytes(b'converted media')
    state.record({'file': str(source), 'status': 'replaced', 'output_file': str(output)}, job)
    state.close()
    state = ResumeManifest(str(path), root=str(tmp_path),
                           fingerprint='new' if change == 'fingerprint' else 'same', resume=True)
    reused = state.prepare({'filepath': str(output)})
    if change != 'fingerprint':
        assert reused['reused'] and reused['file'] == str(output)
        assert reused['savings_bytes'] == 0
    if change == 'delete':
        output.unlink()
        with pytest.raises(OSError):
            state.prepare({'filepath': str(output)})
    elif change == 'edit':
        output.write_bytes(b'changed media')
        assert state.prepare({'filepath': str(output)}) is None
    elif change == 'reappeared-source':
        source.write_bytes(b'new source')
        assert state.prepare({'filepath': str(output)}) is None
    else:
        assert reused is None
    state.close()


def test_resume_applies_current_size_filters_before_reusing(tmp_path, monkeypatch):
    source = tmp_path / 'input'
    source.mkdir()
    (source / 'a.json').write_text(' {"a":1} ')
    manifest = tmp_path / 'run.manifest'
    monkeypatch.setattr('filerepack.__main__.execution_fingerprint', lambda *a: 'test')
    args = ['bulk', str(source), '--json', '--manifest', str(manifest)]
    assert separated_cli_runner().invoke(app, args).exit_code == 0
    result = separated_cli_runner().invoke(app, args + ['--resume', '--min-size', '1MB'])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)['files'][0]['reason_code'] == 'filtered'


def test_interrupted_bulk_reuses_only_completed_input(tmp_path, monkeypatch):
    import filerepack.__main__ as cli
    root = tmp_path / 'input'
    root.mkdir()
    for name in ('a', 'b', 'c'):
        (root / (name + '.json')).write_text(' {"value":1} ')
    manifest = tmp_path / 'run.manifest'
    monkeypatch.setattr(cli, 'execution_fingerprint', lambda *args: 'fixture-execution')
    original = cli.process_file_job
    calls = []

    def interrupted(job):
        calls.append(job['filepath'])
        if len(calls) == 2:
            raise KeyboardInterrupt
        return original(job)

    monkeypatch.setattr(cli, 'process_file_job', interrupted)
    args = ['bulk', str(root), '--json', '--manifest', str(manifest)]
    first = separated_cli_runner().invoke(app, args)
    assert first.exit_code == 130, first.output
    completed = calls[0]
    second_calls = []

    def resumed(job):
        second_calls.append(job['filepath'])
        assert job['filepath'] != completed
        return original(job)

    monkeypatch.setattr(cli, 'process_file_job', resumed)
    second = separated_cli_runner().invoke(app, args + ['--resume'])
    assert second.exit_code == 0, second.output
    rows = json.loads(second.stdout)['files']
    assert len(second_calls) == 2
    assert next(row for row in rows if row['file'] == completed)['reused']


@pytest.mark.parametrize('fault', ['header-type', 'entry-type', 'schema', 'footer', 'checksum'])
def test_malformed_checkpoint_refused_and_lock_released(tmp_path, fault):
    path = tmp_path / 'run.manifest'
    state = ResumeManifest(str(path), root=str(tmp_path), fingerprint='same')
    state.close()
    lines = path.read_text().splitlines()
    if fault == 'header-type':
        lines[0] = '[]'
    elif fault == 'entry-type':
        lines.insert(1, '[]')
    elif fault == 'schema':
        header = json.loads(lines[0])
        header['schema_version'] = 999
        lines[0] = json.dumps(header)
    elif fault == 'footer':
        lines.pop()
    else:
        footer = json.loads(lines[-1])
        footer['sha256'] = '0' * 64
        lines[-1] = json.dumps(footer)
    path.write_text('\n'.join(lines) + '\n')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        ResumeManifest(str(path), root=str(tmp_path), fingerprint='same', resume=True)
    assert path.read_bytes() == before
    assert not os.path.exists(str(path) + '.filerepack-lock')


@pytest.mark.parametrize('change', ['options', 'version', 'path', 'bytes', 'registry',
                                    'adapter', 'profile', 'destination', 'library'])
def test_execution_fingerprint_invalidates_changed_contract(tmp_path, monkeypatch, change):
    import filerepack.resume as resume
    import filerepack.profiles as profiles
    tool = tmp_path / 'encoder'
    tool.write_bytes(b'encoder v1')
    selected, version = [str(tool)], ['fixture-v1']
    monkeypatch.setattr(resume, 'resolve_tool', lambda key: selected[0] if key == 'szip' else None)
    monkeypatch.setattr(resume, 'probe_version', lambda *args: version[0])
    monkeypatch.setattr(resume, 'adapter_fingerprint', lambda: 'fixture-adapter-v1')
    monkeypatch.setattr(resume, 'library_versions', lambda: {'mutagen': None})
    options, destination = {'compression_level': 6}, None
    before = resume.execution_fingerprint(options, str(tmp_path), destination)
    if change == 'options':
        options['compression_level'] = 9
    elif change == 'version':
        version[0] = 'fixture-v2'
    elif change == 'path':
        other = tmp_path / 'other-encoder'
        other.write_bytes(tool.read_bytes())
        selected[0] = str(other)
    elif change == 'bytes':
        tool.write_bytes(b'encoder v2')
    elif change == 'registry':
        monkeypatch.setattr(resume, 'REGISTRY_VERSION', resume.REGISTRY_VERSION + 1)
    elif change == 'adapter':
        monkeypatch.setattr(resume, 'adapter_fingerprint', lambda: 'fixture-adapter-v2')
    elif change == 'profile':
        monkeypatch.setattr(profiles, 'PROFILES', {**profiles.PROFILES, 'fast': {'ultra': True}})
    elif change == 'library':
        monkeypatch.setattr(resume, 'library_versions', lambda: {'mutagen': 'fixture-installed'})
    else:
        destination = str(tmp_path / 'output')
    assert resume.execution_fingerprint(options, str(tmp_path), destination) != before


@pytest.mark.parametrize('fault', ['item', 'finalization'])
@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_report_failure_returns_non_success_with_actual_published_outcome(
    tmp_path, monkeypatch, fault, command,
):
    root = tmp_path / 'input'
    root.mkdir()
    source = root / 'a.json'
    source.write_text(' {"value":1} ')
    report = tmp_path / 'report.json'

    def disk_full(*args, **kwargs):
        raise OSError('fixture disk full')

    monkeypatch.setattr(AuditReport, 'item' if fault == 'item' else '_finalize_json', disk_full)
    target = source if command == 'repack' else root
    result = separated_cli_runner().invoke(
        app, [command, str(target), '--json', '--report', str(report)],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    row = data if command == 'repack' else data['files'][0]
    assert row['published'] and row['status'] == 'replaced'
    assert source.read_text() == '{"value":1}'
