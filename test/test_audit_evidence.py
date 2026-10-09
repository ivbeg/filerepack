import gzip
import json
import subprocess
import sys
import time

from filerepack.evidence import add, command, evidence_scope
from filerepack.format_support import format_scope, run_operation
from filerepack.reports import AuditReport
from filerepack.verification import validate_output


def test_evidence_bounds_and_nested_collection():
    with evidence_scope() as rows:
        with evidence_scope():
            for _ in range(10000):
                command('/private/tools/qpdf')
            for index in range(1000):
                add({'type': 'fixture', 'index': index})
    assert rows[0]['count'] == 10000
    assert len(rows) == 129 and rows[-1]['type'] == 'truncated'


def test_rejected_validator_and_tool_version_in_report(tmp_path, monkeypatch):
    candidate = tmp_path / 'invalid.json'
    candidate.write_text('{bad')
    monkeypatch.setattr('filerepack.tools.probe_version', lambda *args: 'qpdf fixture-version')
    with evidence_scope() as rows:
        command(sys.executable)
        add({'type': 'tool', 'executable': sys.executable, 'key': 'qpdf', 'version': None})
        assert not validate_output(str(candidate), 'json').ok
    target = tmp_path / 'report.jsonl'
    sink = AuditReport(str(target), root=str(tmp_path))
    sink.item({'file': str(candidate), 'status': 'failed', 'published': False,
               'details': {'evidence': rows}})
    sink.finish({'complete': True})
    event = json.loads(target.read_text().splitlines()[1])
    evidence = event['details']['evidence']
    assert any(row.get('version') == 'qpdf fixture-version' for row in evidence)
    assert any(row['type'] == 'validation' and not row['valid'] and row['reason']
               for row in evidence)


def test_worker_evidence_survives_process_boundary(tmp_path):
    source = tmp_path / 'source.gz'
    source.write_bytes(gzip.compress(b'worker evidence'))
    with evidence_scope() as rows, format_scope({}):
        result = run_operation('stream-native', 'fingerprint', str(source),
                               options={'stream_codec': 'gz'})
    assert result['ok']
    assert any(row['type'] == 'worker' and row['action'] == 'fingerprint' and row['valid']
               for row in rows)


def test_bulk_spool_failure_preserves_completed_rows_and_stops_submission(monkeypatch):
    from filerepack.__main__ import _BulkAcc
    acc = _BulkAcc(False, True)
    acc.results.stream.rollover()
    acc.consume({'file': 'first.json', 'status': 'replaced', 'original_size': 10,
                 'final_size': 5, 'published': True}, 'first.json')
    original_write = acc.results.stream.write

    def disk_full(value):
        original_write(value[:4])
        raise OSError('disk full')

    monkeypatch.setattr(acc.results.stream, 'write', disk_full)
    acc.consume({'file': 'second.json', 'status': 'replaced', 'original_size': 10,
                 'final_size': 6, 'published': True}, 'second.json')
    acc.consume({'file': 'third.json', 'status': 'cancelled'}, 'third.json')
    assert acc.abort and acc.sink_error
    assert acc.processed == 2 and acc.skipped == 1
    assert [row['file'] for row in acc.results] == ['first.json', 'second.json', 'third.json']
    assert len(acc.results) == 3
    acc.results.close()


def test_killed_report_recovers_complete_lines_before_partial_tail(tmp_path):
    report, ready = tmp_path / 'killed.jsonl', tmp_path / 'ready'
    script = ('import pathlib,sys,time;from filerepack.reports import AuditReport;'
              'r=AuditReport(sys.argv[1],root=sys.argv[3]);'
              'r.item({"file":"input.json","status":"replaced","published":True});'
              'r.stream.write("{\\\"record_type\\\":");r.stream.flush();'
              'pathlib.Path(sys.argv[2]).touch();time.sleep(30)')
    process = subprocess.Popen([sys.executable, '-c', script, str(report), str(ready),
                                str(tmp_path)])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    lines = report.read_text().splitlines()
    events = [json.loads(line) for line in lines[:-1]]
    assert [event['record_type'] for event in events] == ['run', 'item']
    assert events[1]['published']
    assert lines[-1] == '{"record_type":'


def test_all_terminal_states_and_nested_predictions_are_auditable(tmp_path):
    report = tmp_path / 'all.jsonl'
    sink = AuditReport(str(report), root=str(tmp_path))
    statuses = ['replaced', 'unchanged', 'skipped', 'unsupported', 'failed',
                'predicted', 'cancelled']
    for status in statuses:
        sink.item({'file': status + '.zip', 'status': status, 'published': status == 'replaced',
                   'members': [{'member': 'nested.json', 'status': 'predicted',
                                'published': False, 'original_size': 20, 'final_size': 10}]})
    sink.finish({'complete': False, 'counts': {status: 1 for status in statuses}})
    events = [json.loads(line) for line in report.read_text().splitlines()]
    assert [row['status'] for row in events if row['record_type'] == 'item'] == statuses
    assert all(not row['published'] and row['parent_id'] for row in events
               if row['record_type'] == 'member')
    assert not events[-1]['complete']
