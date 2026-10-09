"""Isolated, bounded compressed-header reader used only for format detection."""

import bz2
import lzma
import sys
import zlib
from typing import Any


def prefix(path: str, codec: str) -> bytes:
    decoder: Any
    if codec == 'gz':
        decoder = zlib.decompressobj(31)
    elif codec == 'bz2':
        decoder = bz2.BZ2Decompressor()
    else:
        fmt = lzma.FORMAT_XZ if codec == 'xz' else lzma.FORMAT_ALONE
        decoder = lzma.LZMADecompressor(format=fmt, memlimit=128 * 1024 * 1024)
    result = bytearray()
    with open(path, 'rb') as source:
        for _ in range(16):  # Never inspect more than 1 MiB of compressed input.
            block = source.read(65536)
            if not block:
                break
            result.extend(decoder.decompress(block, max_length=512 - len(result)))
            if len(result) == 512 or decoder.eof:
                break
    return bytes(result)


if __name__ == '__main__':
    try:
        sys.stdout.buffer.write(prefix(sys.argv[2], sys.argv[1]))
    except (OSError, ValueError, EOFError, zlib.error, lzma.LZMAError):
        sys.exit(1)
