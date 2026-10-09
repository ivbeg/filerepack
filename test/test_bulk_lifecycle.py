"""Bounded discovery, fatal-dispatch draining, and real spawn agreement."""

import json
import threading
from concurrent.futures import Future
from contextlib import nullcontext

import pytest
from typer.testing import CliRunner

from filerepack.__main__ import _BulkAcc, _run_bulk_jobs, app


@pytest.mark.parametrize('failure', ['none', 'scan', 'submit', 'interrupt', 'worker'])
def test_inflight_bound_and_drain(tmp_path, monkeypatch, failure):
    import filerepack.__main__ as cli
    acc = _BulkAcc(False, False)
    pending, yielded, completed, written = [], 0, 0, []

    def scan():
        nonlocal yielded
        for index in range(10000):
            if yielded == 4 and failure == 'scan':
                raise OSError('scan failed')
            assert yielded - completed <= 4
            yielded += 1
            yield str(tmp_path / f'{index}.json')

    class Pool:
        def submit(self, fn, job):
            if len(pending) == 2 and failure == 'submit':
                raise OSError('pool broken')
            future = Future()
            future.set_running_or_notify_cancel()
            pending.append((future, job['filepath']))
            return future

    def wait(futures, **kwargs):
        nonlocal completed
        if completed == 0 and failure == 'interrupt':
            completed += 1
            raise KeyboardInterrupt
        future, path = next((future, path) for future, path in pending if future in futures)
        if failure == 'worker' and completed == 0:
            future.set_exception(ValueError('worker failed'))
        else:
            # A running task may publish just as another task fails. Drain must
            # retain this completed outcome even after cancellation was signalled.
            from pathlib import Path
            Path(path).write_text('{}')
            written.append(path)
            future.set_result({'file': path, 'status': 'replaced', 'published': True})
        completed += 1
        return {future}, set(futures) - {future}

    monkeypatch.setattr(cli, '_reserved_job', lambda path, base, *args: ({'filepath': path}, None))
    monkeypatch.setattr(cli, 'Manager', lambda: nullcontext(
        type('Manager', (), {'Event': staticmethod(threading.Event)})()))
    monkeypatch.setattr(cli, 'ProcessPoolExecutor', lambda **kw: nullcontext(Pool()))
    monkeypatch.setattr(cli, 'wait', wait)
    _run_bulk_jobs(scan(), {}, 2, acc, False, 1)
    rows = list(acc.results)
    assert {row['file'] for row in rows if row.get('published')} == set(written)
    if failure == 'none':
        assert acc.scan_complete and len(rows) == 10000
    else:
        assert acc.abort and not acc.scan_complete
        assert len(rows) == yielded
        assert all(future.done() for future, _ in pending)
    acc.results.close()


@pytest.mark.parametrize('jobs', [1, 2])
def test_serial_and_spawn_account_for_backups_and_reports(tmp_path, jobs):
    source = tmp_path / 'input'
    source.mkdir()
    for index in range(6):
        (source / f'{index}.json').write_text(' { "value": 1 } ')
    report = source / 'audit.jsonl'
    result = CliRunner().invoke(app, ['bulk', str(source), '--jobs', str(jobs), '--backup',
                                    '--report', str(report), '--json'])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload['summary']['scan_complete']
    assert payload['summary']['counts'] == {'replaced': 6}
    assert len(list(source.glob('*.bak'))) == 6
    assert len(payload['files']) == 6
    assert len(report.read_text().splitlines()) == 8
