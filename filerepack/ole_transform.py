"""Explicit OLE transformations with separate independently verified candidates."""

import os
import tempfile
import time
from typing import Any, Dict, Optional

from .format_support import Budget, FormatLimit, run_operation
from .models import PackResult
from .ole_verify import CompoundFile
from .ole_recompress import (
    _DEADLINE,
    _command,
    _native,
    _pack_records,
    _read,
    _rewrite_all,
    planned_native,
)


def run_transform_operation(
    action: str,
    source: str,
    candidate: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return run_operation(
        "ole-embedded",
        action,
        source,
        candidate,
        options,
        deadline=_DEADLINE.get() or time.monotonic() + 120,
    )


def pack_transform_records(
    filepath: str, writer: str, options: Dict[str, Any]
) -> Optional[PackResult]:
    return _pack_records(filepath, writer, options, run_transform_operation)


def rewrite(source: str, candidate: str, options: Dict[str, Any], budget: Budget) -> Dict[str, Any]:
    from .ole import _profile

    original = _read(source, budget)
    host, macros = _profile(original, os.path.splitext(source)[1][1:].lower())
    manifest = original.manifest
    writer = options["ole_writer"]

    def transform(parsed: CompoundFile, selected: Dict[str, Any]) -> Dict[str, Any]:
        if parsed.manifest != manifest:
            raise ValueError("OLE source changed between transformation passes")
        return _additional(source, candidate, options, budget, parsed, selected, host, macros)

    if options.get("ole_recompress") and host in ("doc", "xls", "ppt"):
        # The content operation owns its parsed source. Keeping this outer CFB
        # alive would retain another entire file and stream set during encoding.
        del original
        return _rewrite_all(source, candidate, options, budget, transform=transform)
    elif options.get("ole_recompress") and host == "hwp":
        from .ole_recompress import rewrite_hwp

        del original
        selected = rewrite_hwp(source, candidate, options, budget)
        original = _read(source, budget)
    else:
        baseline = _native(writer, source, candidate, budget)
        if baseline.manifest != original.manifest:
            raise ValueError("OLE compaction changed logical content")
        selected = {
            "verify": "ole",
            "details": {
                "strategy": "ole-compaction",
                "compaction_bytes": len(baseline.data),
                "additional_savings_bytes": 0,
            },
        }
    return transform(original, selected)


def _additional(
    source: str,
    candidate: str,
    options: Dict[str, Any],
    budget: Budget,
    original: CompoundFile,
    selected: Dict[str, Any],
    host: str,
    macros: bool,
) -> Dict[str, Any]:
    from .ole_embedded import compare, optimize

    writer = options["ole_writer"]
    details = selected["details"]
    capabilities = _command([writer, "--capabilities"], budget)
    ready = (
        b"qualified-object-extraction-v1" in capabilities.stdout.split()
        and b"qualified-stream-replacement-v1" in capabilities.stdout.split()
    )
    if options.get("ole_embedded_recompress"):
        try:
            if macros or host not in ("doc", "xls"):
                raise ValueError(
                    "embedded optimization requires a qualified macro-free DOC/XLS host"
                )
            if not ready:
                raise ValueError("embedded optimization requires native helper 0.4.0+")
            replacements, report = optimize(source, original, writer, options, budget)
            details["embedded"] = report
            if replacements:
                with tempfile.TemporaryDirectory(
                    prefix="nested-candidate-", dir=os.path.dirname(candidate)
                ) as scratch:
                    output = os.path.join(scratch, "candidate." + host)
                    with open(output, "xb"):
                        pass
                    rebuilt = planned_native(
                        writer, source, output, host + "-object", replacements, budget
                    )
                    if not compare(source, original, output, rebuilt, writer, options, budget):
                        raise ValueError(
                            "embedded candidate changed parent/child content or references"
                        )
                    if len(rebuilt.data) < os.path.getsize(candidate):
                        os.replace(output, candidate)
                        selected["verify"] = "ole-embedded"
                        details.update(
                            strategy="ole-embedded-recompression",
                            additional_savings_bytes=details["compaction_bytes"]
                            - len(rebuilt.data),
                        )
                    else:
                        report["skip"] = "child savings do not improve selected physical file size"
            else:
                report["skip"] = "no smaller qualified embedded payloads"
        except FormatLimit:
            raise
        except ValueError as exc:
            details["embedded_skip"] = str(exc)
    if options.get("ole_deduplicate_images"):
        from .ole_dedup import try_candidate

        selected = try_candidate(source, original, candidate, selected, writer, options, budget)
    return selected


def operate(
    kind: str,
    action: str,
    source: str,
    candidate: Optional[str],
    options: Dict[str, Any],
    budget: Budget,
) -> Dict[str, Any]:
    from .ole_embedded import compare, scopes
    from .tools import resolve_tool

    if action == "rewrite" and candidate is not None:
        return rewrite(source, candidate, options, budget)
    original = _read(source, budget)
    host, objects = scopes(original, budget)
    if action == "inspect":
        return {"host": host, "objects": len(objects)}
    if action == "compare" and candidate is not None:
        writer = options.get("ole_writer") or resolve_tool("ole_compactor")
        if not writer:
            raise ValueError("independent embedded comparison requires qualified native reader")
        return {
            "equal": compare(
                source, original, candidate, _read(candidate, budget), writer, options, budget
            )
        }
    raise ValueError("Unknown embedded operation")
