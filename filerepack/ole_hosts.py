"""Explicit strict-compaction host gates. No suffix-only CFB acceptance."""

import re
import struct
import uuid
from typing import Dict, Tuple

from .ole_verify import CompoundFile

Path = Tuple[str, ...]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError("OLE host: " + reason)


def msg_profile(compound: CompoundFile) -> None:
    root = next(e for e in compound.entries if e.kind == 5)
    require(
        root.clsid == uuid.UUID("00020d0b-0000-0000-c000-000000000046").bytes_le,
        "unqualified MSG root class",
    )
    storages = {e.path for e in compound.entries if e.kind == 1}
    messages = {()} | {p for p in storages if p[-1] == "__substg1.0_3701000D"}
    require(len(messages) <= 64, "embedded MSG count limit")
    for prefix in sorted(messages):
        data = compound.streams.get(prefix + ("__properties_version1.0",), b"")
        head = 32 if not prefix else 24
        require(
            len(data) >= head and (len(data) - head) % 16 == 0 and not any(data[:8]),
            "MSG property header/record bounds",
        )
        next_recipient, next_attachment, recipients, attachments = struct.unpack_from(
            "<4I", data, 8
        )
        require(
            recipients <= next_recipient <= 8192 and attachments <= next_attachment <= 8192,
            "MSG recipient/attachment counters",
        )
        for label, expected, limit in (
            ("recip", recipients, next_recipient),
            ("attach", attachments, next_attachment),
        ):
            names = [
                p[-1]
                for p in storages
                if p[:-1] == prefix and p[-1].startswith("__" + label + "_version1.0_#")
            ]
            require(
                len(names) == expected
                and all(
                    re.fullmatch("__" + label + r"_version1\.0_#[0-9A-F]{8}", n)
                    and int(n[-8:], 16) < limit
                    for n in names
                ),
                "MSG storage inventory/counters differ",
            )
            for name in names:
                child = compound.streams.get(prefix + (name, "__properties_version1.0"), b"")
                require(
                    len(child) >= 8 and (len(child) - 8) % 16 == 0 and not any(child[:8]),
                    "MSG recipient/attachment property bounds",
                )
                property_index(child, 8)
        tags = property_index(data, head)
        classes = [
            (kind, compound.streams.get(prefix + ("__substg1.0_001A" + kind,), b""))
            for kind in ("001F", "001E")
        ]
        classes = [(kind, value) for kind, value in classes if value]
        require(len(classes) == 1 and any(tag >> 16 == 0x1A for tag in tags), "missing MSG class")
        kind, value = classes[0]
        name = value.decode("utf-16le" if kind == "001F" else "ascii").rstrip("\0")
        require(
            name == "IPM.Note"
            or name.startswith("IPM.Note.")
            and not any(x in name.casefold() for x in ("smime", "signed", "rpmsg", "encrypted")),
            "protected/unqualified MSG message class",
        )


def property_index(data: bytes, head: int) -> Dict[int, bytes]:
    result = {}
    for at in range(head, len(data), 16):
        tag, flags = struct.unpack_from("<II", data, at)
        require(tag not in result and flags & ~7 == 0, "MSG duplicate property/reserved flags")
        result[tag] = data[at + 8 : at + 16]
    return result


def vsd_profile(compound: CompoundFile) -> None:
    data = compound.streams.get(("VisioDocument",), b"")
    require(
        len(data) >= 54 and data[:20] == b"Visio (TM) Drawing\r\n", "missing Visio document header"
    )
    require(
        struct.unpack_from("<H", data, 26)[0] == 11, "only Visio binary version 11 is qualified"
    )
    require(struct.unpack_from("<I", data, 28)[0] == len(data), "Visio document size differs")
    kind, address, offset, length, fmt = struct.unpack_from("<4IH", data, 36)
    require(
        kind == 20 and offset + length <= len(data) and length > 0,
        "Visio trailer pointer bounds/type",
    )
    require(
        not any(
            e.name.casefold().startswith(("vba", "macros", "encrypted")) for e in compound.entries
        ),
        "unqualified active/protected Visio structure",
    )


def pub_profile(compound: CompoundFile) -> None:
    contents = compound.streams.get(("Contents",), b"")
    quill = compound.streams.get(("Quill", "QuillSub", "CONTENTS"), b"")
    require(
        len(contents) >= 44 and contents[:4] == bytes.fromhex("e8ac2c00"),
        "only Publisher 2002 Contents structure is qualified",
    )
    require(
        len(quill) >= 32
        and quill[:8] == b"CHNKINK "
        and ("Escher", "EscherStm") in compound.streams
        and ("\x01CompObj",) in compound.streams,
        "missing Publisher Quill/Escher/class structure",
    )
    require(
        struct.unpack_from("<I", contents, 8)[0] == len(contents), "Publisher Contents size differs"
    )


def mpp_profile(compound: CompoundFile) -> None:
    compobj = compound.streams.get(("\x01CompObj",), b"")
    require(
        b"MSProject.MPP9\0" in compobj and b"Microsoft Project 9.0\0" in compobj,
        "only Project MPP9 is qualified",
    )
    props = compound.streams.get(("Props9",), b"")
    require(
        len(props) >= 16 and struct.unpack_from("<II", props) == (len(props) - 32, len(props) - 32),
        "MPP9 Props header bounds",
    )
    count = struct.unpack_from("<H", props, 12)[0]
    require(0 < count <= 4096, "MPP9 property count")
    at, values = 16, {}
    for _ in range(count):
        require(at + 12 <= len(props), "MPP9 truncated property header")
        size, key, reserved = struct.unpack_from("<III", props, at)
        at += 12
        require(0 < size <= len(props) - at and key not in values, "MPP9 property size/identity")
        values[key] = props[at : at + size]
        at += size + size % 2
    require(
        values.get(0x35400000) == b"\0" and values.get(0x35400007) == b"\0",
        "MPP9 password/encryption flag is unqualified",
    )
    require(
        ("   19", "TBkndTask", "FixedData") in compound.streams
        and ("   19", "TBkndRsc", "FixedData") in compound.streams
        and ("   19", "TBkndCal", "FixedData") in compound.streams,
        "MPP9 task/resource/calendar structure",
    )
    # Private trailing Props data is exact under strict compaction, never rewritten.


MSI_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._"


def msi_name(name: str) -> str:
    result = ""
    for char in name:
        value = ord(char)
        if value == 0x4840:
            result += "\x01"
        elif 0x3800 <= value < 0x4800:
            value -= 0x3800
            result += MSI_ALPHABET[value & 63] + MSI_ALPHABET[value >> 6]
        elif 0x4800 <= value < 0x4840:
            result += MSI_ALPHABET[value - 0x4800]
        else:
            result += char
    return result


def msi_profile(compound: CompoundFile) -> None:
    root = next(e for e in compound.entries if e.kind == 5)
    require(
        root.clsid == uuid.UUID("000c1084-0000-0000-c000-000000000046").bytes_le,
        "unqualified MSI database class (patch/transform excluded)",
    )
    names = {msi_name(p[0]): v for p, v in compound.streams.items() if len(p) == 1}
    require(
        len(names) == len([p for p in compound.streams if len(p) == 1]), "MSI encoded-name aliases"
    )
    require(
        not any(
            "digitalsignature" in msi_name(e.name).casefold()
            or "digitalcertificate" in msi_name(e.name).casefold()
            for e in compound.entries
        ),
        "signed MSI database",
    )
    require(
        all(
            n in names
            for n in (
                "\x01_StringPool",
                "\x01_StringData",
                "\x01_Tables",
                "\x01_Columns",
                "\x05SummaryInformation",
            )
        ),
        "missing MSI table/string/summary streams",
    )
    pool, text = names["\x01_StringPool"], names["\x01_StringData"]
    require(
        len(pool) >= 4
        and len(pool) % 4 == 0
        and len(names["\x01_Tables"]) % 2 == 0
        and len(names["\x01_Columns"]) % 8 == 0,
        "unqualified MSI table bounds",
    )
    codepage, flags = struct.unpack_from("<HH", pool)
    require(flags == 0, "large MSI string-reference format is not qualified")
    total = sum(struct.unpack_from("<H", pool, at)[0] for at in range(4, len(pool), 4))
    require(total == len(text), "MSI string-pool lengths differ")
    summary = names["\x05SummaryInformation"]
    require(
        len(summary) >= 48
        and summary[:2] == b"\xfe\xff"
        and struct.unpack_from("<I", summary, 24)[0] == 1,
        "MSI summary structure",
    )


PROFILES = {
    "msg": msg_profile,
    "vsd": vsd_profile,
    "pub": pub_profile,
    "mpp": mpp_profile,
    "msi": msi_profile,
}
