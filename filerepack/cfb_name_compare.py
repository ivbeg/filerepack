"""MS-CFB 2.6.4 name ordering, independent of Python's Unicode version."""

import struct
from typing import Tuple

from ._cfb_upper_table import SIMPLE_UPPERCASE

NameKey = Tuple[int, Tuple[int, ...]]


def cfb_name_key(name: str) -> NameKey:
    """Order by encoded length, then simple uppercase of each UTF-16 unit.

    Full Unicode uppercase can expand characters (ß -> SS). CFB permits only
    one-unit mappings, and surrogate units are never uppercased. This function
    builds comparison keys only; directory field validation belongs to the reader.
    """
    raw = name.encode("utf-16le", errors="surrogatepass")
    units = struct.unpack("<" + "H" * (len(raw) // 2), raw)
    return len(raw), tuple(SIMPLE_UPPERCASE.get(unit, unit) for unit in units)
