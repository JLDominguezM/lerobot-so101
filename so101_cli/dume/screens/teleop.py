"""Vista Teleop: formulario que re-compone `cal teleop …` y lo lanza (suspend-and-run).

Es el primer formulario "real" de la TUI (Fase 2) y fija el patrón que reusarán
record/eval/train: campos editables → CommandPreview en vivo → suspender la TUI y
correr `./cal teleop <flags>` con el TTY completo (lerobot toma el teclado y la
ventana de rerun). NO reimplementa teleop: delega 1:1 en el subcomando de `cal`.

Pre-vuelo bajo demanda: el botón "Comprobar conexión" corre `probe_connection()` en
un worker con hilo (abre→pinga→cierra, sin retener el bus ni las cámaras), igual que
el cockpit. No se sondea al entrar para no meter latencia ni tocar el bus sin pedirlo.
"""

from __future__ import annotations

from rich.text import Text
from textual import work
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Static, Switch

from ..engine.runner import run_cal
from ..engine.status import probe_connection
from ..theme import AMBER, DIM, RED, S_OK
from ..widgets.command_preview import CommandPreview
from ..widgets.status_pill import BAD, OK, pill_text

DEFAULT_RATE = "30"


class TeleopView(Vertical):
    """Formulario de teleop + pre-vuelo + preview del comando + lanzar."""

    def __init__(self, caps, icons) -> None:
        super().__init__()
        self.caps = caps
        self.icons = icons

    # ---- layout ---------------------------------------------------------

    def compose(self):
        glyph = self.icons.get("teleop", "")
        with VerticalScroll(id="teleop-scroll"):
            yield Static(
                Text(f"{glyph}  Teleop — el leader controla al follower en vivo",
                     style="bold"),
                id="teleop-head",
            )

            with Vertical(id="card-teleop-cfg", classes="card"):
                with Horizontal(classes="form-row"):
                    yield Label("rate (Hz)", classes="form-label")
                    yield Input(value=DEFAULT_RATE, type="number",
                                id="f-rate", classes="form-input")
                with Horizontal(classes="form-row"):
                    yield Label("grabar a disco", classes="form-label")
                    yield Switch(value=False, id="f-record")
                with Horizontal(classes="form-row"):
                    yield Label("out (base)", classes="form-label")
                    yield Input(placeholder="auto: paths/teleop_<ts>",
                                id="f-out", classes="form-input", disabled=True)
                with Horizontal(classes="form-row"):
                    yield Label("cámara front", classes="form-label")
                    yield Switch(value=True, id="f-front")
                with Horizontal(classes="form-row"):
                    yield Label("cámara lateral", classes="form-label")
                    yield Switch(value=True, id="f-lateral")
                with Horizontal(classes="form-row"):
                    yield Label("front-index", classes="form-label")
                    yield Input(placeholder="auto", type="integer",
                                id="f-front-index", classes="form-input")

            with Vertical(id="card-teleop-pre", classes="card"):
                yield Static(Text("Sin sondear. Comprobá la conexión antes de lanzar.",
                                  style="dim"), id="teleop-preflight")

            yield Static(Text("Comando", style="dim"), classes="section-label")
            yield CommandPreview(id="teleop-cmd")

            with Horizontal(id="teleop-buttons"):
                yield Button("Comprobar conexión", id="btn-check", variant="primary")
                yield Button("Lanzar teleop ▶", id="btn-launch", variant="success")

    def on_mount(self) -> None:
        self.query_one("#card-teleop-cfg").border_title = "Configuración"
        self.query_one("#card-teleop-pre").border_title = "Pre-vuelo (conexión)"
        self._update_preview()

    # ---- contrato con la App -------------------------------------------

    def refresh_view(self) -> None:
        """Atajo `r`: re-sondea el pre-vuelo (mismo gesto que el cockpit)."""
        self._set_preflight(Text("Sondeando hardware…", style="dim"))
        self._probe()

    # ---- eventos del formulario ----------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        self._update_preview()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "f-record":
            # out solo tiene sentido cuando grabamos.
            self.query_one("#f-out", Input).disabled = not event.value
        self._update_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-check":
            self.refresh_view()
        elif event.button.id == "btn-launch":
            self._launch()

    # ---- composición del comando ---------------------------------------

    def _compose_flags(self) -> tuple[list[str], str | None]:
        """Lee el formulario → (flags para `cal teleop`, error). error=None si ok."""
        flags: list[str] = []

        rate = self.query_one("#f-rate", Input).value.strip()
        if rate:
            try:
                if float(rate) <= 0:
                    return [], "rate debe ser > 0"
            except ValueError:
                return [], f"rate inválido: {rate!r}"
            flags += ["--rate", rate]

        if self.query_one("#f-record", Switch).value:
            flags.append("--record")
            out = self.query_one("#f-out", Input).value.strip()
            if out:
                flags += ["--out", out]

        if not self.query_one("#f-front", Switch).value:
            flags.append("--no-front")
        if not self.query_one("#f-lateral", Switch).value:
            flags.append("--no-lateral")

        fidx = self.query_one("#f-front-index", Input).value.strip()
        if fidx:
            try:
                int(fidx)
            except ValueError:
                return [], f"front-index inválido: {fidx!r}"
            flags += ["--front-index", fidx]

        return flags, None

    def _update_preview(self) -> None:
        flags, error = self._compose_flags()
        preview = self.query_one("#teleop-cmd", CommandPreview)
        launch = self.query_one("#btn-launch", Button)
        if error is not None:
            preview.update(Text(f"⚠ {error}", style=RED))
            launch.disabled = True
            return
        preview.set_command(["cal", "teleop", *flags])
        launch.disabled = False

    # ---- lanzar (suspende la TUI y corre cal) ---------------------------

    def _launch(self) -> None:
        flags, error = self._compose_flags()
        if error is not None:
            self._update_preview()
            return
        run_cal(self.app, "teleop", *flags)
        # Al volver del subproceso, re-sondear para reflejar el estado real.
        self.refresh_view()

    # ---- pre-vuelo (worker, sin bloquear el render) ---------------------

    @work(thread=True, exclusive=True)
    def _probe(self) -> None:
        status = probe_connection(
            check_front=self.query_one("#f-front", Switch).value,
            check_lateral=self.query_one("#f-lateral", Switch).value,
        )
        self.app.call_from_thread(self._render_preflight, status)

    def _render_preflight(self, status) -> None:
        t = Text()
        for r in status.items:
            t.append_text(pill_text(OK if r.ok else BAD, "", self.caps.ascii_only))
            t.append(f"  {r.label}\n", style="bold")
            t.append(f"      {r.detail}\n", style=DIM)

        # Veredicto: teleop necesita SÍ o SÍ leader + follower.
        if status.follower.ok and status.leader.ok:
            t.append("\nListo para teleop ▶\n", style=S_OK)
        else:
            faltan = [n for n, ok in (("follower", status.follower.ok),
                                      ("leader", status.leader.ok)) if not ok]
            t.append(f"\n⚠ falta {' y '.join(faltan)} — teleop no podrá conectar\n",
                     style=AMBER)
        self._set_preflight(t)
        if hasattr(self.app, "set_connection_summary"):
            self.app.set_connection_summary(status.all_ok, status.n_ok, status.n_total)

    # ---- helpers --------------------------------------------------------

    def _set_preflight(self, renderable) -> None:
        self.query_one("#teleop-preflight", Static).update(renderable)
