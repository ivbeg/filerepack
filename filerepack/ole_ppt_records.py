"""Qualified trailing PPT OLE storages and their independent preservation contract.

MS-PPT 2.1.2, 2.3.2-6, 2.10.12/27/28/34-36. No prefix record moves; only
compressed object atoms, their persist index and the final edit can move.
"""

import hashlib
import io
import struct
import zlib
from dataclasses import dataclass, replace
from importlib.metadata import PackageNotFoundError, version
from typing import Dict, List, Tuple

from .format_support import Budget, FormatLimit, UnsupportedFormat, inflate
from .ole_ppt import PptRecord
from .ole_verify import CompoundFile, OleManifest
from .ole_verify import independent_manifest

DOCUMENT = ("PowerPoint Document",)
CURRENT = ("Current User",)
MAX_OBJECT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_OBJECTS = 64
MAX_ZOPFLI_BYTES = 1024 * 1024

# Standard types/versions audited in MS-PPT and MS-ODRAW, qualified by the POI
# embedding fixture. BinaryTagDataBlob is separately parsed below; an unknown
# record/version/private tag never becomes an opaque relocation exception.
_CONTAINERS = {
    1000,
    1006,
    1010,
    1016,
    1018,
    1033,
    1035,
    1036,
    1043,
    1044,
    2000,
    2005,
    4040,
    4044,
    4080,
    5000,
    5002,
    61440,
    61441,
    61442,
    61443,
    61444,
    61453,
    61457,
}
_ATOMS = {
    1002,
    1011,
    1019,
    1021,
    1022,
    1034,
    1045,
    2032,
    3009,
    3011,
    3998,
    3999,
    4000,
    4001,
    4002,
    4003,
    4004,
    4005,
    4008,
    4009,
    4010,
    4023,
    4026,
    4045,
    4050,
    4056,
    4085,
    4088,
    4090,
    4113,
    5003,
    6002,
    61446,
    61448,
    61456,
    61726,
}
_VERSIONS = {
    **dict.fromkeys(_CONTAINERS, 15),
    **dict.fromkeys(_ATOMS, 0),
    1001: 1,
    1007: 2,
    4035: 1,
    61447: 2,
    61449: 1,
    61450: 2,
    61451: 3,
}


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise UnsupportedFormat("PPT OLE records: " + reason)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extensions(data: bytes, records: Dict[int, PptRecord]) -> None:
    for offset, record in records.items():
        _require(
            _VERSIONS.get(record.kind) == record.flags & 15,
            "unqualified record type/version: " + str(record.kind),
        )
        if record.kind == 5000:
            children = [child for child in records.values() if child.parent == offset]
            _require(
                record.flags == 15
                and bool(children)
                and all(child.kind == 5002 for child in children),
                "unqualified programmable tag list",
            )
        elif record.kind == 5002:
            positions = sorted(pos for pos, child in records.items() if child.parent == offset)
            _require(record.flags == 15 and len(positions) == 2, "unknown binary tag structure")
            name, blob = (records[pos] for pos in positions)
            _require(
                name.kind == 4026
                and name.flags == 0
                and name.size == 16
                and data[positions[0] + 8 : positions[0] + 24] == "___PPT10".encode("utf-16le")
                and blob.kind == 5003
                and blob.flags == 0
                and blob.size == 16,
                "unqualified programmable extension",
            )
            flags, kind, size = struct.unpack_from("<HHI", data, positions[1] + 8)
            _require(
                flags == 0 and kind in (1037, 12011) and size == 8,
                "unqualified PPT10 extension data",
            )
        elif record.kind == 5003:
            _require(
                record.parent is not None and records[record.parent].kind == 5002,
                "binary extension outside a recognized tag",
            )


def _persist(
    data: bytes, records: Dict[int, PptRecord], directory: int, seed: int
) -> Tuple[Dict[int, int], Dict[int, int]]:
    position, end = directory + 8, directory + 8 + records[directory].size
    references: Dict[int, int] = {}
    fields: Dict[int, int] = {}
    targets = set()
    while position < end:
        _require(position + 4 <= end, "truncated persist descriptor")
        descriptor = struct.unpack_from("<I", data, position)[0]
        first, count = descriptor & 0xFFFFF, descriptor >> 20
        position += 4
        _require(
            count > 0
            and first > 0
            and first + count - 1 <= min(seed, 0xFFFFE)
            and position + 4 * count <= end,
            "invalid persist range",
        )
        for identifier in range(first, first + count):
            target = struct.unpack_from("<I", data, position)[0]
            _require(
                identifier not in references
                and target not in targets
                and target < directory
                and target in records
                and records[target].parent is None,
                "ambiguous/invalid persist target",
            )
            references[identifier], fields[identifier] = target, position
            targets.add(target)
            position += 4
    return references, fields


@dataclass(frozen=True)
class EmbeddedObject:
    offset: int
    identifier: int
    identity: int
    profile: str
    raw: bytes
    manifest: OleManifest
    encoded: bytes


def _embedded(
    data: bytes,
    records: Dict[int, PptRecord],
    persist: Dict[int, int],
    document: int,
    budget: Budget,
) -> List[EmbeddedObject]:
    from .ole import _profile

    atoms = [pos for pos, r in records.items() if r.kind == 4035]
    references = [pos for pos, r in records.items() if r.kind == 3009]
    _require(0 < len(atoms) == len(references) <= MAX_OBJECTS, "object/reference count")
    objects: List[EmbeddedObject] = []
    decoded_total = 0
    for offset in atoms:
        atom = records[offset]
        parent = records.get(atom.parent) if atom.parent is not None else None
        ancestor = records.get(parent.parent) if parent and parent.parent is not None else None
        _require(
            atom.flags == 1
            and atom.size == 24
            and parent is not None
            and parent.kind == 4044
            and parent.flags == 15
            and ancestor is not None
            and ancestor.kind == 1033
            and ancestor.flags == 15
            and ancestor.parent == document,
            "object outside current document embedded-object list",
        )
        aspect, kind, identity, subtype, identifier = struct.unpack_from("<5I", data, offset + 8)
        _require(
            aspect == 1
            and kind == 0
            and identity > 0
            and subtype in (2, 3)
            and not any(o.identity == identity or o.identifier == identifier for o in objects),
            "unknown/duplicate embedded object identity/subtype",
        )
        target = persist.get(identifier)
        _require(target is not None, "missing embedded storage reference")
        assert target is not None
        storage = records[target]
        _require(
            storage.kind == 4113
            and storage.flags == 16
            and storage.parent is None
            and 4 < storage.size <= MAX_OBJECT_BYTES,
            "unqualified storage wrapper",
        )
        matches = [
            pos
            for pos in references
            if records[pos].flags == 0
            and records[pos].size == 4
            and struct.unpack_from("<I", data, pos + 8)[0] == identity
        ]
        _require(len(matches) == 1, "missing/duplicate shape reference")
        ref = records[matches[0]]
        _require(
            ref.parent is not None and records[ref.parent].kind == 61457,
            "shape reference outside OfficeArtClientData",
        )
        owner = matches[0]
        while True:
            owner_parent = records[owner].parent
            if owner_parent is None:
                break
            owner = owner_parent
        _require(
            records[owner].kind == 1006 and owner in persist.values(),
            "shape reference outside a live slide",
        )
        assert atom.parent is not None
        children = [r for r in records.values() if r.parent == atom.parent]
        embeds = [r for r in children if r.kind == 4045]
        _require(
            len(embeds) == 1
            and embeds[0].flags == 0
            and embeds[0].size == 8
            and sum(r.kind == 4035 for r in children) == 1
            and all(r.kind in (4045, 4035, 4026) for r in children),
            "unqualified embedded-object container",
        )
        strings = [r for r in children if r.kind == 4026]
        _require(
            all(r.flags in (16, 32, 48) and r.size % 2 == 0 for r in strings)
            and len({r.flags for r in strings}) == len(strings),
            "unqualified OLE name/class strings",
        )
        expected = struct.unpack_from("<I", data, target + 8)[0]
        _require(512 <= expected <= MAX_OBJECT_BYTES, "decoded storage size limit")
        if decoded_total + expected > MAX_TOTAL_BYTES:
            raise FormatLimit("PPT aggregate decoded storage exceeds 64 MiB")
        budget.memory(expected * 2)
        encoded = data[target + 12 : target + 8 + storage.size]
        try:
            raw = inflate(encoded, budget, maximum=expected)
        except zlib.error as exc:
            raise UnsupportedFormat("PPT OLE records: invalid zlib storage") from exc
        _require(len(raw) == expected, "decoded storage length mismatch")
        decoded_total += len(raw)
        nested = CompoundFile(raw)
        profile = "doc" if subtype == 2 else "xls"
        _require(_profile(nested, profile) == (profile, False), "nested VBA is not qualified")
        independent_manifest(io.BytesIO(raw), nested)
        budget.consume(nodes=len(nested.entries))
        objects.append(
            EmbeddedObject(target, identifier, identity, profile, raw, nested.manifest, encoded)
        )
    return sorted(objects, key=lambda obj: obj.offset)


@dataclass
class PptLayout:
    compound: CompoundFile
    data: bytes
    current: bytes
    directory: int
    edit: int
    persist: Dict[int, int]
    fields: Dict[int, int]
    objects: List[EmbeddedObject]

    def fingerprint(self) -> Tuple[object, ...]:
        prefix = self.data[: self.objects[0].offset]
        index = bytearray(self.data[self.directory : self.edit])
        targets = {obj.offset: ("object", i) for i, obj in enumerate(self.objects)}
        references = []
        for identifier, offset in self.persist.items():
            struct.pack_into("<I", index, self.fields[identifier] - self.directory, 0)
            references.append((identifier, targets.get(offset, ("prefix", offset))))
        edit = bytearray(self.data[self.edit :])
        struct.pack_into("<I", edit, 20, 0)
        current = bytearray(self.current)
        struct.pack_into("<I", current, 16, 0)
        entries = tuple(
            replace(e, size=0, sha256="") if e.path in (DOCUMENT, CURRENT) else e
            for e in self.compound.manifest.entries
        )
        objects = tuple(
            (o.identifier, o.identity, o.profile, len(o.raw), _hash(o.raw), o.manifest)
            for o in self.objects
        )
        return (
            entries,
            len(prefix),
            _hash(prefix),
            objects,
            bytes(index),
            tuple(references),
            bytes(edit),
            bytes(current),
        )


def inspect_records(compound: CompoundFile, budget: Budget) -> PptLayout:
    from .ole_ppt_host import inspect_host

    host = inspect_host(compound, budget)
    objects = _embedded(host.data, host.records, host.persist, 0, budget)
    _require(
        [obj.offset for obj in objects] == host.storages,
        "storages must be the complete final contiguous object block",
    )
    return PptLayout(
        compound,
        host.data,
        host.current,
        host.directory,
        host.edit,
        host.persist,
        host.fields,
        objects,
    )


def equal_layouts(source: PptLayout, candidate: PptLayout) -> bool:
    return source.fingerprint() == candidate.fingerprint() and all(
        len(after.encoded) <= len(before.encoded)
        for before, after in zip(source.objects, candidate.objects)
    )


def reencode(layout: PptLayout, budget: Budget) -> Tuple[bytes, bytes, List[str]]:
    data = bytearray(layout.data[: layout.objects[0].offset])
    mapping = dict.fromkeys(layout.persist.values(), 0)
    for offset in mapping:
        mapping[offset] = offset
    encoders = []
    try:
        if version("zopfli") != "0.4.3":
            raise ImportError("Unqualified optional Zopfli version")
        from zopfli.zlib import compress as zopfli_compress
    except (ImportError, PackageNotFoundError):
        zopfli_compress = None
    for obj in layout.objects:
        budget.check()
        mapping[obj.offset] = len(data)
        payload, encoder = obj.encoded, "original"
        encoded = zlib.compress(obj.raw, 9)
        if len(encoded) < len(payload):
            payload, encoder = encoded, "zlib9"
        if zopfli_compress is not None and len(obj.raw) <= MAX_ZOPFLI_BYTES:
            encoded = bytes(zopfli_compress(obj.raw, numiterations=15))
            budget.check()
            if len(encoded) < len(payload):
                payload, encoder = encoded, "zopfli15"
        # Independently check the encoder before allowing any stream replacement.
        check = zlib.decompressobj()
        raw = check.decompress(payload, len(obj.raw) + 1)
        _require(
            raw == obj.raw and check.eof and not check.unused_data and not check.unconsumed_tail,
            "encoder did not preserve decoded bytes",
        )
        budget.consume(decoded=len(raw))
        data.extend(struct.pack("<HHII", 16, 4113, len(payload) + 4, len(obj.raw)))
        data.extend(payload)
        encoders.append(encoder)
    directory = len(data)
    index = bytearray(layout.data[layout.directory : layout.edit])
    for identifier, field in layout.fields.items():
        struct.pack_into("<I", index, field - layout.directory, mapping[layout.persist[identifier]])
    data.extend(index)
    edit = len(data)
    user_edit = bytearray(layout.data[layout.edit :])
    struct.pack_into("<I", user_edit, 20, directory)
    data.extend(user_edit)
    current = bytearray(layout.current)
    struct.pack_into("<I", current, 16, edit)
    budget.check()
    return bytes(data), bytes(current), encoders
