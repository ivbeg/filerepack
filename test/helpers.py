# -*- coding: utf-8 -*-

import re
from typing import Any

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def plain_output(result: Any) -> str:
    """CLI output with ANSI highlighting removed."""
    return _ANSI_ESCAPE.sub("", result.output)
