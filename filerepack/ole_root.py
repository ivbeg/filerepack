"""Narrow compatibility for the observed legacy CFB root-name encoding.

Only directory slot zero's service name/length may change. Application names,
metadata, object types, links and allocation fields remain subject to validation.
"""

import struct
from contextlib import contextmanager
from typing import BinaryIO, Iterator, Union

MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
LEGACY_ROOT_NAME = b"R\0" + b"\0" * 62
CANONICAL_ROOT_NAME = "Root Entry".encode("utf-16le").ljust(64, b"\0")


def normalize_root_name(data: bytes) -> bytes:
    """Return a private canonical view for the exact R/length-2 root anomaly.

    All other name defects are rejected by the strict CFB readers. This does
    not authorize rewriting a document or replace allocation/profile checks.
    """
    if (
        len(data) < 512
        or data[:8] != MAGIC
        or struct.unpack_from("<4H", data, 26) != (3, 0xFFFE, 9, 6)
    ):
        return data
    offset = (struct.unpack_from("<I", data, 48)[0] + 1) * 512
    if (
        offset + 128 > len(data)
        or data[offset : offset + 64] != LEGACY_ROOT_NAME
        or data[offset + 64 : offset + 67] != b"\x02\0\x05"
    ):
        return data
    # Patch only the service fields while allocating one canonical carrier.
    # A full bytearray followed by bytes would hold two additional file copies.
    view = memoryview(data)
    return b"".join((view[:offset], CANONICAL_ROOT_NAME + b"\x16\0", view[offset + 66 :]))


class _RootNameView:
    """Seekable read-only view patching only the qualified 66-byte root fields."""

    def __init__(self, source: BinaryIO):
        self.source, self.position = source, 0
        position = source.tell()
        try:
            source.seek(0, 2)
            self.size = source.tell()
            if not 512 <= self.size <= 128 * 1024 * 1024:
                raise ValueError("OLE: independent source size limit")
            source.seek(0)
            header = source.read(512)
            self.offset = -1
            if header[:8] == MAGIC and struct.unpack_from("<4H", header, 26) == (3, 0xFFFE, 9, 6):
                offset = (struct.unpack_from("<I", header, 48)[0] + 1) * 512
                if offset + 128 <= self.size:
                    source.seek(offset)
                    if source.read(67) == LEGACY_ROOT_NAME + b"\x02\0\x05":
                        self.offset = offset
        finally:
            source.seek(position)

    @property
    def closed(self) -> bool:
        return self.source.closed

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if position < 0 or whence not in (0, 1, 2):
            raise ValueError("invalid root view seek")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        position = self.source.tell()
        try:
            self.source.seek(self.position)
            data = self.source.read(size)
        finally:
            self.source.seek(position)
        start, self.position = self.position, self.position + len(data)
        if self.offset >= 0 and start < self.offset + 66 and self.position > self.offset:
            patch = CANONICAL_ROOT_NAME + b"\x16\0"
            first, end = max(start, self.offset), min(self.position, self.offset + 66)
            data = (
                data[: first - start]
                + patch[first - self.offset : end - self.offset]
                + data[end - start :]
            )
        return data


@contextmanager
def root_name_view(path: Union[str, BinaryIO]) -> Iterator[_RootNameView]:
    if isinstance(path, str):
        with open(path, "rb") as source:
            yield _RootNameView(source)
    else:
        yield _RootNameView(path)
