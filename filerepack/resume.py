"""Locked JSONL checkpoints with a bounded coordinator index and content verification."""

import hashlib
from importlib import metadata
import json
import os
import sqlite3
import tempfile
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from .capabilities import REGISTRY_VERSION
from .reports import identity
from .tools import TOOL_SPECS, resolve_tool, probe_version
from .transactions import digest


def adapter_fingerprint() -> str:
    checksum = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        checksum.update(path.name.encode() + b'\0' + path.read_bytes())
    return checksum.hexdigest()


def library_versions() -> Dict[str, Optional[str]]:
    versions: Dict[str, Optional[str]] = {}
    for name in ('Pillow', 'pikepdf', 'psutil', 'numpy', 'pyarrow', 'duckdb', 'fastavro',
                 'fonttools', 'brotli', 'mutagen', 'lz4', 'olefile', 'zopfli', 'scipy',
                 'h5py', 'netCDF4', 'tifffile', 'imagecodecs', 'pyreadstat', 'zarr',
                 'numcodecs', 'onnx', 'torch', 'zstandard'):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def execution_fingerprint(options: Dict[str, Any], root: str, output: Optional[str]) -> str:
    tools = {}
    for spec in TOOL_SPECS:
        path = resolve_tool(spec.key)
        if path:
            tools[spec.key] = {'path': os.path.realpath(path),
                               'version': probe_version(path, spec.key),
                               'sha256': digest(path)}
    from . import __version__
    from .profiles import PROFILES, PROFILE_VERSION
    value = {'options': {key: item for key, item in options.items()
                         if not key.startswith('_') and key != 'dryrun'},
             'root': identity(root), 'output': identity(output) if output else None,
             'registry': REGISTRY_VERSION, 'policy': 1, 'package': __version__, 'tools': tools,
             'python': tuple(sys.version_info[:3]), 'libraries': library_versions(),
             'adapters': adapter_fingerprint(),
             'profiles': {'version': PROFILE_VERSION, 'definitions': PROFILES}}
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class ResumeManifest:
    def __init__(self, path: str, *, root: str, fingerprint: str,
                 resume: bool = False, dryrun: bool = False) -> None:
        self.path, self.root = os.path.abspath(path), identity(root)
        self.fingerprint, self.dryrun = fingerprint, dryrun
        self.lock_path = self.path + '.filerepack-lock'
        self.lock: Optional[int] = None
        self.temporary = tempfile.TemporaryDirectory(prefix='filerepack-checkpoint-index-')
        self.database = sqlite3.connect(os.path.join(self.temporary.name, 'index.sqlite'))
        self.database.execute('CREATE TABLE entries '
                              '(source TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.database.execute('CREATE TABLE converted '
                              '(output TEXT PRIMARY KEY, source TEXT NOT NULL)')
        try:
            if os.path.islink(self.path):
                raise ValueError('Manifest symlinks are unsupported')
            if os.path.exists(self.path) and os.stat(self.path).st_nlink > 1:
                raise ValueError('Manifest hard links are unsupported')
            if not os.path.isdir(os.path.dirname(self.path)):
                raise ValueError('Manifest parent directory must already exist')
            if not dryrun:
                self.lock = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            if resume:
                self._load()
            elif os.path.lexists(self.path):
                raise FileExistsError('Manifest exists; use --resume')
            elif not dryrun:
                self.checkpoint()
        except BaseException:
            self.close()
            raise

    @property
    def protected_paths(self) -> tuple:
        return self.path, self.lock_path, self.path + '.checkpoint-partial'

    def _load(self) -> None:
        checksum, count = hashlib.sha256(), 0
        with open(self.path, encoding='utf-8') as source:
            header = json.loads(source.readline(1024 * 1024))
            if (not isinstance(header, dict) or header.get('schema_version') != 1 or
                    header.get('root') != self.root):
                raise ValueError('Unsupported manifest schema or mismatched run root')
            final = None
            for line in iter(lambda: source.readline(1024 * 1024 + 1), ''):
                if len(line) > 1024 * 1024:
                    raise ValueError('Manifest record exceeds 1 MiB')
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Manifest records must be objects')
                if row.get('record_type') == 'checkpoint':
                    if final is not None:
                        raise ValueError('Duplicate manifest footer')
                    final = row
                    continue
                if final is not None or row.get('record_type') != 'entry':
                    raise ValueError('Invalid manifest record order')
                if (not isinstance(row.get('source'), str) or
                        not isinstance(row.get('outcome'), dict)):
                    raise ValueError('Malformed manifest completion entry')
                checksum.update(line.encode())
                count += 1
                try:
                    self.database.execute('INSERT INTO entries VALUES (?, ?)',
                                          (row['source'], line))
                except sqlite3.IntegrityError as exc:
                    raise ValueError('Duplicate manifest source identity') from exc
                self._index_conversion(row)
            if final != {'record_type': 'checkpoint', 'entries': count,
                         'sha256': checksum.hexdigest()}:
                raise ValueError('Incomplete or corrupt manifest checkpoint')
        self.database.commit()

    def _index_conversion(self, entry: Dict[str, Any]) -> None:
        self.database.execute('DELETE FROM converted WHERE source=?', (entry['source'],))
        if (entry.get('outcome', {}).get('status') in ('replaced', 'unchanged') and
                entry.get('source_after', {}).get('sha256') is None and entry.get('output')):
            try:
                self.database.execute('INSERT INTO converted VALUES (?, ?)',
                                      (identity(entry['output']['path']), entry['source']))
            except sqlite3.IntegrityError as exc:
                raise ValueError('Duplicate converted destination identity') from exc

    def checkpoint(self) -> None:
        if self.dryrun:
            return
        path = self.path + '.checkpoint-partial'
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as target:
                target.write(json.dumps({'schema_version': 1, 'root': self.root}) + '\n')
                checksum, count = hashlib.sha256(), 0
                rows = self.database.execute('SELECT payload FROM entries ORDER BY source')
                for payload, in rows:
                    target.write(payload)
                    checksum.update(payload.encode())
                    count += 1
                target.write(json.dumps({'record_type': 'checkpoint', 'entries': count,
                                         'sha256': checksum.hexdigest()}) + '\n')
                target.flush()
                os.fsync(target.fileno())
            os.replace(path, self.path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def prepare(self, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        source = identity(job['filepath'])
        found = self.database.execute('SELECT payload FROM entries WHERE source=?',
                                      (source,)).fetchone()
        converted = False
        if not found:
            found = self.database.execute(
                'SELECT entries.payload FROM entries JOIN converted '
                'ON entries.source=converted.source WHERE converted.output=?', (source,),
            ).fetchone()
            converted = bool(found)
        if found:
            entry = json.loads(found[0])
            outcome = entry['outcome']
            try:
                valid = (entry['fingerprint'] == self.fingerprint and
                         outcome.get('status') in ('replaced', 'unchanged') and
                         (not os.path.lexists(entry['source']) if converted else
                          digest(job['filepath']) == entry['source_after']['sha256']) and
                         digest(entry['output']['path']) == entry['output']['sha256'])
            except (OSError, KeyError, TypeError):
                valid = False
            if valid:
                size = os.path.getsize(entry['output']['path'])
                return {**outcome, 'file': job['filepath'], 'output_file': entry['output']['path'],
                        'status': 'unchanged', 'reason_code': 'resumed',
                        'reason': 'Reused verified completion', 'reused': True, 'published': False,
                        'original_size': size, 'final_size': size, 'savings_bytes': 0,
                        'savings_percent': 0, 'elapsed_time': 0,
                        'details': {'historical_outcome': outcome.get('status'),
                                    'historical_source': entry['source']}}
            job['_resume_invalidated'] = 'Content, destination or execution fingerprint changed'
        job['_source_before'] = {'sha256': digest(job['filepath']),
                                  'size': os.path.getsize(job['filepath'])}
        return None

    def record(self, outcome: Dict[str, Any], job: Optional[Dict[str, Any]]) -> None:
        if self.dryrun or not job or outcome.get('reused'):
            return
        source, output = job['filepath'], outcome.get('output_file', job['filepath'])
        entry = {'record_type': 'entry', 'source': identity(source),
                 'fingerprint': self.fingerprint,
                 'source_before': job.get('_source_before'), 'outcome': outcome}
        if outcome.get('status') in ('replaced', 'unchanged'):
            source_after = digest(source) if os.path.isfile(source) else None
            entry.update(source_after={'sha256': source_after},
                         output={'path': os.path.abspath(output), 'sha256': digest(output),
                                 'size': os.path.getsize(output)})
        payload = json.dumps(entry, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n'
        if len(payload) > 1024 * 1024:
            raise ValueError('Manifest record exceeds the bounded 1 MiB profile')
        self.database.execute('INSERT OR REPLACE INTO entries VALUES (?, ?)',
                              (entry['source'], payload))
        self._index_conversion(entry)
        self.database.commit()
        self.checkpoint()

    def close(self) -> None:
        self.database.close()
        self.temporary.cleanup()
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None
            os.unlink(self.lock_path)
