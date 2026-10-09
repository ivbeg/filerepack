"""Human completion labels agree with real terminal outcomes and exit codes."""

import csv
import io
import json

import pytest
from test.helpers import separated_cli_runner

from filerepack.__main__ import app


@pytest.mark.parametrize('dryrun', [False, True])
@pytest.mark.parametrize('content', [' { "value": 1 } ', '{"value":1}'])
def test_success_is_explicit_with_and_without_size_reduction(tmp_path, dryrun, content):
    source = tmp_path / 'data.json'
    source.write_text(content)
    extra = ['--dryrun'] if dryrun else []
    result = separated_cli_runner().invoke(app, ['repack', str(source), '--verbose', *extra])
    assert result.exit_code == 0, result.output
    assert '[SUCCESS]' in result.stdout and '[ERROR]' not in result.output
    if dryrun:
        assert '[SUCCESS] [DRYRUN] File' in result.stdout
        assert source.read_text() == content
    else:
        assert source.read_text() == '{"value":1}'
    if content == '{"value":1}':
        assert 'unchanged' in result.stdout


@pytest.mark.parametrize('quiet', [False, True])
def test_real_decode_error_is_explicit_and_never_reported_as_unchanged(tmp_path, quiet):
    source = tmp_path / 'broken.gz'
    source.write_bytes(b'not gzip')
    extra = ['--quiet'] if quiet else []
    result = separated_cli_runner().invoke(app, ['repack', str(source), *extra])
    assert result.exit_code == 1
    assert '[ERROR] failed' in result.stderr
    assert '[SUCCESS]' not in result.output and 'File ' not in result.stdout
    assert source.read_bytes() == b'not gzip'


def test_missing_tool_is_explicit_error(tmp_path, monkeypatch):
    source = tmp_path / 'source.lzo'
    original = b'\x89LZO\x00\r\n\x1a\n' + b'\x00' * 30
    source.write_bytes(original)
    monkeypatch.setattr('filerepack.tools.which', lambda name: None)
    result = separated_cli_runner().invoke(app, ['repack', str(source)])
    assert result.exit_code == 1
    assert '[ERROR] unsupported' in result.stderr
    assert '[SUCCESS]' not in result.output
    assert source.read_bytes() == original


def test_intentional_skip_is_distinct_from_an_error(tmp_path):
    source = tmp_path / 'small.json'
    source.write_text('{}')
    result = separated_cli_runner().invoke(app, ['repack', str(source), '--min-size', '1KB'])
    assert result.exit_code == 0
    assert '[SKIPPED]' in result.stdout and '[ERROR]' not in result.output
    assert source.read_text() == '{}'


def test_user_interruption_has_an_explicit_cancelled_label(tmp_path, monkeypatch):
    source = tmp_path / 'data.json'
    source.write_text('{}')

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr('filerepack.__main__.FileRepacker.repack_zip_file', interrupted)
    result = separated_cli_runner().invoke(app, ['repack', str(source)])
    assert result.exit_code == 130
    assert '[CANCELLED]' in result.stderr
    assert '[SUCCESS]' not in result.output


def test_quiet_suppresses_success_messages(tmp_path):
    source = tmp_path / 'data.json'
    source.write_text('{}')
    result = separated_cli_runner().invoke(app, ['repack', str(source), '--quiet'])
    assert result.exit_code == 0 and not result.stdout


@pytest.mark.parametrize('format', ['json', 'csv'])
@pytest.mark.parametrize('valid', [False, True])
def test_machine_reports_remain_parseable_without_human_labels(tmp_path, format, valid):
    source = tmp_path / ('data.json' if valid else 'broken.gz')
    source.write_bytes(b' { "value": 1 } ' if valid else b'not gzip')
    result = separated_cli_runner().invoke(app, ['repack', str(source), '--' + format, '--verbose'])
    assert result.exit_code == (0 if valid else 1)
    assert '[SUCCESS]' not in result.stdout and '[ERROR]' not in result.stdout
    if format == 'json':
        row = json.loads(result.stdout)
    else:
        row = next(csv.DictReader(io.StringIO(result.stdout)))
    assert row['status'] == ('replaced' if valid else 'failed')


@pytest.mark.parametrize('dryrun', [False, True])
def test_bulk_clean_completion_has_success_label(tmp_path, dryrun):
    (tmp_path / 'data.json').write_text(' { "value": 1 } ')
    extra = ['--dryrun'] if dryrun else []
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path), *extra])
    assert result.exit_code == 0, result.output
    prefix = '[DRYRUN] ' if dryrun else ''
    assert f'[SUCCESS] {prefix}Bulk processing completed.' in result.stdout
    assert '[ERROR]' not in result.output


@pytest.mark.parametrize('continue_on_error', [False, True])
@pytest.mark.parametrize('quiet', [False, True])
def test_bulk_failure_has_error_summary_matching_exit_code(tmp_path, continue_on_error, quiet):
    (tmp_path / 'a-good.json').write_text(' { "value": 1 } ')
    (tmp_path / 'b-broken.gz').write_bytes(b'not gzip')
    extra = ['--continue-on-error'] if continue_on_error else []
    if quiet:
        extra.append('--quiet')
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path), *extra])
    assert result.exit_code == (2 if continue_on_error else 1)
    assert '[ERROR] (failed)' in result.stderr
    verb = 'completed with errors' if continue_on_error else 'stopped after an error'
    assert f'[ERROR] Bulk processing {verb}.' in result.stderr
    assert '[SUCCESS] Bulk processing completed.' not in result.output
    if quiet:
        assert not result.stdout


@pytest.mark.parametrize('failure', ['scan', 'interrupted'])
def test_bulk_scan_failure_and_interruption_have_terminal_labels(tmp_path, monkeypatch, failure):
    def failed_scan(*args, **kwargs):
        if failure == 'scan':
            raise OSError('Cannot read directory')
        raise KeyboardInterrupt
        yield  # Make discovery lazy so the error occurs inside the job lifecycle.

    monkeypatch.setattr('filerepack.__main__._collect_bulk_files', failed_scan)
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path)])
    assert result.exit_code == (1 if failure == 'scan' else 130)
    label = '[ERROR]' if failure == 'scan' else '[CANCELLED]'
    assert label in result.stderr
    assert '[SUCCESS]' not in result.output
    if failure == 'scan':
        assert 'Cannot read directory' in result.stderr


def test_bulk_intentional_skip_still_completes_successfully(tmp_path):
    (tmp_path / 'small.json').write_text('{}')
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path), '--min-size', '1KB'])
    assert result.exit_code == 0
    assert '[SKIPPED]' in result.stdout
    assert '[SUCCESS] Bulk processing completed.' in result.stdout
    assert '[ERROR]' not in result.output


@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_missing_input_has_explicit_error_label(tmp_path, command):
    result = separated_cli_runner().invoke(app, [command, str(tmp_path / 'missing')])
    assert result.exit_code == 1
    assert '[ERROR]' in result.stderr
    assert '[SUCCESS]' not in result.output


@pytest.mark.parametrize('command', ['repack', 'bulk'])
def test_report_failure_cannot_claim_successful_completion(tmp_path, monkeypatch, command):
    inputs = tmp_path / 'input'
    inputs.mkdir()
    source = inputs / 'data.json'
    source.write_text(' { "value": 1 } ')

    def failed_report(*args, **kwargs):
        raise OSError('disk full')

    monkeypatch.setattr('filerepack.reports.AuditReport.finish', failed_report)
    target = source if command == 'repack' else inputs
    result = separated_cli_runner().invoke(
        app, [command, str(target), '--report', str(tmp_path / 'report.json')],
    )
    assert result.exit_code == 1
    assert '[ERROR]' in result.stderr and 'disk full' in result.stderr
    assert '[SUCCESS] File' not in result.stdout
    assert '[SUCCESS] Bulk processing completed.' not in result.stdout
