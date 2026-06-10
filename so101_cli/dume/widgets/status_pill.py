"""Chip de estado ✓/✗/— con color. Usa unicode básico (no requiere Nerd Font)."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ..theme import AMBER, GREEN, RED

OK = "ok"
BAD = "bad"
UNKNOWN = "unknown"

_GLYPH = {OK: "✓", BAD: "✗", UNKNOWN: "—"}
_GLYPH_ASCII = {OK: "OK", BAD: "X", UNKNOWN: "-"}
_COLOR = {OK: GREEN, BAD: RED, UNKNOWN: AMBER}


def pill_text(state: str, label: str = "", ascii_only: bool = False) -> Text:
    """Rich Text con glyph coloreado + label opcional."""
    glyph = (_GLYPH_ASCII if ascii_only else _GLYPH).get(state, "?")
    s = f"{glyph} {label}".rstrip() if label else glyph
    return Text(s, style=_COLOR.get(state, "white"))


class StatusPill(Static):
    """Pill como widget (p.ej. el resumen global del header)."""

    def __init__(self, state: str = UNKNOWN, label: str = "",
                 ascii_only: bool = False, **kw) -> None:
        self._state = state
        self._label = label
        self._ascii = ascii_only
        super().__init__(pill_text(state, label, ascii_only), **kw)

    def update_state(self, state: str, label: str | None = None) -> None:
        self._state = state
        if label is not None:
            self._label = label
        self.update(pill_text(self._state, self._label, self._ascii))
