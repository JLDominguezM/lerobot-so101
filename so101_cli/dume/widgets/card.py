"""Panel titulado reutilizable del cockpit (borde redondeado + border-title)."""

from __future__ import annotations

from rich.console import RenderableType
from textual.containers import Vertical
from textual.widgets import Static


class Card(Vertical):
    """Contenedor con título en el borde y un Static editable como cuerpo."""

    DEFAULT_CLASSES = "card"

    def __init__(self, title: str, *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self._title = title
        self.body = Static("…", classes="card-body")

    def compose(self):
        yield self.body

    def on_mount(self) -> None:
        self.border_title = self._title

    def set_body(self, renderable: RenderableType) -> None:
        self.body.update(renderable)
