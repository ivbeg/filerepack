"""Terminal operation reports and scoped diagnostics for legacy packer adapters."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Literal, Optional

Status = Literal['replaced', 'unchanged', 'skipped', 'unsupported', 'failed',
                 'predicted', 'cancelled']


@dataclass
class Diagnostic:
    status: Status
    reason_code: str
    message: str


_DIAGNOSTICS: ContextVar[Optional[List[Diagnostic]]] = ContextVar(
    'filerepack_diagnostics', default=None,
)


def record(status: Status, reason_code: str, message: str) -> None:
    diagnostics = _DIAGNOSTICS.get()
    if diagnostics is not None:
        diagnostics.append(Diagnostic(status, reason_code, message))


@contextmanager
def diagnostic_scope() -> Iterator[List[Diagnostic]]:
    diagnostics: List[Diagnostic] = []
    token = _DIAGNOSTICS.set(diagnostics)
    try:
        yield diagnostics
    finally:
        _DIAGNOSTICS.reset(token)


@dataclass
class RepackOutcome:
    source: str
    destination: str
    status: Status
    original_size: int = 0
    final_size: int = 0
    reason_code: str = ''
    reason: str = ''
    elapsed_seconds: float = 0.0
    published: bool = False
    member: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result.update(
            file=self.source, output_file=self.destination,
            elapsed_time=self.elapsed_seconds,
            savings_bytes=self.original_size - self.final_size,
            savings_percent=(100 * (self.original_size - self.final_size) /
                             self.original_size if self.original_size else 0.0),
        )
        return result


def refusal(reason: str) -> Diagnostic:
    """Translate existing preserving adapters' human reasons at their boundary."""
    text = reason.lower()
    if 'budget' in text or 'limit exceeded' in text:
        return Diagnostic('skipped', 'resource_limit', reason)
    if 'cancel' in text or 'interrupt' in text:
        return Diagnostic('cancelled', 'cancelled', reason)
    if 'protected' in text or 'signed' in text or 'encrypted' in text:
        return Diagnostic('skipped', 'protected', reason)
    if 'unsupported' in text or 'experimental' in text or 'inspection only' in text:
        return Diagnostic('unsupported', 'unsupported_profile', reason)
    if 'unavailable' in text or 'requires ' in text or 'missing tool' in text:
        return Diagnostic('unsupported', 'missing_dependency', reason)
    if 'corrupt' in text or 'invalid' in text or 'malformed' in text:
        return Diagnostic('failed', 'invalid_input', reason)
    return Diagnostic('unchanged', 'no_benefit', reason)
