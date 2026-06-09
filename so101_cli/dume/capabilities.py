"""Detección de capacidades del terminal: programa, truecolor y modo de iconos.

No elige el protocolo de imágenes — de eso se encarga `textual-image` solo
(TGP/iTerm2/sixel → half-cell). Acá sólo decidimos el set de iconos (Nerd Font
vs ASCII) y exponemos info útil para el resto de la TUI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    term_program: str   # "WarpTerminal", "iTerm.app", "Apple_Terminal", "ghostty", ...
    truecolor: bool
    ascii_only: bool    # sin Nerd Font ni imágenes "ricas"

    @property
    def use_nerd_font(self) -> bool:
        return not self.ascii_only


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no")


def detect(ascii_flag: bool = False) -> Capabilities:
    """Construye Capabilities a partir del entorno (+ flag --ascii)."""
    term_program = os.environ.get("TERM_PROGRAM", "") or os.environ.get("TERM", "")
    colorterm = os.environ.get("COLORTERM", "").strip().lower()
    truecolor = colorterm in ("truecolor", "24bit")
    ascii_only = bool(ascii_flag) or _env_truthy("DUME_ASCII")
    return Capabilities(term_program=term_program, truecolor=truecolor, ascii_only=ascii_only)
