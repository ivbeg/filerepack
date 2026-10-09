"""QGIS project XML and verified auxiliary SQLite snapshots."""

import hashlib
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Optional
from xml.etree import ElementTree as ET

from . import candidates as tx
from .markup import minify_xml_bytes
from .models import PackResult
from .native import MAX_NATIVE_BYTES, read_native
from .transactions import guard_packer

# QGIS emits this inert public doctype. Preserve it, but never load its DTD.
_DOCTYPE = re.compile(
    rb'\A(?:\xef\xbb\xbf)?(?:<\?xml[^?]*\?>)?[ \t\r\n]*'
    rb'(?P<doctype><!DOCTYPE[ \t\r\n]+qgis[ \t\r\n]+PUBLIC[ \t\r\n]+'
    rb'(?:\x27http://mrcc.com/qgis.dtd\x27[ \t\r\n]+\x27SYSTEM\x27|'
    rb'"http://mrcc.com/qgis.dtd"[ \t\r\n]+"SYSTEM"|'
    rb'"-//Quantum GIS//DTD QGIS 1.0//EN"[ \t\r\n]+"http://mrcc.com/qgis.dtd")'
    rb'[ \t\r\n]*>)',
)


def minify_qgis_bytes(data: bytes) -> Optional[bytes]:
    match = _DOCTYPE.match(data)
    body = data[:match.start('doctype')] + data[match.end('doctype'):] if match else data
    compact = minify_xml_bytes(body)
    if compact is None:
        return None
    try:
        root = ET.fromstring(compact)
        if root.tag != 'qgis' or not root.get('version'):
            return None
    except ET.ParseError:
        return None
    if match:
        offset = match.start('doctype')
        compact = compact[:offset] + match['doctype'] + compact[offset:]
    return compact


@guard_packer
def pack_qgs(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    out_temp = tx.make_temp('.qgs')
    try:
        original = read_native(filepath)
        payload = minify_qgis_bytes(original)
        if payload is None:
            return None
        with open(out_temp, 'wb') as target:
            target.write(payload)
        if minify_qgis_bytes(read_native(out_temp)) != payload:
            return None
        return tx.commit_output(
            out_temp, filepath, len(original), verify='qgs', **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError) as error:
        logging.debug('QGIS XML optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _open_sqlite(path: str) -> sqlite3.Connection:
    if os.path.getsize(path) > MAX_NATIVE_BYTES:
        raise ValueError('Auxiliary database exceeds supported bounds')
    if any(os.path.exists(path + suffix) for suffix in ('-wal', '-journal')):
        raise ValueError('An auxiliary database with sidecars is unsupported')
    with open(path, 'rb') as source:
        if source.read(16) != b'SQLite format 3\0':
            raise ValueError('Not a SQLite auxiliary database')
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def sqlite_fingerprint(path: str) -> str:
    """Hash schema, application settings, row identities and values in bounded batches."""
    checksum = hashlib.sha256()
    connection = _open_sqlite(path)
    try:
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Invalid auxiliary SQLite database')
        for key in ('application_id', 'user_version', 'encoding'):
            checksum.update(repr(connection.execute('PRAGMA ' + key).fetchone()).encode())
        schema = connection.execute(
            'SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name',
        ).fetchall()
        checksum.update(repr(schema).encode('utf-8'))
        for kind, name, _table, sql in schema:
            if kind != 'table':
                continue
            if sql and 'CREATE VIRTUAL TABLE' in sql.upper():
                raise ValueError('Virtual auxiliary tables are unsupported')
            columns = connection.execute('PRAGMA table_xinfo(' + _quote(name) + ')').fetchall()
            if sql and re.search(r'\bWITHOUT\s+ROWID\b', sql, re.IGNORECASE):
                order = ','.join(_quote(column[1]) for column in columns)
                query = 'SELECT * FROM ' + _quote(name) + ' ORDER BY ' + order
            else:
                names = {column[1].lower() for column in columns}
                rowid = next((key for key in ('rowid', '_rowid_', 'oid') if key not in names), None)
                if rowid is None:
                    raise ValueError('All auxiliary rowid aliases are shadowed')
                query = 'SELECT ' + rowid + ', * FROM ' + _quote(name) + ' ORDER BY ' + rowid
            for row in connection.execute(query):
                checksum.update(repr(row).encode('utf-8') + b'\0')
        return checksum.hexdigest()
    finally:
        connection.close()


@guard_packer
def pack_qgd(
    filepath: str, debug: bool = False, quiet: bool = False, **commit: Any,
) -> Optional[PackResult]:
    out_temp = tx.make_temp('.qgd')
    try:
        expected = sqlite_fingerprint(filepath)
        tx.remove_quietly(out_temp)
        for suffix in ('-journal', '-wal', '-shm'):
            tx.own_sidecar(out_temp + suffix)
        source = _open_sqlite(filepath)
        try:
            source.execute("VACUUM INTO '" + out_temp.replace("'", "''") + "'")
        finally:
            source.close()
        if sqlite_fingerprint(out_temp) != expected:
            return None
        return tx.commit_output(
            out_temp, filepath, os.path.getsize(filepath), verify='sqlite',
            **tx.commit_kwargs(**commit),
        )
    except (OSError, ValueError, sqlite3.Error) as error:
        logging.debug('QGIS auxiliary optimization skipped: %s', error)
        return None
    finally:
        tx.remove_quietly(out_temp)
