"""Suspende la TUI y corre `./cal <subcmd>` (o cualquier subproceso) con TTY completo.

Reusa verbatim los flujos ya probados de `cal`: tras `app.suspend()`, lerobot y
sus controles de teclado / la ventana de rerun reciben el terminal real, y al
salir volvemos al cockpit con el returncode. Hoy se usa para las quick actions de
solo lectura (check / find-ports / scan-bus); en Fase 3 será el camino central de
record/eval/train/push/pull.
"""

from __future__ import annotations

import subprocess

from ...config import REPO_DIR

CAL = REPO_DIR / "cal"


def run_cal(app, subcmd: str, *args: str) -> int:
    """Con app.suspend(): corre `./cal <subcmd> <args...>` y devuelve el returncode."""
    cmd = [str(CAL), subcmd, *args]
    with app.suspend():
        print(f"\n[dume] $ {' '.join(cmd)}\n", flush=True)
        try:
            rc = subprocess.call(cmd)
        except FileNotFoundError:
            print(f"[dume] No encontré {CAL}. ¿Estás en el repo con .venv creado?")
            rc = 127
        try:
            input("\n[dume] Comando terminado. Enter para volver al cockpit...")
        except (EOFError, KeyboardInterrupt):
            pass
    return rc
