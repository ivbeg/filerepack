#!/usr/bin/env python3
"""Download a bounded, deterministic subset; inspect bytes without loading objects."""
import argparse
import bz2
import collections
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import platform
import struct
import sys
import time
import urllib.request
import zipfile
import zlib

LIMIT = 8 * 1024 * 1024
DECODE_LIMIT = 32 * 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
FORMATS = {
    "rds": 8,
    "rdata": 6,
    "mat": 6,
    "h5ad": 2,
    "loom": 2,
    "root": 2,
    "vtu": 2,
    "vtp": 2,
    "vti": 2,
    "stl": 2,
    "sav": 2,
    "pt": 3,
    "safetensors": 2,
    "zip": 4,
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def selection(rows):
    selected, seen = [], set()
    for fmt, count in FORMATS.items():
        projects = collections.defaultdict(list)
        for row in rows:
            if (
                row["candidate_format"] == fmt
                and row.get("available")
                and row["size"] is not None
                and 0 < row["size"] <= LIMIT
            ):
                projects[(row["source"], row["project"])].append(row)
        key = lambda r: digest(("multisource-2026-10-04:" + r["url"]).encode())
        queues = [collections.deque(sorted(p, key=key)) for _, p in sorted(projects.items())]
        taken = 0
        while queues and taken < count:
            pending = []
            for queue in queues:
                row = queue.popleft()
                identifier = row["checksum"] or row["url"]
                if identifier not in seen and taken < count:
                    selected.append(row)
                    seen.add(identifier)
                    taken += 1
                if queue:
                    pending.append(queue)
            queues = pending
    return selected


def decode(data):
    if data.startswith(b"\x1f\x8b"):
        codec = "gzip"
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            body = stream.read(DECODE_LIMIT + 1)
    elif data.startswith(b"\xfd7zXZ\x00"):
        codec = "xz"
        decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
        body = decoder.decompress(data, max_length=DECODE_LIMIT + 1)
        if not decoder.eof or decoder.unused_data:
            raise ValueError("incomplete, excessive or concatenated XZ stream")
    elif data.startswith(b"BZh"):
        codec = "bzip2"
        decoder = bz2.BZ2Decompressor()
        body = decoder.decompress(data, max_length=DECODE_LIMIT + 1)
        if not decoder.eof or decoder.unused_data:
            raise ValueError("incomplete, excessive or concatenated bzip2 stream")
    else:
        codec, body = "uncompressed", data
    if len(body) > DECODE_LIMIT:
        raise ValueError("decoded stream exceeds 32 MiB")
    return codec, body


def inspect(data, fmt):
    info = {"signature": "unidentified"}
    if fmt in ("rds", "rdata"):
        codec, body = decode(data)
        serialization = body
        if fmt == "rdata" and body[:3] in (b"RDX", b"RDA", b"RDB"):
            serialization = body[5:]
            info["workspace_header"] = body[:5].decode("ascii", errors="replace")
        if serialization[:2] not in (b"X\n", b"B\n", b"A\n"):
            info.update(codec=codec, signature="not an identified R serialization prefix")
            return info
        info.update(
            signature="R serialization prefix",
            codec=codec,
            decoded_bytes=len(body),
            decoded_sha256=digest(body),
            representation=serialization[:1].decode(),
        )
        if serialization[:2] == b"X\n" and len(serialization) >= 14:
            info["serialization_version"] = struct.unpack(">I", serialization[2:6])[0]
            info["writer_version_code"] = struct.unpack(">I", serialization[6:10])[0]
            info["minimum_reader_version_code"] = struct.unpack(">I", serialization[10:14])[0]
        experiments = []
        for codec, encode in (
            ("gzip-9", lambda b: gzip.compress(b, compresslevel=9, mtime=0)),
            ("xz-6", lambda b: lzma.compress(b, preset=6)),
        ):
            start = time.monotonic()
            candidate = encode(body)
            _, restored = decode(candidate)
            experiments.append(
                {
                    "codec": codec,
                    "output_bytes": len(candidate),
                    "saved_bytes_if_adopted": max(0, len(data) - len(candidate)),
                    "stream_roundtrip_equal": restored == body,
                    "seconds": round(time.monotonic() - start, 6),
                }
            )
        info["experiments"] = experiments
        info["reader_validation"] = "R runtime unavailable; no readRDS/load validation"
    elif fmt == "mat":
        if data.startswith(b"MATLAB 7.3 MAT-file"):
            info["signature"] = "MAT 7.3 HDF5 header"
        elif data.startswith(b"MATLAB 5.0 MAT-file") and len(data) >= 136:
            order = "<" if data[126:128] == b"IM" else ">" if data[126:128] == b"MI" else None
            info.update(signature="MAT v5 family header", endian_indicator=data[126:128].hex())
            if order:
                tag, size = struct.unpack(order + "II", data[128:136])
                info.update(
                    first_element_type=tag,
                    first_element_size=size,
                    first_element_compressed=tag == 15,
                )
        else:
            info["signature"] = "no v5/7.3 header; possible v4 or mislabeled file"
    elif fmt in ("h5ad", "loom"):
        offsets = [0] + [2**n for n in range(9, 17)]
        found = [o for o in offsets if data[o : o + 8] == b"\x89HDF\r\n\x1a\n"]
        info.update(
            signature="HDF5 signature" if found else "no HDF5 signature",
            offsets=found,
            schema_validation="not performed",
        )
    elif fmt == "root":
        info["signature"] = "ROOT header" if data[:4] == b"root" else "no ROOT header"
    elif fmt in ("vtu", "vtp", "vti"):
        prefix = data[:8192].decode("utf-8", errors="replace")
        info.update(
            signature="VTK XML prefix" if "<VTKFile" in prefix else "no VTK XML prefix",
            has_compressor_attribute="compressor=" in prefix,
        )
    elif fmt == "stl":
        count = struct.unpack("<I", data[80:84])[0] if len(data) >= 84 else 0
        if len(data) == 84 + count * 50:
            info.update(signature="binary STL length layout", triangles=count)
        elif data.lstrip().startswith(b"solid"):
            info["signature"] = "ASCII STL prefix"
    elif fmt == "sav":
        info["signature"] = "SPSS header" if data[:4] in (b"$FL2", b"$FL3") else "no SPSS header"
    elif fmt == "safetensors":
        if len(data) < 8:
            raise ValueError("safetensors header too short")
        length = struct.unpack("<Q", data[:8])[0]
        if length > len(data) - 8 or length > 1024 * 1024:
            raise ValueError("safetensors header length exceeds bounds")
        header = json.loads(data[8 : 8 + length])
        tensors = {k: v for k, v in header.items() if k != "__metadata__"}
        if not all(
            isinstance(v, dict) and {"dtype", "shape", "data_offsets"} <= set(v)
            for v in tensors.values()
        ):
            raise ValueError("unidentified tensor header schema")
        info.update(
            signature="safetensors header schema",
            tensor_count=len(tensors),
            header_bytes=length,
            dtypes=sorted({v["dtype"] for v in tensors.values()}),
        )
    elif fmt in ("zip", "pt"):
        if fmt == "pt" and not zipfile.is_zipfile(io.BytesIO(data)):
            info["signature"] = "not a ZIP checkpoint; legacy or another PT variant"
            return info
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 5000:
                raise ValueError("ZIP directory exceeds 5000 members")
            info.update(signature="ZIP central directory", members=len(members))
            if fmt == "pt":
                info.update(
                    signature="ZIP checkpoint layout",
                    stored_members=sum(m.compress_type == zipfile.ZIP_STORED for m in members),
                    pickle_member=any(m.filename.endswith("/data.pkl") for m in members),
                    reader_validation="not performed; torch.load not invoked",
                )
            info["nested_inventory"] = [
                {
                    "name": m.filename,
                    "decoded_bytes": m.file_size,
                    "compressed_bytes": m.compress_size,
                    "crc32": f"{m.CRC:08x}",
                    "method": m.compress_type,
                }
                for m in members
                if not m.is_dir()
            ]
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=pathlib.Path, required=True)
    parser.add_argument("--run", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.inventory, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    inputs = args.run / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    results, nested = [], []
    consumed = 0
    for row in selection(rows):
        result = {
            "source": row["source"],
            "project": row["project"],
            "name": row["name"],
            "format": row["candidate_format"],
            "url": row["url"],
            "metadata_size": row["size"],
            "metadata_checksum": row["checksum"],
        }
        path = inputs / (digest(row["url"].encode()) + ".bin")
        try:
            if consumed + row["size"] > TOTAL_LIMIT:
                raise ValueError("64 MiB aggregate download/sample budget reached")
            if path.exists():
                data = path.read_bytes()
            else:
                req = urllib.request.Request(
                    row["url"],
                    headers={"User-Agent": "filerepack-format-survey/1.0 (bounded research probe)"},
                )
                with urllib.request.urlopen(req, timeout=20) as response:
                    data = response.read(LIMIT + 1)
                if len(data) > LIMIT:
                    raise ValueError("download exceeds 8 MiB")
                path.write_bytes(data)
            consumed += len(data)
            if len(data) != row["size"]:
                raise ValueError(f"size mismatch: expected {row['size']}, got {len(data)}")
            if row["checksum"]:
                algorithm, expected = row["checksum"].split(":", 1)
                actual = (
                    hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
                    if algorithm == "git-sha1"
                    else hashlib.new(algorithm, data).hexdigest()
                )
                if actual != expected:
                    raise ValueError("metadata checksum mismatch")
                result["metadata_checksum_verified"] = True
            else:
                result["metadata_checksum_verified"] = False
            result.update(sha256=digest(data), downloaded_bytes=len(data), status="inspected")
            info = inspect(data, row["candidate_format"])
            for member in info.pop("nested_inventory", []):
                nested.append(
                    {
                        "source": row["source"],
                        "project": row["project"],
                        "container": row["name"],
                        **member,
                    }
                )
            result["inspection"] = info
        except Exception as exc:
            result.update(status="unavailable", error=f"{type(exc).__name__}: {exc}")
        results.append(result)
        print(result["format"], result["source"], result["status"], row["name"][:70], flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "probes.json").write_text(
        json.dumps(
            {
                "limits": {
                    "per_file_bytes": LIMIT,
                    "total_sample_bytes": TOTAL_LIMIT,
                    "decoded_stream_bytes": DECODE_LIMIT,
                },
                "consumed_sample_bytes": consumed,
                "selection_limits": FORMATS,
                "environment": {
                    "python": sys.version,
                    "platform": platform.platform(),
                    "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
                },
                "scope": (
                    "Signature checks and R serialization stream experiments; "
                    "no object execution, no runtime handlers."
                ),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (args.output / "nested-inventory.json").write_text(
        json.dumps(nested, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
