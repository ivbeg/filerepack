"""Public outcome/reporting contracts with real input bytes and owned processes."""

import csv
import gzip
import io
import json
import sys
import threading
import time

import pytest
from test.helpers import separated_cli_runner

from filerepack import FileRepacker
from filerepack.__main__ import app
from filerepack.commands import capture_command
from filerepack.format_support import format_scope


def test_corrupt_gzip_is_failed_and_does_not_publish(tmp_path):
    source = tmp_path / 'broken.gz'
    source.write_bytes(b'not gzip')
    destination = tmp_path / 'out.gz'
    summary = FileRepacker().repack(str(source), outfile=str(destination))
    assert summary.outcome.status == 'failed'
    assert summary.outcome.reason_code == 'decode_or_encode_error'
    assert not summary.outcome.published
    assert not destination.exists()
    assert source.read_bytes() == b'not gzip'
    assert not summary.results  # legacy successful-file projection stays compatible


def test_unchanged_copy_is_published_without_claiming_transformation(tmp_path):
    source = tmp_path / 'a.json'
    source.write_bytes(b'{"x":1}')
    destination = tmp_path / 'copy.json'
    outcome = FileRepacker().repack(str(source), outfile=str(destination)).outcome
    assert outcome.status == 'unchanged'
    assert outcome.published
    assert outcome.destination == str(destination)
    assert destination.read_bytes() == source.read_bytes()


def test_dryrun_is_predicted_and_source_is_unchanged(tmp_path):
    source = tmp_path / 'a.json'
    original = b' { "x": 1 } '
    source.write_bytes(original)
    outcome = FileRepacker().repack(str(source), options={'dryrun': True}).outcome
    assert outcome.status == 'predicted'
    assert not outcome.published
    assert outcome.final_size < outcome.original_size
    assert source.read_bytes() == original


@pytest.mark.parametrize('mode', ['--json', '--csv'])
def test_bulk_report_retains_all_terminal_outcomes(tmp_path, mode):
    (tmp_path / 'a.json').write_bytes(b' { "x": 1 } ')
    (tmp_path / 'broken.gz').write_bytes(b'bad')
    (tmp_path / 'filtered.json').write_bytes(b'{}')
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path), mode, '--continue-on-error',
                                    '--min-size', '3', '--verbose'])
    assert result.exit_code == 2, result.output
    if mode == '--json':
        data = json.loads(result.stdout)
        rows = data['files']
        assert data['summary']['known_inputs'] == 3
        assert sum(data['summary']['counts'].values()) == 3
        assert data['summary']['scan_complete']
    else:
        rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert {row['status'] for row in rows} == {'replaced', 'failed', 'skipped'}
    assert len(rows) == 3


def test_missing_tool_is_unsupported(tmp_path, monkeypatch):
    source = tmp_path / 'a.lzo'
    source.write_bytes(b'\x89LZO\x00\r\n\x1a\n' + b'\x00' * 30)
    monkeypatch.setattr('filerepack.tools.which', lambda name: None)
    outcome = FileRepacker().repack(str(source)).outcome
    assert outcome.status == 'unsupported'
    assert outcome.reason_code == 'missing_tool'


def test_parallel_bulk_excludes_output_and_drains_known_results(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    (output / 'existing.json').write_bytes(b' { "x": 0 } ')
    for number in range(7):
        (tmp_path / f'{number}.json').write_bytes(b' { "x": 1 } ')
    result = separated_cli_runner().invoke(app, ['bulk', str(tmp_path), '--json', '--jobs', '2',
                                    '--output-dir', str(output)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert len(data['files']) == 7
    assert all(row['status'] == 'replaced' for row in data['files'])
    assert data['summary']['scan_complete']
    assert (output / 'existing.json').read_bytes() == b' { "x": 0 } '


def test_cancellation_terminates_owned_encoder(tmp_path):
    marker = tmp_path / 'late-write'
    event = threading.Event()
    timer = threading.Timer(0.2, event.set)
    started = time.monotonic()
    timer.start()
    try:
        with format_scope({'_cancel_event': event}):
            result = capture_command([
                sys.executable, '-c',
                'import sys,time,pathlib;time.sleep(10);'
                'pathlib.Path(sys.argv[1]).write_text("bad")',
                str(marker),
            ])
    finally:
        timer.cancel()
        timer.join()
    assert result is None
    assert time.monotonic() - started < 5
    assert not marker.exists()


def test_repeated_invocations_do_not_reuse_log(tmp_path):
    source = tmp_path / 'a.gz'
    with gzip.open(source, 'wb') as target:
        target.write(b'x' * 500)
    log = tmp_path / 'operation.log'
    runner = separated_cli_runner()
    first = runner.invoke(app, ['repack', str(source), '--log-file', str(log)])
    assert first.exit_code == 0, first.output
    logged = log.read_text()
    assert 'File ' in logged
    second = runner.invoke(app, ['repack', str(source), '--json'])
    assert second.exit_code == 0
    json.loads(second.stdout)
    assert log.read_text() == logged
