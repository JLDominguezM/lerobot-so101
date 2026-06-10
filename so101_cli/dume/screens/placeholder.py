"""Vista 'próxima fase' para entradas del sidebar aún no implementadas."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Center, Middle, Vertical
from textual.widgets import Static

from ..theme import AMBER


class PlaceholderView(Vertical):
    """Cartel centrado: nombre de la vista + aviso de que llega en otra fase."""

    def __init__(self, view, icons) -> None:
        super().__init__()
        self._view = view
        self._icons = icons

    def compose(self):
        glyph = self._icons.get(self._view.icon, "")
        t = Text()
        t.append(f"{glyph}  {self._view.label}\n\n", style="bold")
        t.append("Próxima fase — aún no implementado.\n", style=AMBER)
        t.append("\nElegí otra vista en el sidebar (1 = Home).", style="dim")
        with Middle():
            with Center():
                yield Static(t, classes="placeholder")
