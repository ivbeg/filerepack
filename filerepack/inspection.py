"""Read-only planning. Unknown protection and estimates never qualify a writer."""

import os
import struct
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .capabilities import capability
from .formats import identify_filename
from .models import RepackOptions
from .repack import _normalize_options, prepare_destination_plan, OptionsInput
from .selection import category_enabled


@dataclass
class InspectionResult:
    source: str
    destination: str
    schema_version: int = 1
    record_type: str = 'item'
    format: Optional[str] = None
    detection: str = 'extension'
    protection: str = 'unknown'
    eligibility: str = 'requires-validation'
    blockers: List[str] = field(default_factory=list)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    estimates: Dict[str, Any] = field(default_factory=dict)
    effective_options: Dict[str, Any] = field(default_factory=dict)
    proposed_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _zip_probe(path: str, result: InspectionResult) -> None:
    with open(path, 'rb') as stream:
        stream.seek(max(0, os.path.getsize(path) - 65557))
        tail = stream.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or offset + 22 > len(tail):
        result.blockers.append('ZIP directory is missing or unsupported')
        return
    fields = struct.unpack_from('<4s4H2IH', tail, offset)
    if fields[5] > 1024 * 1024 or fields[4] > 10000 or fields[4] == 65535:
        result.blockers.append('ZIP listing exceeds the bounded inspection profile')
        return
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        protected = any(info.flag_bits & 1 for info in entries)
        for info in entries:
            name = info.filename.lower()
            protected |= name.startswith('_xmlsignatures/') or name in (
                'meta-inf/encryption.xml', 'meta-inf/rights.xml', 'meta-inf/signatures.xml',
            ) or (name.startswith('meta-inf/') and name.endswith(('.sf', '.rsa', '.dsa', '.ec')))
        result.detection = 'ZIP directory'
        # Absence of familiar signature names is not a comprehensive protection check.
        result.protection = 'protected' if protected else 'unknown'
        result.estimates.update(decoded_bytes={'value': sum(x.file_size for x in entries),
                                               'provenance': 'ZIP directory estimate'},
                                members={'value': len(entries), 'provenance': 'ZIP directory'})
        if protected:
            result.blockers.append('Signed, encrypted or rights-managed package')


def inspect_file(path: str, outfile: Optional[str] = None,
                 options: Optional[OptionsInput] = None) -> InspectionResult:
    effective = _normalize_options(options or RepackOptions())
    source = os.path.abspath(path)
    result = InspectionResult(source, os.path.abspath(outfile or path), effective_options=effective)
    if not os.path.isfile(source) or os.path.islink(source):
        raise ValueError('Inspection requires a regular non-symlink file')
    kind = identify_filename(source)  # Do not decode a stream merely to guess its payload.
    result.estimates = {'input_bytes': {'value': os.path.getsize(source),
                                       'provenance': 'filesystem'},
                        'candidate_savings': {'value': None, 'provenance': 'not measured'}}
    if kind is None:
        result.blockers.append('Unknown format')
    else:
        result.format = kind.packer or kind.key
        info = capability(kind)
        result.capabilities = info.to_dict()
        result.blockers.extend('Missing prerequisite: ' + value for value in info.missing)
        if not info.writer:
            result.blockers.append('No qualified writer for this format')
        if not category_enabled(info.category, effective):
            result.blockers.append('Category disabled')
        if kind.family == 'zip':
            try:
                _zip_probe(source, result)
            except (OSError, ValueError, zipfile.BadZipFile) as exc:
                result.blockers.append(str(exc))
        try:
            plan = prepare_destination_plan(source, outfile, effective, peek=False)
            result.destination = plan.converted or plan.output
            result.proposed_paths = list(plan.paths)
        except (OSError, ValueError) as exc:
            result.blockers.append('Destination conflict: ' + str(exc))
        if result.format == 'tracev3':
            from .tracev3 import destination_refusal
            reason = destination_refusal(source, result.destination, None)
            if reason:
                result.blockers.append(reason)
        if result.format in ('sqlite', 'sqlite3', 'gpkg', 'mbtiles'):
            from .data import sqlite_eligibility
            reason = sqlite_eligibility(source, result.destination, effective)
            if reason:
                result.blockers.append(reason)
    if result.blockers:
        result.eligibility = 'blocked'
    return result
