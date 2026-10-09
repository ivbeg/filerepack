"""Isolated opt-in OLE content recompression; workers never publish destinations."""

import logging
import hashlib
import os
import subprocess
import struct
import tempfile
import time
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional

from . import candidates as tx
from .format_support import (
    Budget,
    FormatLimit,
    format_scope,
    read_small,
    run_operation,
    unchanged,
    write_bytes,
)
from .models import PackResult
from .ole_ppt_records import DOCUMENT, equal_layouts, inspect_records, reencode
from .ole_verify import CompoundFile, independent_manifest
from .transactions import FileSnapshot

_DEADLINE: ContextVar[Optional[float]] = ContextVar("filerepack_ppt_deadline", default=None)


def run_ppt_operation(
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    deadline = _DEADLINE.get()
    return run_operation(
        "ppt-ole",
        action,
        source,
        candidate,
        options,
        deadline=deadline if deadline is not None else time.monotonic() + 120,
    )


def run_art_operation(
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    deadline = _DEADLINE.get()
    return run_operation(
        "officeart",
        action,
        source,
        candidate,
        options,
        deadline=deadline if deadline is not None else time.monotonic() + 120,
    )


def run_hwp_operation(
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return run_operation(
        "hwp-ole",
        action,
        source,
        candidate,
        options,
        deadline=_DEADLINE.get() or time.monotonic() + 120,
    )


def _command(arguments: List[str], budget: Budget) -> subprocess.CompletedProcess:
    budget.check()
    result = subprocess.run(arguments, capture_output=True, timeout=budget.remaining()["seconds"])
    budget.check()
    if len(result.stdout) + len(result.stderr) > 1024 * 1024:
        raise FormatLimit("OLE helper diagnostic limit exceeded")
    return result


def _read(path: str, budget: Budget) -> CompoundFile:
    compound = CompoundFile(read_small(path, budget))
    budget.consume(nodes=len(compound.entries))
    independent_manifest(path, compound)
    return compound


def _native(
    writer: str,
    source: str,
    candidate: str,
    budget: Budget,
    replacements: Optional[List[str]] = None,
) -> CompoundFile:
    arguments = [writer] + (["--replace-ppt-streams"] + replacements if replacements else [])
    if _command(arguments + [source, candidate], budget).returncode:
        raise ValueError("OLE native writer failed")
    budget.consume(written=os.path.getsize(candidate))
    return _read(candidate, budget)


def _rewrite(
    source: str,
    candidate: str,
    options: Dict[str, Any],
    budget: Budget,
    original: Optional[CompoundFile] = None,
) -> Dict[str, Any]:
    from .ole import _profile

    if original is None:
        original = _read(source, budget)
    _profile(original, "ppt")
    writer = options["ole_writer"]
    baseline = _native(writer, source, candidate, budget)
    _profile(baseline, "ppt")
    if original.manifest != baseline.manifest:
        raise ValueError("OLE baseline changed live stream bytes or metadata")
    details: Dict[str, Any] = {
        "strategy": "ole-compaction",
        "compaction_bytes": len(baseline.data),
        "additional_savings_bytes": 0,
    }
    try:
        layout = inspect_records(original, budget)
    except FormatLimit:
        raise
    except ValueError as exc:
        details["recompression_skip"] = str(exc)
        return {"verify": "ole", "details": details}
    capabilities = _command([writer, "--capabilities"], budget)
    if capabilities.returncode or b"ppt-stream-replacement-v1" not in capabilities.stdout.split():
        details["recompression_skip"] = "native helper lacks PPT replacement capability"
        return {"verify": "ole", "details": details}
    document, current, encoders = reencode(layout, budget)
    if document == original.streams[DOCUMENT]:
        details["recompression_skip"] = "no smaller compressed object wrappers"
        return {"verify": "ole", "details": details}
    with tempfile.TemporaryDirectory(prefix="streams-", dir=os.path.dirname(candidate)) as scratch:
        document_path = os.path.join(scratch, "document")
        current_path = os.path.join(scratch, "current")
        write_bytes(document_path, document, budget)
        write_bytes(current_path, current, budget)
        replacement = os.path.join(scratch, "candidate.ppt")
        with open(replacement, "xb"):
            pass
        rebuilt = _native(writer, source, replacement, budget, [document_path, current_path])
        after = inspect_records(rebuilt, budget)
        if not equal_layouts(layout, after):
            raise ValueError("PPT record candidate did not preserve the intended content")
        if len(rebuilt.data) >= len(baseline.data):
            details["recompression_skip"] = "record savings do not improve physical compaction size"
            return {"verify": "ole", "details": details}
        os.replace(replacement, candidate)
        details.update(
            strategy="ppt-ole-recompression",
            encoders=encoders,
            additional_savings_bytes=len(baseline.data) - len(rebuilt.data),
            document_stream_savings_bytes=len(layout.data) - len(after.data),
            decoded_storage_bytes=sum(len(obj.raw) for obj in layout.objects),
        )
        return {"verify": "ppt-ole", "details": details}


def _art_native(
    writer: str,
    source: str,
    candidate: str,
    host: str,
    replacements: Dict[tuple, bytes],
    budget: Budget,
    *,
    release_payloads: bool = False,
) -> CompoundFile:
    names = {
        "doc": ("WordDocument", "Data"),
        "xls": ("Workbook",),
        "ppt": ("PowerPoint Document", "Pictures"),
    }[host]
    if set(replacements) == {(name,) for name in names}:
        with tempfile.TemporaryDirectory(
            prefix="art-streams-", dir=os.path.dirname(candidate)
        ) as scratch:
            inputs = []
            for index, name in enumerate(names):
                path = os.path.join(scratch, str(index))
                write_bytes(path, replacements[(name,)], budget)
                inputs.append(path)
            if release_payloads:
                replacements.clear()
            if _command(
                [writer, "--replace-officeart-streams", host, *inputs, source, candidate], budget
            ).returncode:
                raise ValueError("OfficeArt native root-stream replacement failed")
        budget.consume(written=os.path.getsize(candidate))
        return _read(candidate, budget)
    return planned_native(
        writer, source, candidate, host, replacements, budget, release_payloads=release_payloads
    )


def planned_native(
    writer: str,
    source: str,
    candidate: str,
    host: str,
    replacements: Dict[tuple, bytes],
    budget: Budget,
    *,
    release_payloads: bool = False,
) -> CompoundFile:
    if not replacements or len(replacements) > 8192:
        raise ValueError("Invalid qualified replacement count")
    directory = os.path.dirname(candidate)
    with tempfile.TemporaryDirectory(prefix="art-streams-", dir=directory) as scratch:
        plan = bytearray(b"FRPLAN01" + struct.pack("<I", len(replacements)))
        for index, (parts, data) in enumerate(sorted(replacements.items())):
            if not parts or any(not p or any(c in p for c in "/\\\0") for p in parts):
                raise ValueError("Invalid qualified stream path")
            path = os.path.join(scratch, str(index))
            write_bytes(path, data, budget)
            name, file = "/".join(parts).encode(), path.encode()
            if len(name) > 65535 or len(file) > 65535:
                raise ValueError("Qualified plan path limit")
            plan.extend(struct.pack("<HH", len(name), len(file)) + name + file)
        if release_payloads:
            replacements.clear()
            del data
        manifest = os.path.join(scratch, "plan")
        write_bytes(manifest, bytes(plan), budget)
        arguments = [writer, "--replace-qualified-streams-v1", host, manifest, source, candidate]
        if _command(arguments, budget).returncode:
            raise ValueError("OfficeArt native root-stream replacement failed")
    budget.consume(written=os.path.getsize(candidate))
    return _read(candidate, budget)


def _rewrite_all(
    source: str,
    candidate: str,
    options: Dict[str, Any],
    budget: Budget,
    transform: Optional[Callable[[CompoundFile, Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    from .ole import _profile
    from .ole_art_layout import equal_art, inspect_art

    source_snapshot = FileSnapshot.capture(source)
    original = _read(source, budget)
    host, _ = _profile(original, os.path.splitext(source)[1][1:].lower())
    writer = options["ole_writer"]
    info: Dict[str, Any]
    if host == "ppt":
        # Each representation has its own verifier. Never combine patch plans.
        # Retain the already independently verified source instead of keeping
        # two full data/stream copies alive throughout native compaction.
        info = _rewrite(source, candidate, options, budget, original=original)
    else:
        baseline = _native(writer, source, candidate, budget)
        _profile(baseline, host)
        if baseline.manifest != original.manifest:
            raise ValueError("OLE baseline changed live stream bytes or metadata")
        info = {
            "verify": "ole",
            "details": {
                "strategy": "ole-compaction",
                "compaction_bytes": len(baseline.data),
                "additional_savings_bytes": 0,
            },
        }
    # Additional independent strategies use the already verified source before
    # PNG encoding. Afterwards its carrier can be released without a new parse.
    if transform is not None:
        info = transform(original, info)
    details = info["details"]
    try:
        layout = inspect_art(original, budget, pack_images=options.get("pack_images", True))
    except FormatLimit:
        raise
    except ValueError as exc:
        details["officeart_skip"] = str(exc)
        if info["verify"] == "ole":
            details["recompression_skip"] = str(exc)
        return info
    from .ole_ppt_storage import storage_diagnostics

    details.update(storage_diagnostics(original.streams.get(DOCUMENT, b""), budget, host))
    # The adapter owns precisely the application bytes it compares/rebuilds.
    # Its source snapshot contains independently verified metadata and sizes,
    # so the duplicate CFB carrier/allocation tables can be released now.
    del original
    capabilities = _command([writer, "--capabilities"], budget)
    if (
        capabilities.returncode
        or b"officeart-stream-replacement-v1" not in capabilities.stdout.split()
    ):
        reason = "native helper lacks OfficeArt replacement capability (requires 0.3.0+)"
        details["officeart_skip"] = reason
        if info["verify"] == "ole":
            details["recompression_skip"] = reason
        return info
    replacements, diagnostics = layout.reencode(budget, ultra=options.get("ultra", False))
    legacy = {
        "doc": {("WordDocument",), ("Data",)},
        "xls": {("Workbook",)},
        "ppt": {("PowerPoint Document",), ("Pictures",)},
    }
    if (
        set(replacements) != legacy[host]
        and b"qualified-stream-replacement-v1" not in capabilities.stdout.split()
    ):
        details["officeart_skip"] = "this OfficeArt layout requires native helper 0.4.0+"
        return info
    details["officeart"] = diagnostics
    if not diagnostics["recompressed_metafiles"] and not diagnostics["recompressed_rasters"]:
        reason = "no smaller qualified OfficeArt picture representations"
        details["officeart_skip"] = reason
        if info["verify"] == "ole":
            details["recompression_skip"] = reason
        return info
    directory = os.path.dirname(candidate)
    identity = layout.identity()
    del layout
    with tempfile.TemporaryDirectory(prefix="art-candidate-", dir=directory) as scratch:
        output = os.path.join(scratch, "candidate." + host)
        with open(output, "xb"):
            pass
        rebuilt = _art_native(
            writer, source, output, host, replacements, budget, release_payloads=True
        )
        rebuilt_size = len(rebuilt.data)
        rebuilt_sha256 = hashlib.sha256(rebuilt.data).hexdigest()
        del replacements
        after = inspect_art(rebuilt, budget)
        del rebuilt
        if not equal_art(identity, after):
            raise ValueError("OfficeArt candidate did not preserve intended content/references")
        details["officeart_candidate_bytes"] = rebuilt_size
        if rebuilt_size >= os.path.getsize(candidate):
            reason = "OfficeArt stream savings do not improve the selected physical file size"
            details["officeart_skip"] = reason
            if info["verify"] == "ole":
                details["recompression_skip"] = reason
            return info
        source_snapshot.require_unchanged()
        os.replace(output, candidate)
        details.pop("recompression_skip", None)
        details.update(
            diagnostics,
            strategy="ole-officeart-recompression",
            additional_savings_bytes=details["compaction_bytes"] - rebuilt_size,
        )
        # The worker independently parsed the final complete host above.
        # Bind that check to bytes so publication need not decode all PNGs
        # again with a depleted root budget and a different selection.
        return {
            "verify": "officeart", "details": details,
            "verified_content": {
                "source_sha256": source_snapshot.checksum,
                "candidate_sha256": rebuilt_sha256,
            },
        }


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    if kind == "hwp-ole":
        from .ole_hwp import inspect_hwp

        if action == "rewrite" and candidate is not None:
            return rewrite_hwp(source, candidate, options, budget)
        original_hwp = inspect_hwp(_read(source, budget), budget)
        if action == "inspect":
            return {"streams": len(original_hwp.decoded)}
        if action == "compare" and candidate is not None:
            after_hwp = inspect_hwp(_read(candidate, budget), budget)
            return {
                "equal": original_hwp.fingerprint() == after_hwp.fingerprint()
                and all(
                    len(after_hwp.compound.streams[p]) <= len(original_hwp.compound.streams[p])
                    for p in original_hwp.decoded
                )
            }
        raise ValueError("Unknown HWP worker action")
    if action == "rewrite":
        if candidate is None:
            raise ValueError("Missing private PPT candidate")
        return _rewrite_all(source, candidate, options, budget)
    if kind == "officeart":
        from .ole_art_layout import equal_art, inspect_art

        art = inspect_art(_read(source, budget), budget)
        if action == "inspect":
            return {"host": art.host, "metafiles": len(art.metafiles)}
        if action == "compare" and candidate is not None:
            return {"equal": equal_art(art, inspect_art(_read(candidate, budget), budget))}
        raise ValueError("Unknown OfficeArt worker action")
    original = inspect_records(_read(source, budget), budget)
    if action == "inspect":
        return {"objects": len(original.objects)}
    if action == "compare" and candidate is not None:
        after = inspect_records(_read(candidate, budget), budget)
        return {"equal": equal_layouts(original, after)}
    raise ValueError("Unknown PPT worker action")


def pack_ppt_records(filepath: str, writer: str, options: Dict[str, Any]) -> Optional[PackResult]:
    return _pack_records(filepath, writer, options, run_ppt_operation)


def pack_art_records(filepath: str, writer: str, options: Dict[str, Any]) -> Optional[PackResult]:
    return _pack_records(filepath, writer, options, run_art_operation)


def pack_hwp_records(filepath: str, writer: str, options: Dict[str, Any]) -> Optional[PackResult]:
    return _pack_records(filepath, writer, options, run_hwp_operation)


def rewrite_hwp(
    source: str, candidate: str, options: Dict[str, Any], budget: Budget
) -> Dict[str, Any]:
    from .ole_hwp import inspect_hwp, profile

    original = _read(source, budget)
    profile(original)
    writer = options["ole_writer"]
    baseline = _native(writer, source, candidate, budget)
    profile(baseline)
    if baseline.manifest != original.manifest:
        raise ValueError("HWP compaction changed logical content")
    info: Dict[str, Any] = {
        "verify": "ole",
        "details": {
            "strategy": "ole-compaction",
            "compaction_bytes": len(baseline.data),
            "additional_savings_bytes": 0,
        },
    }
    try:
        layout = inspect_hwp(original, budget)
    except FormatLimit:
        raise
    except ValueError as exc:
        info["details"]["recompression_skip"] = str(exc)
        return info
    capabilities = _command([writer, "--capabilities"], budget)
    if b"qualified-stream-replacement-v1" not in capabilities.stdout.split():
        info["details"]["recompression_skip"] = "HWP replacements require native helper 0.4.0+"
        return info
    replacements, diagnostics = layout.reencode(budget)
    info["details"]["hwp"] = diagnostics
    if not diagnostics["recompressed_streams"]:
        info["details"]["recompression_skip"] = "no smaller HWP streams"
        return info
    with tempfile.TemporaryDirectory(
        prefix="hwp-candidate-", dir=os.path.dirname(candidate)
    ) as scratch:
        output = os.path.join(scratch, "candidate.hwp")
        with open(output, "xb"):
            pass
        rebuilt = planned_native(writer, source, output, "hwp", replacements, budget)
        after = inspect_hwp(rebuilt, budget)
        if layout.fingerprint() != after.fingerprint():
            raise ValueError("HWP candidate changed decoded content or metadata")
        if len(rebuilt.data) >= len(baseline.data):
            info["details"]["recompression_skip"] = (
                "stream savings do not improve physical compaction size"
            )
            return info
        os.replace(output, candidate)
        info["verify"] = "hwp-ole"
        info["details"].update(
            strategy="hwp-stream-recompression",
            additional_savings_bytes=len(baseline.data) - len(rebuilt.data),
        )
    return info


def _pack_records(
    filepath: str, writer: str, options: Dict[str, Any], runner: Any
) -> Optional[PackResult]:
    """Called inside pack_ole's source transaction; share the root archive budget."""
    with format_scope(options) as budget:
        token = _DEADLINE.set(min(time.monotonic() + 120, budget.started + budget.limits.seconds))
        try:
            with tempfile.TemporaryDirectory(prefix="filerepack-ppt-operation-") as scratch:
                output = os.path.join(scratch, "candidate" + os.path.splitext(filepath)[1])
                with open(output, "xb"):
                    pass
                worker_options = dict(options, ole_writer=writer, _scratch_directory=scratch)
                info = runner("rewrite", filepath, output, worker_options)
                verified = None
                proof = info.get("verified_content")
                if proof is not None:
                    if info["verify"] != "officeart":
                        raise ValueError("Unexpected worker preservation evidence")
                    source_snapshot = FileSnapshot.capture(filepath)
                    candidate_snapshot = FileSnapshot.capture(output)
                    if (source_snapshot.checksum != proof["source_sha256"]
                            or candidate_snapshot.checksum != proof["candidate_sha256"]):
                        raise ValueError("Files changed after worker preservation verification")
                    verified = tx.VerifiedCandidate(
                        info["verify"], source_snapshot, candidate_snapshot
                    )
                result = tx.commit_output(
                    output,
                    filepath,
                    os.path.getsize(filepath),
                    verify=info["verify"],
                    lossless=True,
                    verified=verified,
                    **tx.commit_kwargs(**options),
                )
                if result is not None:
                    result.details.update(info["details"], worker_usage=info["usage"])
                return result
        except (ValueError, OSError, ImportError) as exc:
            logging.warning("OLE content recompression skipped: %s", exc)
            return unchanged(filepath, str(exc), {"strategy": "unchanged"})
        finally:
            _DEADLINE.reset(token)
