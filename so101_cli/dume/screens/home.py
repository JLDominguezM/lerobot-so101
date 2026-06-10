"""Home cockpit: grid de cards con conexión, brazos, datasets, modelos, acciones.

Reglas de oro:
  - NO retener hardware: la conexión se sondea una vez al entrar y con `r` (refresh),
    cada sonda abre→pinga→cierra (engine/status). Sin polling de fondo.
  - Carga segura sin robot: todo degrada a ✗ / "ninguno" y nunca crashea.
  - Trabajo bloqueante (sondeo) corre en un worker con hilo, fuera del render.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from rich.text import Text
from textual import work
from textual.containers import Grid, Vertical

from ..engine.inventory import arm_summary, list_datasets, list_models
from ..engine.status import probe_connection
from ..theme import NEON, RED, S_KEY, S_OK
from ..widgets.card import Card
from ..widgets.status_pill import BAD, OK, pill_text


def _smoke_image_path() -> Path | None:
    """PNG para el smoke test inline: reusa photo*.png del repo o genera uno con Pillow."""
    from ...config import REPO_DIR

    for p in sorted(REPO_DIR.glob("photo*.png")):
        return p
    try:
        from PIL import Image as PILImage

        cache = Path(tempfile.gettempdir()) / "dume_smoke.png"
        if not cache.exists():
            img = PILImage.new("RGB", (240, 160))
            px = img.load()
            for y in range(160):
                for x in range(240):
                    px[x, y] = (x % 256, y % 256, (x + y) % 256)
            img.save(cache)
        return cache
    except Exception:
        return None


class HomeView(Vertical):
    """El cockpit. Se monta dentro de #content; los atajos viven en la App."""

    def __init__(self, caps, icons) -> None:
        super().__init__()
        self.caps = caps
        self.icons = icons

    def compose(self):
        with Grid(id="cockpit"):
            yield Card("Connection", id="card-conn")
            yield Card("Arms & calibration", id="card-arms")
            yield Card("Datasets", id="card-datasets")
            yield Card("Models", id="card-models")
            yield Card("Quick actions", id="card-actions")
            yield Card("Image smoke test", id="card-image")

    def on_mount(self) -> None:
        self._fill_arms()
        self._fill_inventory()
        self._fill_actions()
        self._fill_image()
        self.refresh_view()

    # ---- API usada por la App (atajo `r`) -------------------------------

    def refresh_view(self) -> None:
        self.query_one("#card-conn", Card).set_body(Text("Sondeando hardware…", style="dim"))
        self._fill_inventory()
        self._probe()

    # ---- conexión (worker, sin bloquear el render) ----------------------

    @work(thread=True, exclusive=True)
    def _probe(self) -> None:
        status = probe_connection()
        self.app.call_from_thread(self._render_connection, status)

    def _render_connection(self, status) -> None:
        t = Text()
        for r in status.items:
            t.append_text(pill_text(OK if r.ok else BAD, "", self.caps.ascii_only))
            t.append(f"  {r.label}\n", style="bold")
            t.append(f"      {r.detail}\n", style="dim")
        self.query_one("#card-conn", Card).set_body(t)
        if hasattr(self.app, "set_connection_summary"):
            self.app.set_connection_summary(status.all_ok, status.n_ok, status.n_total)

    # ---- cards estáticas (lectura de disco/config) ----------------------

    def _fill_arms(self) -> None:
        t = Text()
        for which in ("follower", "leader"):
            a = arm_summary(which)
            t.append(f"{which}\n", style="bold")
            t.append(f"   port  {a.port}\n", style="dim")
            t.append(f"   id    {a.id}   ", style="dim")
            if a.calib_present:
                age = f"{a.calib_age_days:.0f}d" if a.calib_age_days is not None else "?"
                t.append(f"calib ✓ ({age})\n", style=S_OK)
            else:
                t.append("calib ✗ (falta)\n", style=RED)
        self.query_one("#card-arms", Card).set_body(t)

    def _fill_inventory(self) -> None:
        ds = list_datasets()
        t = Text()
        if not ds:
            t.append("ninguno en cache\n", style="dim")
        else:
            for d in ds[:8]:
                t.append("• ", style=NEON)
                t.append(d.name, style="bold")
                t.append(f"   {d.episodes} ep\n", style="dim")
            if len(ds) > 8:
                t.append(f"… +{len(ds) - 8} más\n", style="dim")
        self.query_one("#card-datasets", Card).set_body(t)

        models = list_models()
        tm = Text()
        if not models:
            tm.append("ninguno\n", style="dim")
        else:
            for m in models[:8]:
                tm.append("• ", style=NEON)
                tm.append(m.name, style="bold")
                tm.append(f"   [{m.source}]\n", style="dim")
            if len(models) > 8:
                tm.append(f"… +{len(models) - 8} más\n", style="dim")
        self.query_one("#card-models", Card).set_body(tm)

    def _fill_actions(self) -> None:
        t = Text()
        t.append("Suspende la TUI y corre dume run:\n", style="dim")
        for key, desc in (("c", "check  (brazos + cámaras)"),
                          ("f", "find-ports"),
                          ("s", "scan-bus follower"),
                          ("S", "scan-bus leader")):
            t.append(f"  [{key}] ", style=S_KEY)
            t.append(f"{desc}\n")
        t.append("\nteleop → vista propia (2)\n", style="dim italic")
        t.append("record / eval / train → próxima fase\n", style="dim italic")
        self.query_one("#card-actions", Card).set_body(t)

    def _fill_image(self) -> None:
        card = self.query_one("#card-image", Card)
        if os.environ.get("DUME_NO_IMAGE"):
            card.set_body(Text("(smoke test deshabilitado: DUME_NO_IMAGE)", style="dim"))
            return
        path = _smoke_image_path()
        if path is None:
            card.set_body(Text("(sin PNG de prueba y Pillow no disponible)", style="dim"))
            return
        try:
            from textual_image.widget import Image as AutoImage
        except Exception as e:  # textual-image ausente
            card.set_body(Text(f"textual-image no disponible:\n{e}", style=RED))
            return
        try:
            card.body.display = False
            card.mount(AutoImage(str(path)))
        except Exception as e:
            card.set_body(Text(f"no pude renderizar la imagen:\n{e}", style=RED))
