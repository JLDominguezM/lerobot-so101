"""Render de un comando compuesto (`$ cal record-dataset ...`).

Se usa ya (preview de quick actions) y será central en los formularios de Fase 3,
donde cada campo del form re-compone el comando antes del suspend-and-run.
"""

from __future__ import annotations

from collections.abc import Iterable

from rich.text import Text
from textual.widgets import Static


class CommandPreview(Static):
    DEFAULT_CLASSES = "command-preview"

    def __init__(self, parts: Iterable[str] | None = None, **kw) -> None:
        super().__init__(**kw)
        self._parts = list(parts or [])

    def on_mount(self) -> None:
        self._render()

    def set_command(self, parts: Iterable[str]) -> None:
        self._parts = list(parts)
        self._render()

    def _render(self) -> None:
        if not self._parts:
            self.update(Text("—", style="dim"))
            return
        t = Text()
        t.append("$ ", style="bold green")
        t.append(" ".join(self._parts), style="bold")
        self.update(t)
