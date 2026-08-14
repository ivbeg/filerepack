# -*- coding: utf-8 -*-

"""Optional progress reporting for CLI commands (rich bar, else interval text)."""

import os
import sys
from typing import Any, Callable, Optional, TextIO


def stderr_is_tty() -> bool:
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


class ProgressReporter:
    """Rich progress bar when installed; otherwise prints every ``interval`` items."""

    def __init__(
        self,
        enabled: bool,
        *,
        interval: int = 10,
        description: str = "Repacking",
        echo: Optional[Callable[[str], None]] = None,
        stream: Optional[TextIO] = None,
    ) -> None:
        self.enabled = enabled
        self.interval = interval if interval > 0 else 10
        self.description = description
        self._echo = echo
        self._stream = stream if stream is not None else sys.stderr
        self._rich: Any = None
        self._task: Any = None
        self._total: Optional[int] = None
        if enabled:
            self._start_rich()

    def __enter__(self) -> "ProgressReporter":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _print(self, message: str) -> None:
        if self._echo is not None:
            self._echo(message)
            return
        print(message, file=self._stream)

    def _start_rich(self) -> None:
        try:
            from rich.console import Console
            from rich.progress import (
                BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
                TextColumn, TimeElapsedColumn,
            )
        except ImportError:
            return
        console = Console(file=self._stream, stderr=self._stream is sys.stderr)
        self._rich = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        )
        self._rich.start()
        self._task = self._rich.add_task(self.description, total=None)

    def set_stage(self, description: str, total: Optional[int] = None) -> None:
        if not self.enabled:
            return
        self.description = description
        self._total = total
        if self._rich is not None and self._task is not None:
            self._rich.update(
                self._task, description=description, completed=0, total=total,
            )
            return
        self._print(f"{description}...")

    def update(self, completed: int, name: str = "") -> None:
        if not self.enabled:
            return
        if self._rich is not None and self._task is not None:
            label = self.description
            if name:
                short = os.path.basename(name)
                if len(short) > 40:
                    short = short[:37] + "..."
                label = f"{self.description} {short}"
            self._rich.update(self._task, completed=completed, description=label)
            return
        total = self._total
        if total and completed % self.interval == 0:
            self._print(f"Progress: {completed}/{total} files processed")

    def close(self) -> None:
        if self._rich is not None:
            self._rich.stop()
            self._rich = None
            self._task = None

    def hook(
        self,
        event: str,
        *,
        current: int = 0,
        total: int = 0,
        name: str = "",
    ) -> None:
        """FileRepacker progress callback: extract / files / file / write / standalone."""
        if event == "extract":
            self.set_stage("Extracting")
        elif event == "files":
            self.set_stage("Optimizing", total=total or None)
        elif event == "file":
            self.update(current, name=name)
        elif event == "write":
            self.set_stage("Rewriting")
        elif event == "standalone":
            label = f"Repacking {os.path.basename(name)}" if name else "Repacking"
            self.set_stage(label)
