"""Tema 'hacker': fósforo verde sobre negro (CRT). Una sola fuente de color.

`HACKER_THEME` alimenta TODAS las variables CSS de la TUI ($primary, $surface,
$accent, $panel…), así que el cromado (bordes, header, footer, sidebar, scrollbars)
se vuelve verde neón sin tocar cada widget. Las constantes NEON/GREEN/AMBER/RED…
se usan en los renderables Rich (status pill, cards, command preview) para que el
color literal también sea coherente con el tema. Tunear el look = tocar acá.
"""

from __future__ import annotations

from textual.theme import Theme

# --- paleta CRT fósforo --------------------------------------------------
BLACK      = "#000000"
NEAR_BLACK = "#020802"
SURFACE    = "#07140b"   # fondo de las vistas (negro con tinte verde)
PANEL      = "#0b1f10"   # sidebar / paneles (un punto más claro)
GREEN      = "#00ff66"   # primario: bordes, énfasis, ✓
NEON       = "#39ff14"   # acento: títulos, teclas, prompts (lima brillante)
MINT       = "#9dffc4"   # secundario suave / descripciones
TEXT       = "#c8ffd4"   # texto principal (verde menta claro)
DIM        = "#3f8d5e"   # texto atenuado (verde apagado, no gris)
AMBER      = "#ffcf3a"   # advertencias
RED        = "#ff3b5c"   # errores

# Estilos Rich reutilizables (string de estilo, no Color).
S_KEY  = f"bold {NEON}"   # teclas de atajo / bullets activos
S_OK   = GREEN
S_BAD  = RED
S_WARN = AMBER


HACKER_THEME = Theme(
    name="hacker",
    primary=GREEN,
    secondary=MINT,
    accent=NEON,
    foreground=TEXT,
    background=BLACK,
    surface=SURFACE,
    panel=PANEL,
    success=GREEN,
    warning=AMBER,
    error=RED,
    boost="#00ff6614",   # overlay verde muy tenue (hex8 con alpha)
    dark=True,
    variables={
        "border": GREEN,
        "border-blurred": "#0e3a20",
        "footer-key-foreground": NEON,
        "footer-description-foreground": MINT,
        "footer-background": NEAR_BLACK,
        "block-cursor-foreground": BLACK,
        "block-cursor-background": GREEN,
        "block-cursor-text-style": "bold",
        "input-selection-background": "#00ff6640",
        "scrollbar": "#0e3a20",
        "scrollbar-hover": GREEN,
        "scrollbar-active": NEON,
        "scrollbar-background": SURFACE,
    },
)


def install(app) -> None:
    """Registra y activa el tema hacker. Tolerante: si algo falla, no rompe la app."""
    try:
        app.register_theme(HACKER_THEME)
        app.theme = "hacker"
    except Exception:
        pass
