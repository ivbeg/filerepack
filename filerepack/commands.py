"""Shared, typed argv execution; subprocesses never mutate the caller's cwd."""

import logging
import os
import subprocess
import threading
import time
from contextlib import ExitStack
from typing import Any, Callable, List, Optional, cast
from .outcomes import record
from .evidence import command


def _cancelable_run(cmd: List[str], **kwargs: object) -> subprocess.CompletedProcess:
    """Own the process tree and bound diagnostics, RSS, scratch and wall time."""
    from .format_support import (
        current_budget, check_cancelled, FormatLimit, _terminate, tool_environment,
    )
    command(cmd[0])
    budget = current_budget()
    if budget is None:
        return cast(subprocess.CompletedProcess[Any],
                    subprocess.run(cmd, **kwargs))  # type: ignore[call-overload]
    import psutil
    import tempfile
    timeout = float(kwargs.pop('timeout', 3600))  # type: ignore[arg-type]
    check_cancelled()
    capture = kwargs.pop('capture_output', False)
    text_mode = bool(kwargs.pop('text', False))
    encoding = str(kwargs.pop('encoding', 'utf-8'))
    errors = str(kwargs.pop('errors', 'replace'))
    with ExitStack() as stack:
        stdout = stack.enter_context(tempfile.TemporaryFile()) if capture else None
        stderr = stack.enter_context(tempfile.TemporaryFile()) if (
            capture or kwargs.get('stderr') == subprocess.PIPE
        ) else None
        if stdout is not None:
            kwargs['stdout'] = stdout
        if stderr is not None:
            kwargs['stderr'] = stderr
        kwargs.setdefault('env', tool_environment())
        process = subprocess.Popen(cmd, start_new_session=os.name == 'posix',
                                   **kwargs)  # type: ignore[call-overload]
        monitor = psutil.Process(process.pid)
        started = time.monotonic()
        try:
            while process.poll() is None:
                budget.check_scratch()
                if time.monotonic() - started >= timeout:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                for stream in (stdout, stderr):
                    if stream is not None and os.fstat(stream.fileno()).st_size > 1024 * 1024:
                        raise FormatLimit('command diagnostic/output capture exceeds 1 MiB')
                try:
                    rss = monitor.memory_info().rss + sum(
                        child.memory_info().rss for child in monitor.children(recursive=True)
                    )
                    if rss > budget.limits.memory:
                        raise FormatLimit('owned command process-tree RSS budget exceeded')
                except psutil.NoSuchProcess:
                    pass
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
            budget.check_scratch()
            values: List[Any] = []
            for stream in (stdout, stderr):
                if stream is None:
                    values.append(None)
                    continue
                stream.seek(0)
                value = stream.read(1024 * 1024 + 1)
                if len(value) > 1024 * 1024:
                    raise FormatLimit('command diagnostic/output capture exceeds 1 MiB')
                values.append(value.decode(encoding, errors) if text_mode else value)
            return subprocess.CompletedProcess(cmd, process.returncode, *values)
        finally:
            if process.poll() is None:
                _terminate(process, monitor)


def expand_globs(cmd: List[str], cwd: Optional[str] = None) -> List[str]:
    """Expand only a bare '*'; filenames with wildcard characters remain literal."""
    cwd = cwd if cwd is not None else os.getcwd()
    expanded: List[str] = []
    for arg in cmd:
        if arg == '*':
            matches = sorted(os.listdir(cwd))
            expanded.extend(matches or [arg])
        else:
            expanded.append(arg)
    return expanded


def capture_command(
    cmd: List[str], debug: bool = False, cwd: Optional[str] = None, *, timeout: int = 3600,
) -> Optional[subprocess.CompletedProcess[str]]:
    """Capture even an unsuccessful probe; launch/timeout failures return None."""
    from .format_support import OperationCancelled, FormatLimit
    cmd = expand_globs(cmd, cwd)
    if debug:
        logging.info('command: %s', ' '.join(cmd))
    try:
        result = _cancelable_run(cmd, capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', cwd=cwd, timeout=timeout)
        return result
    except (OSError, subprocess.TimeoutExpired, OperationCancelled, FormatLimit) as exc:
        record('skipped' if isinstance(exc, FormatLimit) else 'failed',
               'resource_limit' if isinstance(exc, FormatLimit) else 'command_error', str(exc))
        if debug:
            logging.warning('command exception: %s', str(exc))
    return None


def run_command(
    cmd: List[str], quiet: bool = False, debug: bool = False, cwd: Optional[str] = None,
) -> Optional[subprocess.CompletedProcess[str]]:
    """Capture a successful encoder; quiet remains accepted for helper compatibility."""
    result = capture_command(cmd, debug=debug, cwd=cwd)
    if result is not None:
        if result.returncode == 0:
            return result
        if debug:
            logging.warning('command failed with return code %d: %s',
                            result.returncode, ' '.join(cmd))
        record('failed', 'encoder_exit', 'Encoder exited with code ' + str(result.returncode))
    return None


def run_to_file(
    cmd: List[str], out_path: str, debug: bool = False, *, stdin_path: Optional[str] = None,
) -> bool:
    from .format_support import OperationCancelled, FormatLimit
    if debug:
        logging.info('command: %s', ' '.join(cmd))
    try:
        with ExitStack() as stack:
            target = stack.enter_context(open(out_path, 'wb'))
            source = stack.enter_context(open(stdin_path, 'rb')) if stdin_path else None
            result = _cancelable_run(cmd, stdin=source, stdout=target,
                                     stderr=subprocess.PIPE, timeout=3600)
        ok = result.returncode == 0 and os.path.getsize(out_path) > 0
        if not ok:
            record('failed', 'encoder_exit', 'Encoder failed or produced an empty candidate')
        return ok
    except (OSError, subprocess.TimeoutExpired, OperationCancelled, FormatLimit) as exc:
        record('skipped' if isinstance(exc, FormatLimit) else 'failed',
               'resource_limit' if isinstance(exc, FormatLimit) else 'command_error', str(exc))
        if debug:
            logging.warning('command exception: %s', str(exc))
    return False


def _check_decoder(budget: Any, monitor: Any) -> None:
    import psutil
    from .format_support import FormatLimit
    budget.check_scratch()
    try:
        resident = monitor.memory_info().rss + sum(
            item.memory_info().rss for item in monitor.children(recursive=True)
        )
        if resident > budget.limits.memory:
            raise FormatLimit('verifier/decoder process-tree RSS budget exceeded')
    except psutil.NoSuchProcess:
        pass


def _consume_stdout(process: subprocess.Popen, failed: threading.Event,
                    consume: Callable[[bytes], None], maximum: int) -> None:
    size = 0
    assert process.stdout is not None
    output = process.stdout
    try:
        for block in iter(lambda: output.read(65536), b''):
            size += len(block)
            if size > maximum:
                raise ValueError('Verifier output limit exceeded')
            consume(block)
    except Exception:
        failed.set()
        try:
            process.kill()
        except OSError:
            pass


def consume_command(
    cmd: List[str], consume: Callable[[bytes], None], *,
    max_output: int = 512 * 1024 * 1024, timeout: int = 120,
) -> bool:
    """Drain a verifier/decoder with bounded output and a portable timeout.

    Reading runs separately so a stalled pipe cannot bypass the process timeout.
    Verifier diagnostics are discarded, avoiding unbounded stderr capture.
    """
    from .format_support import current_budget, FormatLimit, _terminate, tool_environment
    budget = current_budget()
    failed = threading.Event()
    command(cmd[0])
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   start_new_session=os.name == 'posix', env=tool_environment())
    except OSError:
        return False
    monitor = None
    if budget:
        import psutil
        monitor = psutil.Process(process.pid)
    assert process.stdout is not None
    output = process.stdout

    reader = threading.Thread(target=_consume_stdout,
                              args=(process, failed, consume, max_output), daemon=True)
    reader.start()
    started = time.monotonic()
    try:
        while process.poll() is None:
            if budget:
                _check_decoder(budget, monitor)
            if failed.is_set() or time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(cmd, timeout)
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        code = process.returncode
    except (OSError, subprocess.TimeoutExpired, FormatLimit) as exc:
        failed.set()
        if isinstance(exc, FormatLimit):
            record('skipped', 'resource_limit', str(exc))
        _terminate(process, monitor)
        code = process.returncode
    finally:
        reader.join(timeout=5)
        if reader.is_alive():
            failed.set()
        if failed.is_set():
            _terminate(process, monitor)
            reader.join(timeout=5)
        if not reader.is_alive():
            output.close()
    return code == 0 and not failed.is_set()


def capture_prefix(cmd: List[str], maximum: int = 512, timeout: float = 2.0) -> bytes:
    """Read a bounded prefix and terminate the owned producer, including descendants."""
    import psutil
    from .format_support import current_budget, Budget, FormatLimits, _terminate, tool_environment
    budget = current_budget() or Budget(FormatLimits(seconds=timeout))
    command(cmd[0])
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               start_new_session=os.name == 'posix', env=tool_environment())
    monitor = psutil.Process(process.pid)
    result: List[bytes] = []
    ready = threading.Event()
    assert process.stdout is not None
    output = process.stdout

    def read() -> None:
        try:
            result.append(output.read(maximum))
        finally:
            ready.set()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    started = time.monotonic()
    try:
        while not ready.wait(0.05):
            _check_decoder(budget, monitor)
            if time.monotonic() - started >= timeout:
                raise subprocess.TimeoutExpired(cmd, timeout)
        budget.check()
        return result[0] if result else b''
    finally:
        _terminate(process, monitor)
        reader.join(timeout=5)
        if not reader.is_alive():
            output.close()


def capture_bytes(
    cmd: List[str], *, max_output: int = 16 * 1024 * 1024, timeout: int = 120,
) -> Optional[bytes]:
    output = bytearray()
    if not consume_command(cmd, output.extend, max_output=max_output, timeout=timeout):
        return None
    return bytes(output)


def check_command(cmd: List[str], *, timeout: int = 120) -> bool:
    return consume_command(cmd, lambda block: None, max_output=1024 * 1024, timeout=timeout)
