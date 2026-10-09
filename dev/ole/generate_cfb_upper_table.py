"""Regenerate the pinned CFB table from local UnicodeData and Unicode license files.

Usage: python dev/ole/generate_cfb_upper_table.py UnicodeData.txt license.txt
Download the versioned source listed in the generated module, never UCD/latest.
"""

import argparse
import hashlib
from pathlib import Path

SOURCE_SHA256 = "ff58e5823bd095166564a006e47d111130813dcf8bf234ef79fa51a870edb48f"
SOURCE_URL = "https://www.unicode.org/Public/16.0.0/ucd/UnicodeData.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unicode_data", type=Path)
    parser.add_argument("license", type=Path)
    args = parser.parse_args()
    source = args.unicode_data.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        parser.error("UnicodeData must match the pinned Unicode 16.0.0 SHA-256")
    entries = []
    for line in source.decode().splitlines():
        fields = line.split(";")
        unit = int(fields[0], 16)
        if unit <= 0xFFFF and fields[12]:
            upper = int(fields[12], 16)
            assert upper <= 0xFFFF and not 0xD800 <= unit <= 0xDFFF
            entries.append(f"0x{unit:04X}: 0x{upper:04X},")
    header = (
        '\"\"\"Generated BMP Simple_Uppercase_Mapping from Unicode 16.0.0.\n\n'
        f"Source: {SOURCE_URL}\nSHA-256: {SOURCE_SHA256}\n"
        "Field 12 only; absent mappings and surrogate units retain their original value.\n"
        "No Unicode SpecialCasing expansions are used. See dev/ole/generate_cfb_upper_table.py.\n"
        '\"\"\"\n\n'
    )
    header += "\n".join(
        "# " + line if line else "#" for line in args.license.read_text().splitlines()
    ) + "\n\n"
    body = "SIMPLE_UPPERCASE = {\n" + "\n".join(
        "    " + " ".join(entries[i : i + 5]) for i in range(0, len(entries), 5)
    ) + "\n}\n"
    target = Path(__file__).resolve().parents[2] / "filerepack" / "_cfb_upper_table.py"
    target.write_text(header + body, encoding="utf-8")


if __name__ == "__main__":
    main()
