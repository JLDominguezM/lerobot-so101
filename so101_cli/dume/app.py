"""DumeApp: layout (header + sidebar + content), atajos globales, theme y navegación.

El sidebar es persistente; las "vistas" se montan/desmontan en #content. Los
atajos de teclado (refresh, quick actions, saltos 1-9) viven acá —no en las
vistas— para que funcionen tenga o no el foco la vista actual.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from . import theme
from .capabilities import detect
from .icons import icons_for
from .screens.home import HomeView
from .screens.placeholder import PlaceholderView
from .screens.teleop import TeleopView
from .widgets.sidebar import VIEWS, Sidebar


class HelpScreen(ModalScreen):
    """Overlay de ayuda con los atajos. Esc o ? para cerrar."""

    BINDINGS = [
        Binding("escape", "close", "Cerrar"),
        Binding("question_mark", "close", "Cerrar"),
        Binding("q", "close", "Cerrar"),
    ]

    def compose(self) -> ComposeResult:
        t = Text()
        t.append("DUM-E — atajos\n\n", style="bold")
        rows = [
            ("1-8", "saltar a una vista"),
            ("↑/↓ + Enter", "navegar el sidebar"),
            ("r", "refrescar el cockpit"),
            ("c", "check (suspende → cal)"),
            ("f", "find-ports"),
            ("s / S", "scan-bus follower / leader"),
            ("?", "esta ayuda"),
            ("q", "salir"),
        ]
        for k, d in rows:
            t.append(f"  {k:<16}", style=theme.S_KEY)
            t.append(f"{d}\n")
        yield Static(t, id="help-box")

    def action_close(self) -> None:
        self.dismiss()


class DumeApp(App):
    CSS_PATH = "dume.tcss"
    TITLE = "DUM-E"
    SUB_TITLE = "SO-101"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "quick('check')", "check", show=False),
        Binding("f", "quick('find-ports')", "find-ports", show=False),
        Binding("s", "quick('scan-bus','follower')", "scan F", show=False),
        Binding("S", "quick('scan-bus','leader')", "scan L", show=False),
        *[Binding(str(i), f"jump({i})", VIEWS[i - 1].label, show=False)
          for i in range(1, min(len(VIEWS), 9) + 1)],
    ]

    def __init__(self, start_view: str = "home", ascii_mode: bool = False) -> None:
        super().__init__()
        self.caps = detect(ascii_flag=ascii_mode)
        self.icons = icons_for(self.caps)
        self._start_view = start_view if any(v.key == start_view for v in VIEWS) else "home"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            yield Sidebar(self.icons, id="sidebar")
            yield Container(id="content")
        yield Footer()

    def on_mount(self) -> None:
        theme.install(self)
        self.show_view(self._start_view)

    # ---- navegación -----------------------------------------------------

    def show_view(self, key: str) -> None:
        view = next((v for v in VIEWS if v.key == key), VIEWS[0])
        content = self.query_one("#content", Container)
        content.remove_children()
        if view.key == "home" and view.builtin:
            content.mount(HomeView(self.caps, self.icons))
        elif view.key == "teleop" and view.builtin:
            content.mount(TeleopView(self.caps, self.icons))
        else:
            content.mount(PlaceholderView(view, self.icons))
        try:
            self.query_one(Sidebar).highlight_view(view.key)
        except Exception:
            pass

    def on_sidebar_view_selected(self, message: Sidebar.ViewSelected) -> None:
        self.show_view(message.view.key)

    # ---- acciones (atajos) ---------------------------------------------

    def action_jump(self, n: int) -> None:
        if 1 <= n <= len(VIEWS):
            self.show_view(VIEWS[n - 1].key)

    def action_refresh(self) -> None:
        view = self._content_view()
        if view is not None and hasattr(view, "refresh_view"):
            view.refresh_view()

    def action_quick(self, subcmd: str, which: str | None = None) -> None:
        from .engine.runner import run_cal

        args = (which,) if which else ()
        run_cal(self, subcmd, *args)
        self.action_refresh()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    # ---- helpers --------------------------------------------------------

    def _content_view(self):
        content = self.query_one("#content", Container)
        return content.children[0] if content.children else None

    def set_connection_summary(self, ok: bool, n_ok: int, n_total: int) -> None:
        mark = "✓" if ok else "✗"
        self.sub_title = f"SO-101   {mark} {n_ok}/{n_total} conectado"
