"""Coordinator-owned bounded outcome spools and local audit reports."""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
import sys
from typing import Any, Dict, Iterator, Optional, TextIO, cast


class ResultSpool:
    def __init__(self) -> None:
        self.stream = cast(TextIO, tempfile.SpooledTemporaryFile(max_size=262144, mode='w+',
                                                                encoding='utf-8'))
        self.count = 0
        self.committed = 0
        self.failed = False
        self.drained: list = []

    def append(self, value: Dict[str, Any]) -> None:
        if self.failed:
            raise OSError('Result spool is unavailable; scheduling must stop')
        try:
            self.stream.seek(0, os.SEEK_END)
            self.stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n')
            self.stream.flush()
        except OSError:
            self.failed = True
            raise
        self.committed = self.stream.tell()
        self.count += 1

    def preserve_drained(self, value: Dict[str, Any]) -> None:
        """Keep only the bounded in-flight jobs after the coordinator stops submission."""
        self.drained.append(value)
        self.count += 1

    def __len__(self) -> int:
        return self.count

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        if self.failed and getattr(self.stream, '_rolled', False):
            # A new reader bypasses the failed writer's buffered partial tail.
            with os.fdopen(os.dup(self.stream.fileno()), encoding='utf-8') as reader:
                reader.seek(0)
                while reader.tell() < self.committed:
                    yield json.loads(reader.readline())
            yield from self.drained
            return
        self.stream.flush()
        self.stream.seek(0)
        while self.stream.tell() < self.committed:
            yield json.loads(self.stream.readline())
        yield from self.drained

    def close(self) -> None:
        try:
            self.stream.close()
        except OSError:
            if not self.failed:
                raise


def identity(path: str) -> str:
    return os.path.realpath(os.path.abspath(path)).casefold()


class AuditReport:
    def __init__(self, path: str, *, root: str, format: Optional[str] = None,
                 paths: str = 'absolute', options: Optional[Dict[str, Any]] = None) -> None:
        self.path = os.path.abspath(path)
        self.root = os.path.abspath(root)
        self.format = format or ('jsonl' if path.endswith('.jsonl') else 'json')
        if (self.format not in ('json', 'jsonl') or
                paths not in ('absolute', 'relative', 'redacted')):
            raise ValueError('report format must be json|jsonl; paths absolute|relative|redacted')
        if os.path.lexists(self.path):
            raise FileExistsError('Report destination already exists')
        if not os.path.isdir(os.path.dirname(self.path)):
            raise ValueError('Report parent directory must already exist')
        self.paths, self.run_id = paths, str(uuid.uuid4())
        self.partial = self.path + '.partial-' + self.run_id + '.jsonl'
        self.closed = False
        self.stream = open(self.path if self.format == 'jsonl' else self.partial, 'x',
                           encoding='utf-8')
        try:
            from . import __version__
            self.write({'record_type': 'run', 'schema_version': 1, 'run_id': self.run_id,
                        'paths': paths, 'options': options or {}, 'root': self.root,
                        'package_version': __version__, 'python_version': sys.version.split()[0],
                        'started_utc': datetime.now(timezone.utc).isoformat()})
        except BaseException:
            self.stream.close()
            raise

    @property
    def protected_paths(self) -> tuple:
        return self.path, self.partial

    def _scrub(self, value: Any, key: str = '') -> Any:
        path_fields = ('file', 'source', 'destination', 'output_file', 'member', 'root',
                       'backup_dir', 'output_dir')
        if self.paths == 'redacted':
            if key in ('options', 'effective_options'):
                return {name: item for name, item in value.items()
                        if isinstance(item, (bool, int, float)) or
                        name in ('profile', 'profile_version', 'video_mode')}
            if key in ('reason', 'error', 'message'):
                return 'Diagnostic redacted; see reason_code'
            if key == 'details':
                return {}
            if key in path_fields and isinstance(value, str):
                return 'item-' + hashlib.sha256((self.run_id + value).encode()).hexdigest()[:16]
        if self.paths == 'relative' and key in path_fields and isinstance(value, str):
            source, separator, member = value.partition('!/')
            if os.path.isabs(source):
                source = os.path.relpath(source, self.root)
            return source + separator + member
        if isinstance(value, dict):
            return {k: self._scrub(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scrub(item, key) for item in value]
        return value

    def write(self, value: Dict[str, Any]) -> None:
        self.stream.write(json.dumps(self._scrub(value), ensure_ascii=True, allow_nan=False) + '\n')
        self.stream.flush()

    def item(self, value: Dict[str, Any]) -> None:
        from .evidence import report_evidence
        value = dict(value)
        details = dict(value.get('details', {}))
        if self.paths != 'redacted' and 'evidence' in details:
            details['evidence'] = report_evidence(details['evidence'])
        value['details'] = details
        source = value.get('source', value.get('file', ''))
        item_id = hashlib.sha256((self.run_id + source).encode())
        row = {**value, 'schema_version': 1, 'record_type': 'item', 'run_id': self.run_id,
               'item_id': item_id.hexdigest()[:24]}
        self.write(row)
        for member in value.get('members', []):
            self.write({**member, 'schema_version': 1, 'record_type': 'member',
                        'parent_id': row['item_id'], 'run_id': self.run_id})

    def finish(self, summary: Dict[str, Any]) -> None:
        if self.closed:
            return
        try:
            self.write({**summary, 'schema_version': 1, 'record_type': 'summary'})
            os.fsync(self.stream.fileno())
            self.stream.close()
            if self.format == 'json':
                self._finalize_json()
        finally:
            self.closed = True
            self.stream.close()

    def _finalize_json(self) -> None:
        descriptor, candidate = tempfile.mkstemp(prefix='.filerepack-report-',
                                                dir=os.path.dirname(self.path))
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as target, open(
                self.partial, encoding='utf-8'
            ) as source:
                target.write('{"schema_version":1,"events":[')
                first = True
                for line in source:
                    json.loads(line)  # Refuse a partial/truncated event.
                    target.write(('' if first else ',') + line.strip())
                    first = False
                target.write(']}\n')
                target.flush()
                os.fsync(target.fileno())
            os.link(candidate, self.path)  # A newly occupied destination cannot be overwritten.
            os.unlink(self.partial)
        finally:
            if os.path.exists(candidate):
                os.unlink(candidate)
