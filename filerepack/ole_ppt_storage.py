"""Duplicate inventory for already qualified PPT hosts; no storage rewriting."""

from typing import Dict

from .format_support import Budget
from .ole_ppt import read_records


def storage_diagnostics(data: bytes, budget: Budget, host: str = "ppt") -> Dict[str, object]:
    """Report exact duplicate wrappers without enabling persist-offset aliases.

    Apache POI 5.4.1 resolves only one of seven distinct object IDs after such
    sharing in the qualification corpus. Byte equality cannot prove independent
    editing. The strict host/index checks and all nested bytes remain unchanged.
    """
    if host != "ppt":
        return {}
    records = read_records(data)
    budget.consume(nodes=len(records))
    wrappers = [data[p : p + 8 + r.size] for p, r in records.items() if r.kind == 4113]
    distinct = set(wrappers)
    saved = sum(map(len, wrappers)) - sum(map(len, distinct))
    if not saved:
        return {}
    return {
        "ppt_storage_count": len(wrappers),
        "ppt_unique_storage_wrappers": len(distinct),
        "ppt_duplicate_wrapper_bytes": saved,
        "storage_sharing_skip": "identical OLE storage wrappers retained: persist-offset "
        "sharing is unqualified for independent resolution of distinct persist IDs",
    }
