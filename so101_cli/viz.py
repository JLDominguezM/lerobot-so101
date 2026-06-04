"""Visualización con Rerun.

Se inicializa una sola vez por proceso (`init(app)`). Si rerun no está
instalado, las funciones de log se vuelven no-ops para no romper nada.

Estructura del recording:
  follower/<joint>     -> scalar (grados o % en gripper)
  leader/<joint>       -> scalar
  target/<joint>       -> scalar (lo que mandamos al follower)
  cameras/<name>       -> Image  (cuando haya cámaras)
  events               -> TextLog (waypoints capturados, start/stop, etc.)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .poses import JOINTS

try:
    import rerun as rr

    _HAS_RR = True
except ImportError:
    _HAS_RR = False

_initialized = False


def _find_viewer() -> str | None:
    """Localiza el binario `rerun`. El wrapper `cal` corre `.venv/bin/python` sin
    activar el venv, así que `.venv/bin` no está en PATH y `rr.spawn` no encuentra
    el viewer. Buscamos primero junto al intérprete y luego en PATH.
    """
    sibling = Path(sys.executable).parent / "rerun"
    if sibling.exists():
        return str(sibling)
    return shutil.which("rerun")


def init(
    app_name: str, spawn: bool = True, save_path: Path | str | None = None
) -> None:
    """Inicializa rerun. Spawn abre el viewer en vivo; save_path persiste un .rrd.

    Idempotente. Si ambos están activos, hace fan-out (live + file).
    """
    global _initialized
    if _initialized:
        return
    if not _HAS_RR:
        print(
            "(rerun no instalado; corre `uv sync` o `pip install rerun-sdk` para visualización)"
        )
        _initialized = True
        return
    rr.init(f"so101.{app_name}")
    # rr.serve_web_viewer()

    sinks: list = []
    if spawn:
        viewer = _find_viewer()
        try:
            rr.spawn(
                connect=False,
                executable_path=viewer,
                memory_limit="2GB",
                server_memory_limit="0B",
            )
            sinks.append(rr.GrpcSink())
        except Exception as e:
            print(
                f"(no se pudo abrir el viewer de rerun: {e}; sigo sin visualización en vivo)"
            )
    if save_path is not None:
        sinks.append(rr.FileSink(str(save_path)))
    if sinks:
        rr.set_sinks(*sinks)
    _initialized = True


def _normalize(positions: list[float] | dict[str, float]) -> list[float]:
    if isinstance(positions, dict):
        # Acepta tanto {joint: val} como {joint.pos: val}
        if all(k in positions for k in JOINTS):
            return [positions[j] for j in JOINTS]
        return [positions[f"{j}.pos"] for j in JOINTS]
    return list(positions)


def log_positions(
    positions: list[float] | dict[str, float], source: str = "follower"
) -> None:
    """Registra una snapshot de las 6 posiciones bajo `source/<joint>`."""
    if not _HAS_RR or not _initialized:
        return
    vals = _normalize(positions)
    for joint, val in zip(JOINTS, vals):
        rr.log(f"{source}/{joint}", rr.Scalars(val))


def log_event(message: str, level: str = "info") -> None:
    """Registra un texto en el timeline (eventos: waypoints, start/stop, etc.)."""
    if not _HAS_RR or not _initialized:
        return
    rr.log("events", rr.TextLog(message, level=level.upper()))


def log_image(name: str, image: Any) -> None:
    """Registra un frame de cámara bajo `cameras/<name>`. Para uso futuro."""
    if not _HAS_RR or not _initialized:
        return
    if name == "external":
        cv2.imshow("debug", image)
        cv2.waitKey(1)
    rr.log(f"cameras/{name}", rr.Image(image))


def set_time_seconds(seconds: float, timeline: str = "wall_time") -> None:
    """Avanza el timeline a un instante específico (para replay sincronizado)."""
    if not _HAS_RR or not _initialized:
        return
    rr.set_time(timeline, duration=seconds)
