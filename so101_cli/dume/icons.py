"""Glyphs (Nerd Font) con fallback ASCII, elegido según capabilities.

Los símbolos de estado ✓/✗/— viven en widgets/status_pill.py porque son unicode
básico (renderizan casi en cualquier lado); acá van los iconos "ricos" que
requieren una Nerd Font.
"""

from __future__ import annotations

# Requiere una Nerd Font instalada en el terminal (Warp/iTerm con MesloLGS NF, etc.).
_NERD: dict[str, str] = {
    "robot":    "\U000f06a9",  # 󰚩  nf-md-robot
    "follower": "",      #   nf-fa-robot-ish
    "leader":   "",      #   link
    "motor":    "",      #   cogs
    "camera":   "",      #   camera
    "dataset":  "",      #   database
    "model":    "",      #   brain
    "home":     "",      #   home
    "teleop":   "",      #   gamepad
    "record":   "",      #   circle (REC)
    "eval":     "",      #   play
    "train":    "",      #   cubes
    "diag":     "",      #   stethoscope
    "arrow":    "",      #   angle-right
    "warn":     "",      #   warning
}

_ASCII: dict[str, str] = {
    "robot":    "[DUM-E]",
    "follower": "F",
    "leader":   "L",
    "motor":    "M",
    "camera":   "C",
    "dataset":  "D",
    "model":    "W",
    "home":     "H",
    "teleop":   "T",
    "record":   "R",
    "eval":     "E",
    "train":    "G",
    "diag":     "?",
    "arrow":    ">",
    "warn":     "!",
}


class IconSet:
    """Mapa de iconos según el modo (Nerd Font o ASCII)."""

    def __init__(self, ascii_only: bool) -> None:
        self.ascii_only = ascii_only
        self._m = _ASCII if ascii_only else _NERD

    def get(self, name: str, default: str = "") -> str:
        return self._m.get(name, default)

    __call__ = get


def icons_for(caps) -> IconSet:
    return IconSet(caps.ascii_only)
