"""Navegación lateral: lista de vistas (icono + label), teclado/mouse + teclas 1-9.

VIEWS es la fuente única del orden y de qué vistas son nativas vs placeholder;
lo consume también __main__ (para las choices del argv) y app.py (atajos 1-9).
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.message import Message
from textual.widgets import Label, ListItem, ListView


@dataclass(frozen=True)
class View:
    key: str       # id estable, p.ej. "home"
    label: str     # texto visible
    icon: str      # nombre en icons.py
    builtin: bool   # True = pantalla nativa; False = placeholder "próxima fase"


VIEWS: list[View] = [
    View("home",        "Home",        "home",    True),
    View("teleop",      "Teleop",      "teleop",  False),
    View("record",      "Record",      "record",  False),
    View("eval",        "Eval",        "eval",    False),
    View("train",       "Train",       "train",   False),
    View("datasets",    "Datasets",    "dataset", False),
    View("models",      "Models",      "model",   False),
    View("diagnostics", "Diagnostics", "diag",    False),
]


class Sidebar(ListView):
    """ListView de vistas; emite ViewSelected al elegir (Enter/click)."""

    class ViewSelected(Message):
        def __init__(self, view: View) -> None:
            self.view = view
            super().__init__()

    def __init__(self, icons, **kw) -> None:
        items = []
        for i, v in enumerate(VIEWS, start=1):
            glyph = icons.get(v.icon, "")
            tag = "" if v.builtin else "  ·"   # · marca vistas "próxima fase"
            items.append(ListItem(Label(f"{i} {glyph}  {v.label}{tag}"), id=f"nav-{v.key}"))
        super().__init__(*items, **kw)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is None or event.item.id is None:
            return
        key = event.item.id[len("nav-"):]
        view = next((v for v in VIEWS if v.key == key), None)
        if view is not None:
            self.post_message(self.ViewSelected(view))

    def highlight_view(self, key: str) -> None:
        for i, v in enumerate(VIEWS):
            if v.key == key:
                self.index = i
                return
