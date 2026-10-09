# -*- coding: utf-8 -*-

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Protocol, cast

from .validation import validate_options
from .outcomes import RepackOutcome, Status

_UNSET = object()
_PROFILE_DEFAULTS = {'compression_level': 9, 'ultra': False, 'keep_meta': False, 'lossy': False}


class ProgressHook(Protocol):
    def __call__(
        self, event: str, *, current: int = 0, total: int = 0, name: str = '',
    ) -> None:
        ...


@dataclass
class PackResult:
    """Result of packing a single file."""
    filepath: str
    insize: int
    outsize: int
    savings_pct: float
    replaced: bool = True
    reason: str = ''
    details: Dict[str, Any] = field(default_factory=dict)
    status: Optional[Status] = None
    reason_code: str = ''
    source: str = ''
    member: Optional[str] = None
    published: bool = False

    @property
    def savings_bytes(self) -> int:
        return self.insize - self.outsize


@dataclass
class RepackOptions:
    """Options for FileRepacker.repack / repack_zip_file."""
    debug: bool = False
    profile: Optional[str] = None
    profile_version: Optional[int] = None
    tool_threads: int = 1
    dryrun: bool = False
    quiet: bool = False
    ultra: bool = cast(bool, _UNSET)
    deep_walking: bool = True
    pack_images: bool = True
    pack_archives: bool = True
    compression_level: int = cast(int, _UNSET)
    jpeg_quality: Optional[int] = None
    png_quality: Optional[str] = None
    pdf_profile: Optional[str] = None
    wmv_lossless: bool = False
    video_mode: Optional[str] = None
    lossy: bool = cast(bool, _UNSET)
    convert_container: bool = True
    keep_if_larger: bool = True
    keep_meta: bool = cast(bool, _UNSET)
    min_savings: Optional[float] = None
    max_extract_bytes: Optional[int] = None
    max_extract_ratio: Optional[float] = None
    repack_archive: bool = True
    log: bool = False
    overwrite: bool = False
    backup: bool = False
    backup_dir: Optional[str] = None
    durability: str = 'atomic'
    pdf_linearize: bool = False
    ole_recompress: bool = False
    ole_embedded_recompress: bool = False
    ole_deduplicate_images: bool = False
    r_compression: str = 'preserve'
    checkpoint_compatibility: str = 'preserve-mmap'
    zarr_codec_policy: str = 'preserve'
    experimental_formats: bool = False
    sqlite_offline: bool = False
    exclude_members: List[str] = field(default_factory=list)
    allow_categories: Optional[List[str]] = None
    skip_categories: List[str] = field(default_factory=list)
    max_depth: Optional[int] = None
    format_max_decoded_bytes: int = 512 * 1024 * 1024
    format_max_memory_bytes: int = 256 * 1024 * 1024
    format_max_scratch_bytes: int = 2 * 1024 * 1024 * 1024
    format_max_nodes: int = 100000
    format_max_depth: int = 16
    format_timeout: float = 120.0

    def __post_init__(self) -> None:
        from .profiles import resolve_profile
        explicit = {name: getattr(self, name) for name in _PROFILE_DEFAULTS
                    if getattr(self, name) is not _UNSET}
        effective = {**_PROFILE_DEFAULTS, **resolve_profile(self.profile, explicit)}
        for name in _PROFILE_DEFAULTS:
            setattr(self, name, effective[name])
        if self.profile and self.profile_version is None:
            self.profile_version = effective['profile_version']
        normalized = validate_options(asdict(self))
        self.pdf_profile = normalized['pdf_profile']
        self.png_quality = normalized.get('png_quality')

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
    outcome: Optional[RepackOutcome] = None
    transformed: bool = False
    published: bool = False
    member_outcomes: List[RepackOutcome] = field(default_factory=list)

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
