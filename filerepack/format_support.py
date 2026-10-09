"""Resource accounting and isolated execution for preserving scientific formats.

Only operation-owned child processes are monitored/terminated. Optional native
libraries are imported in that child, never by file detection or user object hooks.
"""

import bz2
import json
import logging
import lzma
import os
import signal
import subprocess
import sys
import tempfile
import time
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, Optional, cast

from .models import PackResult


class UnsupportedFormat(ValueError):
    """A structure/reader property is outside the verified profile."""


class FormatLimit(ValueError):
    """The root operation exhausted a declared resource budget."""


class OperationCancelled(FormatLimit):
    """A coordinator stopped the operation before publication."""


@dataclass(frozen=True)
class FormatLimits:
    decoded: int = 512 * 1024 * 1024
    memory: int = 256 * 1024 * 1024
    scratch: int = 2 * 1024 * 1024 * 1024
    nodes: int = 100000
    depth: int = 16
    seconds: float = 120.0

    @classmethod
    def from_options(cls, options: Dict[str, Any]) -> "FormatLimits":
        names = {
            "decoded": "format_max_decoded_bytes",
            "memory": "format_max_memory_bytes",
            "scratch": "format_max_scratch_bytes",
            "nodes": "format_max_nodes",
            "depth": "format_max_depth",
            "seconds": "format_timeout",
        }
        defaults = asdict(cls())
        return cls(**{key: options.get(name, defaults[key]) for key, name in names.items()})


class Budget:
    def __init__(self, limits: FormatLimits):
        self.limits = limits
        self.started = time.monotonic()
        self.decoded = 0
        self.written = 0
        self.nodes = 0
        self.interrupted = False
        self.scratch_paths: set = set()
        self.peak_scratch = 0

    def check(self) -> None:
        check_cancelled()
        if self.interrupted:
            raise FormatLimit("format budget accounting incomplete after worker termination")
        if time.monotonic() - self.started >= self.limits.seconds:
            raise FormatLimit("format operation time budget exceeded")

    def consume(self, *, decoded: int = 0, written: int = 0, nodes: int = 0) -> None:
        self.check()
        self.decoded += decoded
        self.written += written
        self.nodes += nodes
        if self.decoded > self.limits.decoded:
            raise FormatLimit("cumulative format decoded-byte budget exceeded")
        if self.written > self.limits.scratch:
            raise FormatLimit("cumulative format scratch-byte budget exceeded")
        if self.nodes > self.limits.nodes:
            raise FormatLimit("cumulative format graph/record budget exceeded")

    def memory(self, amount: int) -> None:
        self.check()
        if amount > self.limits.memory // 2:
            raise FormatLimit("format buffer exceeds memory budget")

    def depth(self, amount: int) -> None:
        self.check()
        if amount > self.limits.depth:
            raise FormatLimit('root-input nesting depth budget exceeded')

    def remaining(self) -> Dict[str, Any]:
        self.check()
        result = asdict(self.limits)
        result.update(
            decoded=self.limits.decoded - self.decoded,
            scratch=self.limits.scratch - self.written,
            nodes=self.limits.nodes - self.nodes,
            seconds=self.limits.seconds - (time.monotonic() - self.started),
        )
        return result

    def own(self, path: str) -> None:
        self.scratch_paths.add(os.path.abspath(path))

    def check_scratch(self) -> None:
        self.check()
        total = 0
        parents = [path for path in self.scratch_paths if os.path.isdir(path)]
        for path in self.scratch_paths:
            if any(path != parent and os.path.commonpath((path, parent)) == parent
                   for parent in parents):
                continue
            if os.path.isdir(path):
                total += _scratch_size(path)
            elif os.path.isfile(path):
                total += os.path.getsize(path)
        self.peak_scratch = max(self.peak_scratch, total)
        if total > self.limits.scratch:
            raise FormatLimit('live operation scratch-byte budget exceeded')


_BUDGET: ContextVar[Optional[Budget]] = ContextVar("filerepack_format_budget", default=None)
_OPTIONS: ContextVar[Dict[str, Any]] = ContextVar("filerepack_format_options", default={})


def current_budget() -> Optional[Budget]:
    return _BUDGET.get()


def own_scratch(path: str) -> None:
    budget = current_budget()
    if budget is not None:
        budget.own(path)


def tool_threads() -> int:
    return int(_OPTIONS.get().get('tool_threads', 1))


def current_options() -> Dict[str, Any]:
    return dict(_OPTIONS.get())


def tool_environment() -> Dict[str, str]:
    environment = dict(os.environ)
    threads = str(tool_threads())
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        environment[key] = threads
    return environment


def check_cancelled() -> None:
    event = _OPTIONS.get().get('_cancel_event')
    if event is not None and event.is_set():
        from .outcomes import record
        record('cancelled', 'cancelled', 'Operation cancelled before publication')
        raise OperationCancelled('Operation cancelled')


def cancellation_event() -> Any:
    return _OPTIONS.get().get('_cancel_event')


@contextmanager
def format_scope(options: Dict[str, Any]) -> Iterator[Budget]:
    parent = _BUDGET.get()
    if parent is not None:
        yield parent
        return
    budget = Budget(FormatLimits.from_options(options))
    token = _BUDGET.set(budget)
    option_token = _OPTIONS.set(options)
    try:
        yield budget
    finally:
        _BUDGET.reset(token)
        _OPTIONS.reset(option_token)


def read_small(path: str, budget: Budget) -> bytes:
    size = os.path.getsize(path)
    # Retain space for decoded bytes, encoder dictionaries and native-reader RSS.
    if size > budget.limits.memory // 8:
        raise FormatLimit("byte-parser input exceeds its bounded buffer profile")
    budget.check()
    with open(path, "rb") as source:
        data = source.read(size + 1)
    if len(data) != size:
        raise ValueError("source length changed while reading")
    return data


def inflate(data: bytes, budget: Budget, codec: str = "zlib", *,
            maximum: Optional[int] = None) -> bytes:
    available = min(budget.limits.memory // 8, budget.limits.decoded - budget.decoded)
    maximum = available if maximum is None else min(available, maximum)
    if maximum < 0:
        raise FormatLimit("decoded-byte budget exhausted")
    if codec in ("zlib", "gzip", "raw-deflate"):
        bits = {"zlib": 15, "gzip": 31, "raw-deflate": -15}[codec]
        decoder: Any = zlib.decompressobj(bits)
    elif codec == "bzip2":
        decoder = bz2.BZ2Decompressor()
    elif codec == "xz":
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=budget.limits.memory // 2)
    else:
        raise UnsupportedFormat("unknown compression envelope: " + codec)
    raw = decoder.decompress(data, max_length=maximum + 1)
    if len(raw) > maximum:
        raise FormatLimit("decoded payload exceeds bounded parser budget")
    if not decoder.eof or decoder.unused_data or getattr(decoder, "unconsumed_tail", b""):
        raise ValueError("incomplete compression envelope or trailing data")
    budget.consume(decoded=len(raw))
    return bytes(raw)


def write_bytes(path: str, data: bytes, budget: Budget) -> None:
    budget.consume(written=len(data))
    with open(path, "wb") as target:
        target.write(data)


def unchanged(path: str, reason: str, details: Optional[Dict[str, Any]] = None) -> PackResult:
    size = os.path.getsize(path)
    return PackResult(path, size, size, 0.0, replaced=False, reason=reason, details=details or {})


def _terminate(process: subprocess.Popen, monitor: Any) -> None:
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # On macOS the group may already have disappeared while its leader
            # is an unreaped zombie. Refresh before attempting a direct kill.
            if process.poll() is None:
                process.kill()
    else:
        try:
            for child in monitor.children(recursive=True):
                child.kill()
            monitor.kill()
        except Exception:
            process.kill()
    process.wait()


def _scratch_size(path: str) -> int:
    paths = (os.path.join(root, name) for root, _, names in os.walk(path) for name in names)
    total = 0
    for name in paths:
        try:
            total += os.path.getsize(name)
        except FileNotFoundError:
            # The owned writer atomically moves completed chunks between its
            # private directories. Account for their new name on the next scan.
            continue
    return total


def _candidate_scratch(candidate: str, options: Dict[str, Any]) -> int:
    directory = options.get('_scratch_directory')
    if directory or os.path.isdir(candidate):
        return _scratch_size(directory or os.path.dirname(candidate))
    try:
        return os.path.getsize(candidate)
    except FileNotFoundError:
        return 0


def _worker_limits(budget: Budget, deadline: Optional[float]) -> Dict[str, Any]:
    remaining = budget.remaining()
    if deadline is not None:
        remaining['seconds'] = min(remaining['seconds'], deadline - time.monotonic())
        if remaining['seconds'] <= 0:
            raise FormatLimit('format operation deadline exceeded')
    return remaining


def run_operation(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    *, deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """Run a passive operation with cumulative limits and a hard RSS/time supervisor."""
    try:
        import psutil
    except ImportError as exc:
        extra = 'ole-recompress' if kind in ('ppt-ole', 'officeart', 'hwp-ole', 'ole-embedded',
                                            'ole-dedup') else 'scientific'
        raise UnsupportedFormat(
            f"format isolation requires filerepack[{extra}] (psutil)"
        ) from exc
    options = _OPTIONS.get() if options is None else options
    with format_scope(options) as budget:
        remaining = _worker_limits(budget, deadline)
        worker_started, peak_rss = time.monotonic(), 0
        request = {
            "kind": kind,
            "action": action,
            "source": os.path.abspath(source),
            "candidate": os.path.abspath(candidate) if candidate else None,
            "limits": remaining,
            "options": {key: value for key, value in options.items() if not key.startswith("_")},
            "base_depth": options.get('_optimization_depth', 0),
        }
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                [sys.executable, "-m", "filerepack.format_worker"],
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=errors,
                env=tool_environment(),
                start_new_session=os.name != "nt",
            )
            monitor = psutil.Process(process.pid)
            try:
                assert process.stdin is not None
                process.stdin.write(json.dumps(request).encode())
                process.stdin.close()
                while process.poll() is None:
                    budget.check_scratch()
                    if time.monotonic() - worker_started >= remaining["seconds"]:
                        raise FormatLimit("format worker deadline exceeded")
                    event = options.get("_cancel_event")
                    if event is not None and event.is_set():
                        raise FormatLimit("format operation cancelled")
                    try:
                        children = [monitor, *monitor.children(recursive=True)]
                        resident = sum(
                            child.memory_info().rss for child in children if child.is_running()
                        )
                    except psutil.NoSuchProcess:
                        resident = 0
                    if resident > remaining["memory"]:
                        raise FormatLimit("format worker memory budget exceeded")
                    peak_rss = max(peak_rss, resident)
                    if candidate:
                        scratch = _candidate_scratch(candidate, options)
                        if scratch > remaining["scratch"]:
                            raise FormatLimit("format worker scratch budget exceeded")
                    if output.tell() > 65536 or errors.tell() > 1024 * 1024:
                        raise FormatLimit("format worker diagnostic budget exceeded")
                    time.sleep(0.02)
                output.seek(0)
                payload = output.read(65537)
                if len(payload) > 65536 or process.returncode:
                    budget.interrupted = True
                    raise UnsupportedFormat("format worker failed or exceeded control-output limit")
                try:
                    result = json.loads(payload)
                except ValueError as exc:
                    budget.interrupted = True
                    raise UnsupportedFormat("invalid format worker control output") from exc
                usage = result.get("usage", {})
                from .evidence import add
                for evidence in result.get('evidence', []):
                    add(evidence)
                add({'type': 'worker', 'kind': kind, 'action': action,
                     'valid': bool(result.get('ok')), 'reason': result.get('reason', '')[:500]})
                budget.consume(
                    decoded=usage.get("decoded", 0),
                    written=usage.get("written", 0),
                    nodes=usage.get("nodes", 0),
                )
                if not result.get("ok"):
                    error = (FormatLimit if result.get('limited') else
                             UnsupportedFormat if result.get('unsupported') else ValueError)
                    raise error(result.get("reason", "format verification failed"))
                result.setdefault("usage", {}).update(
                    peak_worker_rss_bytes=peak_rss,
                    seconds=time.monotonic() - worker_started,
                )
                return cast(Dict[str, Any], result)
            finally:
                if process.poll() is None:
                    # A terminated worker cannot report its cumulative work. Do
                    # not give a later nested adapter an unmeasured fresh budget.
                    budget.interrupted = True
                    _terminate(process, monitor)


def pack_format(kind: str, filepath: str, options: Dict[str, Any]) -> PackResult:
    """Shared ordinary-file lifecycle; the worker never publishes user destinations."""
    from . import candidates as tx
    from .validation import validate_options

    validate_options(options)
    temp: Optional[str] = None
    with format_scope(options):
        try:
            if options.get("dryrun"):
                info = run_operation(kind, "inspect", filepath, options=options)
                return unchanged(
                    filepath, "dry-run: inspected without encoding", info.get("details")
                )
            temp = tx.make_temp("." + kind)
            info = run_operation(kind, "rewrite", filepath, temp, options)
            if not info.get("changed"):
                return unchanged(
                    filepath,
                    info.get("reason", "no compatible smaller candidate"),
                    info.get("details"),
                )
            result = tx.commit_output(
                temp,
                filepath,
                os.path.getsize(filepath),
                verify=kind,
                lossless=True,
                **tx.commit_kwargs(**options),
            )
            if result is None:
                result = unchanged(filepath, "candidate validation/publication refused")
                result.status, result.reason_code = 'failed', 'candidate_refused'
                return result
            result.details = info.get("details", {})
            result.reason = (
                (
                    "experimental: exact preservation verified; native-reader gate pending"
                    if result.details.get("experimental")
                    else "verified"
                )
                if (result.replaced)
                else "no candidate meets size policy"
            )
            return result
        except (ValueError, OSError, ImportError) as exc:
            logging.warning("%s optimization skipped: %s", kind, exc)
            result = unchanged(filepath, str(exc))
            if isinstance(exc, (InterruptedError, OperationCancelled)):
                result.status, result.reason_code = 'cancelled', 'cancelled'
            elif isinstance(exc, FormatLimit):
                result.status, result.reason_code = 'skipped', 'resource_limit'
            elif isinstance(exc, (UnsupportedFormat, ImportError)):
                result.status, result.reason_code = 'unsupported', 'unsupported_profile'
            else:
                result.status, result.reason_code = 'failed', 'invalid_input'
            return result
        finally:
            tx.remove_quietly(temp)


def pack_inspection_only(kind: str, filepath: str, options: Dict[str, Any]) -> PackResult:
    """Return bounded passive format details without registering a writer."""
    from .validation import validate_options

    validate_options(options)
    try:
        with format_scope(options):
            result = run_operation(kind, "inspect", filepath, options=options)
    except (OSError, ValueError, ImportError) as exc:
        return unchanged(
            filepath,
            str(exc),
            {"format": kind, "inspection_only": True, "writer_registered": False},
        )
    details = result.get("details", {})
    details.update(inspection_only=True, writer_registered=False)
    if not result.get("ok"):
        return unchanged(filepath, result.get("reason", "format inspection failed"), details)
    return unchanged(
        filepath,
        "inspection only: no qualified lossless same-format writer",
        details,
    )
