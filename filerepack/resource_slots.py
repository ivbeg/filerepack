"""Conservative coordinator credits for simultaneous root-input grants."""

import os
from dataclasses import dataclass
from typing import Dict, Optional

from .models import RepackOptions


@dataclass(frozen=True)
class ResourceSlots:
    requested: int
    granted: int
    memory_bytes: int
    scratch_bytes: int
    cpu_threads: int

    def to_dict(self) -> Dict[str, int]:
        return dict(self.__dict__)


def reserve_slots(jobs: int, options: RepackOptions, memory: int = 2147483648,
                  scratch: int = 8589934592, cpu: Optional[int] = None) -> ResourceSlots:
    cpu = cpu if cpu is not None else (os.cpu_count() or 1)
    if any(type(value) is not int or value < 1 for value in (jobs, memory, scratch, cpu)):
        raise ValueError('Bulk memory, scratch and CPU grants must be positive integers')
    granted = min(jobs, memory // options.format_max_memory_bytes,
                  scratch // options.format_max_scratch_bytes, cpu // options.tool_threads)
    if granted < 1:
        raise ValueError('A root-input resource grant exceeds the aggregate bulk budget')
    return ResourceSlots(jobs, granted, memory, scratch, cpu)
