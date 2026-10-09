# -*- coding: utf-8 -*-

import inspect
import re
from typing import Any

from typer.testing import CliRunner

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def plain_output(result: Any) -> str:
    """CLI output with ANSI highlighting removed."""
    return _ANSI_ESCAPE.sub("", result.output)


def separated_cli_runner() -> CliRunner:
    """Keep JSON/CSV stdout separate from errors on both Click 8.1 and 8.2+."""
    if 'mix_stderr' in inspect.signature(CliRunner).parameters:
        return CliRunner(mix_stderr=False)
    return CliRunner()
