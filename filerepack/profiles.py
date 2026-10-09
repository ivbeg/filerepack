"""Versioned effort defaults with explicit override provenance."""

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RepackOptions

PROFILE_VERSION = 1
PROFILES = {
    'fast': {'compression_level': 3, 'ultra': False},
    'balanced': {'compression_level': 6, 'ultra': False},
    'maximum': {'compression_level': 9, 'ultra': True},
    'preserve': {'compression_level': 6, 'ultra': False, 'keep_meta': True},
}


def resolve_profile(name: Optional[str], overrides: Dict[str, Any]) -> Dict[str, Any]:
    if name is None:
        return dict(overrides)
    if name not in PROFILES:
        raise ValueError('profile must be fast, balanced, maximum or preserve')
    if overrides.get('profile_version') not in (None, PROFILE_VERSION):
        raise ValueError('Unsupported optimization profile version')
    return {'lossy': False, **PROFILES[name], **overrides, 'profile': name,
            'profile_version': PROFILE_VERSION}


def options_for_profile(name: str, **overrides: Any) -> 'RepackOptions':
    """Library builder: even false/default-valued overrides remain explicit."""
    from .models import RepackOptions
    return RepackOptions(**resolve_profile(name, overrides))
