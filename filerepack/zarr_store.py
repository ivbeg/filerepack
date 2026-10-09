"""Whole local Zarr v2 stores, exact chunk bytes and exclusive directory publication."""

import ctypes
import errno
import hashlib
import json
import math
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from . import xattrs
from .format_support import (
    Budget,
    FormatLimit,
    UnsupportedFormat,
    format_scope,
    inflate,
    run_operation,
)
from .models import RepackOptions
from .transactions import FileMetadata, FileSnapshot
from .validation import validate_options


def _object(pairs: Any) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON metadata key")
        result[key] = value
    return result


def json_document(data: bytes) -> Any:
    return json.loads(
        data,
        object_pairs_hook=_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("non-standard JSON constant: " + value)
        ),
    )


def replace_member(data: bytes, path: List[str], value: Any) -> bytes:
    """Replace one JSON value while retaining every other byte/number lexeme."""
    text = data.decode("utf-8")
    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    if cursor >= len(text) or text[cursor] != "{":
        raise ValueError("metadata path is not an object")
    cursor += 1
    while cursor < len(text):
        while text[cursor].isspace() or text[cursor] == ",":
            cursor += 1
        if text[cursor] == "}":
            break
        key, end = decoder.raw_decode(text, cursor)
        cursor = end
        while text[cursor].isspace():
            cursor += 1
        if text[cursor] != ":":
            raise ValueError("invalid JSON metadata member")
        cursor += 1
        while text[cursor].isspace():
            cursor += 1
        start = cursor
        _, end = decoder.raw_decode(text, cursor)
        if key == path[0]:
            replacement = (
                replace_member(text[start:end].encode(), path[1:], value).decode()
                if len(path) > 1
                else json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            )
            return (text[:start] + replacement + text[end:]).encode()
        cursor = end
    raise ValueError("missing JSON metadata path: " + "/".join(path))


@dataclass
class Tree:
    files: Dict[str, FileSnapshot]
    directories: Dict[str, Tuple[Tuple[int, ...], FileMetadata]]
    signature: str
    size: int


def _state(path: str) -> Tuple[int, ...]:
    item = os.lstat(path)
    return item.st_dev, item.st_ino, item.st_mode, item.st_mtime_ns, item.st_ctime_ns


def tree(root: str, budget: Budget) -> Tree:
    if os.path.islink(root) or not os.path.isdir(root):
        raise ValueError("store root must be a regular directory, not a link")
    files, directories, folded = {}, {}, set()
    checksum, size = hashlib.sha256(), 0
    for directory, names, entries in os.walk(root, followlinks=False):
        relative = os.path.relpath(directory, root)
        budget.consume(nodes=1)
        item = os.lstat(directory)
        if not stat.S_ISDIR(item.st_mode) or stat.S_ISLNK(item.st_mode):
            raise ValueError("linked/special store directory")
        metadata = FileMetadata(
            stat.S_IMODE(item.st_mode), item.st_atime_ns, item.st_mtime_ns, xattrs.read(directory)
        )
        directories[relative] = (_state(directory), metadata)
        checksum.update(repr((relative, directories[relative][0], metadata.xattrs)).encode())
        for name in sorted([*names, *entries]):
            key = os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/")
            normalized = unicodedata.normalize("NFD", key).casefold()
            if normalized in folded:
                raise UnsupportedFormat(
                    "store keys collide under destination filename normalization"
                )
            folded.add(normalized)
            if any(character in name for character in "\\:\x00") or name.rstrip(" .") != name:
                raise UnsupportedFormat("store key is not portable to supported filesystems")
            if name.split(".")[0].casefold() in {
                "con",
                "prn",
                "aux",
                "nul",
                *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10)),
            }:
                raise UnsupportedFormat("reserved destination filename")
            path = os.path.join(root, key)
            state = os.lstat(path)
            if stat.S_ISLNK(state.st_mode) or not (
                stat.S_ISDIR(state.st_mode) or stat.S_ISREG(state.st_mode)
            ):
                raise UnsupportedFormat("linked/special store key")
            if stat.S_ISREG(state.st_mode):
                if state.st_nlink != 1:
                    raise UnsupportedFormat("hard-linked store files are outside the profile")
                budget.consume(nodes=1)
                snapshot = FileSnapshot.capture(path)
                files[key] = snapshot
                size += state.st_size
                checksum.update(
                    repr(
                        (
                            key,
                            snapshot.entry_generation,
                            snapshot.checksum,
                            snapshot.metadata.xattrs,
                        )
                    ).encode()
                )
                budget.memory(len(files) * 1536)
        names.sort()
    return Tree(files, directories, checksum.hexdigest(), size)


def _read(path: str, budget: Budget) -> bytes:
    length = os.path.getsize(path)
    if length > budget.limits.memory // 8:
        raise FormatLimit("store object exceeds bounded codec/metadata buffer profile")
    with open(path, "rb") as source:
        result = source.read(length + 1)
    if len(result) != length:
        raise ValueError("store object changed while reading")
    return result


def _codec(config: Any) -> Any:
    import numcodecs

    if config is None:
        return None
    if not isinstance(config, dict):
        raise UnsupportedFormat("invalid Zarr compressor configuration")
    identity = config.get("id")
    if identity == "blosc":
        if config.keys() - {"id", "cname", "clevel", "shuffle", "blocksize"}:
            raise UnsupportedFormat("unknown Blosc configuration field")
        if config.get("cname", "lz4") not in numcodecs.blosc.list_compressors():
            raise UnsupportedFormat("Blosc algorithm is unavailable")
        return numcodecs.Blosc(**{key: value for key, value in config.items() if key != "id"})
    if identity in ("gzip", "zlib") and not config.keys() - {"id", "level"}:
        cls = numcodecs.GZip if identity == "gzip" else numcodecs.Zlib
        return cls(level=config.get("level", 1))
    raise UnsupportedFormat("Zarr compressor is outside the tested static allowlist")


def _decode(data: bytes, config: Any, expected: int, budget: Budget) -> bytes:
    budget.memory(expected * 4)
    if config is None:
        raw = data
        budget.consume(decoded=len(raw))
    elif config["id"] in ("gzip", "zlib"):
        raw = inflate(data, budget, config["id"])
    else:
        if (
            len(data) < 16
            or int.from_bytes(data[4:8], "little") != expected
            or (int.from_bytes(data[12:16], "little") != len(data))
        ):
            raise ValueError("Blosc header disagrees with chunk geometry/length")
        raw = bytes(_codec(config).decode(data))
        budget.consume(decoded=len(raw))
    if len(raw) != expected:
        raise ValueError("Zarr decoded chunk does not match fixed-size geometry")
    return raw


def _dtype(value: Any) -> Any:
    import numpy as np

    if isinstance(value, list):
        value = [
            (field[0], _dtype(field[1]), tuple(field[2]))
            if len(field) == 3
            else (field[0], _dtype(field[1]))
            for field in value
        ]
    dtype = np.dtype(value)
    if dtype.hasobject or dtype.itemsize == 0:
        raise UnsupportedFormat("Zarr object/variable-size dtype is outside the profile")
    return dtype


def _array_keys(key: str, data: Dict[str, Any], state: Tree, budget: Budget) -> Any:
    if data.get("zarr_format") != 2 or data.get("filters") is not None:
        raise UnsupportedFormat("Zarr v3 or filtered arrays are outside the initial profile")
    required = {"shape", "chunks", "dtype", "compressor", "fill_value", "order", "filters"}
    if required - data.keys() or data["order"] not in ("C", "F"):
        raise ValueError("incomplete Zarr array metadata")
    shape, chunks = data["shape"], data["chunks"]
    if (
        not isinstance(shape, list)
        or not isinstance(chunks, list)
        or len(shape) != len(chunks)
        or len(shape) > 32
        or any(type(n) is not int or n < 0 for n in shape)
        or any(type(n) is not int or n <= 0 for n in chunks)
    ):
        raise ValueError("invalid Zarr chunk geometry")
    dtype = _dtype(data["dtype"])
    expected = math.prod(chunks) * dtype.itemsize
    budget.memory(expected * 4)
    _codec(data["compressor"])
    prefix = key[: -len(".zarray")]
    separator = data.get("dimension_separator", ".")
    if separator not in (".", "/"):
        raise UnsupportedFormat("unknown Zarr dimension separator")
    keys = []
    for candidate in state.files:
        if not candidate.startswith(prefix):
            continue
        suffix = candidate[len(prefix) :]
        if len(shape) == 0:
            match = suffix == "0"
            indexes = []
        else:
            match = bool(re.fullmatch(r"\d+(?:" + re.escape(separator) + r"\d+)*", suffix))
            indexes = [int(n) for n in suffix.split(separator)] if match else []
        if match:
            if len(indexes) != len(shape) or any(
                index >= math.ceil(length / width)
                for index, length, width in zip(indexes, shape, chunks)
            ):
                raise UnsupportedFormat("out-of-grid/ambiguous Zarr chunk key")
            keys.append(candidate)
    return keys, expected


def inventory(root: str, state: Tree, budget: Budget) -> Tuple[Any, Any]:
    metadata = {}
    for key in state.files:
        if key.rsplit("/", 1)[-1] in (".zarray", ".zgroup", ".zattrs"):
            metadata[key] = json_document(_read(os.path.join(root, key), budget))
    if not (".zarray" in metadata or ".zgroup" in metadata):
        raise UnsupportedFormat("not a complete supported Zarr v2 root")
    arrays = []
    for key, data in sorted(metadata.items()):
        if not isinstance(data, dict):
            raise ValueError("Zarr metadata must be an object")
        if key.endswith(".zgroup") and data.get("zarr_format") != 2:
            raise UnsupportedFormat("only Zarr storage v2 is supported")
        if not key.endswith(".zarray"):
            continue
        keys, expected = _array_keys(key, data, state, budget)
        prefix = key[: -len(".zarray")]
        if any(
            other != key and other.startswith(prefix) and other.endswith(".zarray")
            for other in metadata
        ):
            raise UnsupportedFormat("nested array roots inside a Zarr array")
        arrays.append((key, data, sorted(keys), expected))
    cache = None
    if ".zmetadata" in state.files:
        cache = json_document(_read(os.path.join(root, ".zmetadata"), budget))
        if (
            cache.get("zarr_consolidated_format") != 1
            or not isinstance(cache.get("metadata"), dict)
            or cache["metadata"] != metadata
        ):
            raise ValueError("stale or inconsistent consolidated Zarr metadata")
    return arrays, cache


def fingerprint(root: str, state: Tree, arrays: Any, budget: Budget) -> Any:
    chunks, array_tokens = set(), []
    for key, metadata, keys, expected in arrays:
        values = []
        for chunk in keys:
            budget.consume(nodes=1)
            raw = _decode(
                _read(os.path.join(root, chunk), budget), metadata["compressor"], expected, budget
            )
            values.append((chunk, hashlib.sha256(raw).hexdigest()))
        semantic = {name: value for name, value in metadata.items() if name != "compressor"}
        array_tokens.append((key, semantic, values))
        chunks.update(keys)
    controls = {key for key, _, _, _ in arrays} | {".zmetadata"}
    auxiliaries = [
        (key, snapshot.checksum)
        for key, snapshot in sorted(state.files.items())
        if key not in chunks and key not in controls
    ]
    return sorted(state.files), sorted(state.directories), array_tokens, auxiliaries


def _write(path: str, data: bytes, budget: Budget) -> None:
    budget.consume(written=len(data))
    with open(path, "wb") as target:
        target.write(data)


def _rewrite(
    root: str,
    target: str,
    state: Tree,
    arrays: Any,
    cache: Any,
    options: Dict[str, Any],
    budget: Budget,
) -> Any:
    for relative in state.directories:
        os.makedirs(os.path.join(target, relative), exist_ok=True)
    for key, snapshot in state.files.items():
        budget.check()
        budget.consume(written=os.path.getsize(snapshot.path))
        shutil.copyfile(snapshot.path, os.path.join(target, key))
    decisions = []
    cache_bytes = _read(os.path.join(root, ".zmetadata"), budget) if cache is not None else None
    for key, metadata, keys, expected in arrays:
        old = metadata["compressor"]
        if old is None or not keys:
            continue
        proposed = dict(old)
        if old["id"] == "blosc":
            proposed["clevel"] = 9
            if options.get("zarr_codec_policy") == "compatible-upgrade":
                proposed["cname"] = "zstd"
        else:
            proposed["level"] = 9
        if old == proposed:
            continue
        encoder = _codec(proposed)
        # Per-array temporary output is separate from the candidate store itself.
        with tempfile.TemporaryDirectory(prefix="array-", dir=os.path.dirname(target)) as scratch:
            size, baseline = 0, 0
            for index, chunk in enumerate(keys):
                data = _read(os.path.join(root, chunk), budget)
                raw = _decode(data, old, expected, budget)
                encoded = bytes(encoder.encode(raw))
                if raw != _decode(encoded, proposed, expected, budget):
                    raise ValueError("Zarr codec changed decompressed chunk bytes")
                _write(os.path.join(scratch, str(index)), encoded, budget)
                size += len(encoded)
                baseline += len(data)
            original_meta = _read(os.path.join(root, key), budget)
            updated = replace_member(original_meta, ["compressor"], proposed)
            size += len(updated)
            baseline += len(original_meta)
            if size >= baseline:
                continue
            for index, chunk in enumerate(keys):
                os.replace(os.path.join(scratch, str(index)), os.path.join(target, chunk))
            _write(os.path.join(target, key), updated, budget)
            if cache_bytes is not None:
                cache_bytes = replace_member(cache_bytes, ["metadata", key, "compressor"], proposed)
            decisions.append(
                {"array": key, "source": old, "output": proposed, "saved_bytes": baseline - size}
            )
    if cache_bytes is not None:
        _write(os.path.join(target, ".zmetadata"), cache_bytes, budget)
    return decisions


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    state = tree(source, budget)
    if action == "generation":
        return {"source_generation": state.signature}
    arrays, cache = inventory(source, state, budget)
    original = fingerprint(source, state, arrays, budget)
    details = {
        "profile": "local-Zarr-v2",
        "arrays": len(arrays),
        "chunks": sum(len(keys) for _, _, keys, _ in arrays),
        "input_bytes": state.size,
        "consolidated": cache is not None,
    }
    if action == "inspect":
        return {"details": details, "source_generation": state.signature}
    decisions = []
    if action == "rewrite":
        if state.size > budget.limits.scratch - budget.written:
            raise FormatLimit("complete store copy exceeds scratch budget")
        assert candidate is not None
        decisions = _rewrite(source, candidate, state, arrays, cache, options, budget)
    other = tree(candidate or "", budget)
    newarrays, newcache = inventory(candidate or "", other, budget)
    if fingerprint(candidate or "", other, newarrays, budget) != original or (
        (newcache is None) != (cache is None)
    ):
        raise ValueError("Zarr keys, decoded chunks, attributes or metadata semantics changed")
    if tree(source, budget).signature != state.signature:
        raise ValueError("source store changed during recompression")
    if action == "rewrite":
        for key, snapshot in state.files.items():
            snapshot.metadata.apply(os.path.join(candidate or "", key))
        for key, (_, metadata) in reversed(list(state.directories.items())):
            metadata.apply(os.path.join(candidate or "", key))
    details.update(
        output_bytes=other.size,
        codec_decisions=decisions[:64],
        codec_decisions_total=len(decisions),
    )
    return {
        "changed": other.size < state.size,
        "equal": True,
        "details": details,
        "source_generation": state.signature,
    }


def publish_directory(source: str, destination: str) -> None:
    """Atomic no-replace rename; never fall back to POSIX overwriting rename."""
    if sys.platform == "darwin":
        function = ctypes.CDLL(None, use_errno=True).renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        code = function(os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        library = ctypes.CDLL(None, use_errno=True)
        if not hasattr(library, "renameat2"):
            raise UnsupportedFormat("atomic no-replace directory publication is unavailable")
        function = library.renameat2
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        code = function(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif os.name == "nt":
        # Windows os.rename refuses an existing destination; MoveFileEx does not
        # receive REPLACE_EXISTING. Same-volume publication is required by staging.
        os.rename(source, destination)
        return
    else:
        raise UnsupportedFormat("unverified atomic directory publication platform")
    if code:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(error, "store destination already exists", destination)
        raise OSError(error, os.strerror(error), destination)


@dataclass
class StoreResult:
    source: str
    destination: str
    input_bytes: int
    output_bytes: int
    replaced: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _cleanup_owned_directory(owner: str) -> None:
    # Staged source directory permissions may be read-only. This private tree
    # has already passed the ownership identity check; never follow links.
    os.chmod(owner, stat.S_IMODE(os.lstat(owner).st_mode) | 0o700)
    for directory, names, _ in os.walk(owner, followlinks=False):
        for name in names:
            child = os.path.join(directory, name)
            state = os.lstat(child)
            if stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode):
                os.chmod(child, stat.S_IMODE(state.st_mode) | 0o700)
    shutil.rmtree(owner)


def repack_store(
    source: str, output_dir: str, options: Optional[Union[Dict[str, Any], RepackOptions]] = None
) -> StoreResult:
    """Repack a complete OFFLINE local store to a new absent destination.

    Generation checks detect changes; they are not a live-writer snapshot protocol.
    """
    options = validate_options(
        options.to_dict() if isinstance(options, RepackOptions) else (options or {})
    )
    source = os.path.abspath(source)
    parent = os.path.realpath(os.path.abspath(output_dir))
    destination = os.path.join(parent, os.path.basename(source))
    real_source, real_destination = os.path.realpath(source), os.path.realpath(destination)
    common = os.path.commonpath([real_source, real_destination])
    if common in (real_source, real_destination):
        raise ValueError("source, destination and staging store trees must be disjoint")
    if os.path.lexists(destination):
        raise FileExistsError("store destination already exists: " + destination)
    staging, owner_identity = None, None
    with format_scope(options):
        try:
            if options.get("dryrun"):
                info = run_operation("zarr-store", "inspect", source, options=options)
                size = info["details"]["input_bytes"]
                return StoreResult(
                    source,
                    destination,
                    size,
                    size,
                    False,
                    "dry-run: inspected without staging",
                    info["details"],
                )
            os.makedirs(parent, exist_ok=True)
            staging_owner = tempfile.mkdtemp(prefix=".filerepack-store-", dir=parent)
            stat_owner = os.lstat(staging_owner)
            owner_identity = (stat_owner.st_dev, stat_owner.st_ino)
            staging = os.path.join(staging_owner, "store")
            os.mkdir(staging)
            # Exercise the actual filesystem primitive with private directories.
            probe, target = (
                os.path.join(staging_owner, "probe"),
                os.path.join(staging_owner, "target"),
            )
            os.mkdir(probe)
            os.mkdir(target)
            try:
                publish_directory(probe, target)
            except FileExistsError:
                pass
            else:
                raise UnsupportedFormat("filesystem no-replace directory guarantee unavailable")
            os.rmdir(target)
            publish_directory(probe, target)
            os.rmdir(target)
            info = run_operation("zarr-store", "rewrite", source, staging, options)
            detail = info["details"]
            before, after = detail["input_bytes"], detail["output_bytes"]
            savings = (before - after) * 100 / before if before else 0.0
            if (options.get("keep_if_larger", True) and after >= before) or savings < (
                options.get("min_savings") or 0
            ):
                return StoreResult(
                    source,
                    destination,
                    before,
                    before,
                    False,
                    "no store candidate meets size policy",
                    detail,
                )
            generation = run_operation("zarr-store", "generation", source, options=options)
            if generation["source_generation"] != info["source_generation"]:
                raise ValueError("source store changed before publication")
            publish_directory(staging, destination)
            return StoreResult(
                source,
                destination,
                before,
                after,
                True,
                "verified atomic no-replace publication",
                detail,
            )
        finally:
            if staging is not None:
                owner = os.path.dirname(staging)
                try:
                    current = os.lstat(owner)
                    if (
                        not stat.S_ISLNK(current.st_mode)
                        and (current.st_dev, current.st_ino) == owner_identity
                    ):
                        _cleanup_owned_directory(owner)
                except FileNotFoundError:
                    pass
