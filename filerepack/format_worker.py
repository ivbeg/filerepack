"""Private JSON worker protocol for bounded, passive format operations."""

import importlib
import json
import sys
from typing import Any, Dict, cast

from .format_support import Budget, FormatLimit, FormatLimits, UnsupportedFormat, _BUDGET, _OPTIONS
from .evidence import evidence_scope, loaded_packages

MODULES = {
    'stream-native': 'stream_worker',
    'font-native': 'fonts',
    'pdf-native': 'pdf_streams',
    'tracev3': 'tracev3',
    'warc-zopfli': 'warc',
    'arrow-native': 'columnar',
    'feather-native': 'columnar',
    'orc-native': 'columnar',
    'avro-native': 'avro',
    "officeart": "ole_recompress",
    "hwp-ole": "ole_recompress",
    "ole-embedded": "ole_transform",
    "ole-dedup": "ole_dedup",
    "ppt-ole": "ole_recompress",
    "r-serialization": "r_serialization",
    "mat": "mat",
    "hdf5-native": "hierarchical",
    "netcdf-native": "hierarchical",
    "tiff-native": "tiff",
    "checkpoint": "checkpoint",
    "spss": "spss",
    "zarr-store": "zarr_store",
    "safetensors": "model_formats",
    "gguf": "model_formats",
    "onnx": "model_formats",
}


def execute(request: Dict[str, Any], budget: Budget) -> Dict[str, Any]:
    module = importlib.import_module("filerepack." + MODULES[request["kind"]])
    return cast(
        Dict[str, Any],
        module.operate(
            request["kind"],
            request["action"],
            request["source"],
            request.get("candidate"),
            request.get("options", {}),
            budget,
        ),
    )


def main() -> None:
    budget = Budget(FormatLimits())
    evidence: list = []
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("worker request too large")
        request = json.loads(raw)
        request.setdefault('options', {})['_optimization_depth'] = request.get('base_depth', 0)
        budget = Budget(FormatLimits(**request["limits"]))
        budget.depth(request.get('base_depth', 0))
        _BUDGET.set(budget)
        _OPTIONS.set(request.get('options', {}))
        with evidence_scope() as evidence:
            try:
                result = execute(request, budget)
            finally:
                loaded_packages()
        result["ok"] = True
    except Exception as exc:
        result = {"ok": False, "reason": str(exc), "limited": isinstance(exc, FormatLimit),
                  'unsupported': isinstance(exc, (UnsupportedFormat, ImportError))}
    result['evidence'] = evidence
    result["usage"] = {"decoded": budget.decoded, "written": budget.written, "nodes": budget.nodes}
    payload = json.dumps(result, ensure_ascii=True, allow_nan=False)
    if len(payload) > 65536:
        payload = json.dumps(
            {"ok": False, "reason": "worker result too large", "usage": result["usage"]}
        )
    sys.stdout.write(payload)


if __name__ == "__main__":
    main()
