# -*- coding: utf-8 -*-

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PackResult:
    """Result of packing a single file."""
    filepath: str
    insize: int
    outsize: int
    savings_pct: float
    replaced: bool = True

    @property
    def savings_bytes(self) -> int:
        return self.insize - self.outsize


@dataclass
class RepackOptions:
    """Options for FileRepacker.repack / repack_zip_file."""
    debug: bool = False
    dryrun: bool = False
    quiet: bool = False
    ultra: bool = False
    deep_walking: bool = True
    pack_images: bool = True
    pack_archives: bool = True
    compression_level: int = 9
    jpeg_quality: Optional[int] = None
    png_quality: Optional[str] = None
    pdf_profile: Optional[str] = None
    wmv_lossless: bool = False
    lossy: bool = False
    convert_container: bool = True
    keep_if_larger: bool = True
    keep_meta: bool = False
    min_savings: Optional[float] = None
    max_extract_bytes: Optional[int] = None
    max_extract_ratio: Optional[float] = None
    repack_archive: bool = True
    log: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepackSummary:
    """Summary of repacking an archive or standalone file."""
    filepath: str = ""
    results: List[PackResult] = field(default_factory=list)
    total_insize: int = 0
    total_outsize: int = 0
    elapsed_seconds: float = 0.0
    inner_count: int = 0
    inner_insize: int = 0
    inner_outsize: int = 0

    @property
    def total_savings_bytes(self) -> int:
        return self.total_insize - self.total_outsize

    @property
    def total_savings_pct(self) -> float:
        if self.total_insize > 0:
            return (self.total_insize - self.total_outsize) * 100.0 / self.total_insize
        return 0.0

    def as_legacy_dict(self) -> Dict[str, Any]:
        """Dict shape used by the 0.1.x FileRepacker API."""
        return {
            'stats': [self.inner_count, self.inner_insize, self.inner_outsize],
            'files': [
                [r.filepath, r.insize, r.outsize, r.savings_pct] for r in self.results
            ],
            'final': [self.total_insize, self.total_outsize, self.total_savings_pct],
        }

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        return key in ('stats', 'files', 'final')

    def __getitem__(self, key: str) -> Any:
        data = self.as_legacy_dict()
        if key not in data:
            raise KeyError(key)
        return data[key]
