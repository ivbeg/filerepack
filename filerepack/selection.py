"""Logical member globbing and inherited category/optimization-depth policy."""

import re
from functools import lru_cache
from typing import Any, Dict

CATEGORIES = frozenset(('image', 'audio', 'video', 'document', 'data'))


@lru_cache(maxsize=1024)
def _pattern(pattern: str) -> re.Pattern:
    if not isinstance(pattern, str) or not pattern or len(pattern) > 4096 or '\0' in pattern:
        raise ValueError('Member patterns must be nonempty strings up to 4096 characters')
    pattern = pattern + '**' if pattern.endswith('/') else pattern
    parts = []
    index = 0
    while index < len(pattern):
        token = pattern[index]
        if pattern[index:index + 3] == '**/':
            parts.append('(?:.*/)?')
            index += 3
        elif pattern[index:index + 2] == '**':
            parts.append('.*')
            index += 2
        else:
            parts.append('[^/]*' if token == '*' else '[^/]' if token == '?' else re.escape(token))
            index += 1
    return re.compile(''.join(parts) + '\\Z')


def excluded_member(name: str, options: Dict[str, Any]) -> bool:
    return any(_pattern(pattern).fullmatch(name) is not None
               for pattern in options.get('exclude_members', ()))


def category_enabled(category: str, options: Dict[str, Any]) -> bool:
    if category in ('image', 'audio', 'video') and not options.get('pack_images', True):
        return False
    if category in options.get('skip_categories', ()):
        return False
    allowed = options.get('allow_categories')
    return allowed is None or category in allowed


def depth_enabled(depth: int, options: Dict[str, Any]) -> bool:
    maximum = options.get('max_depth')
    return maximum is None or depth <= maximum


def embedded_images_enabled(options: Dict[str, Any]) -> bool:
    return category_enabled('image', options) and depth_enabled(
        options.get('_optimization_depth', 0) + 1, options,
    )
