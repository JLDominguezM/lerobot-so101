"""Suspende la TUI y corre `dume run <subcmd>` (o cualquier subproceso) con TTY completo.

Reusa verbatim los flujos scriptables de `dume run` (el árbol de so101_cli.cli):
tras `app.suspend()`, lerobot y sus controles de teclado / la ventana de rerun
reciben el terminal real, y al salir volvemos al cockpit con el returncode. Hoy se
usa para las quick actions de solo lectura (check / find-ports / scan-bus) y para
lanzar teleop; en Fase 3 será el camino central de record/eval/train/push/pull.

Invocamos vía `python -m so101_cli.dume run …` (con el intérprete actual) para que
funcione igual en dev (clone editable) que instalado, sin depender de wrappers ni
del PATH.
"""

from __future__ import annotations

import subprocess
import sys


def run_cli(app, subcmd: str, *args: str) -> int:
    """Con app.suspend(): corre `dume run <subcmd> <args...>` y devuelve el returncode."""
    cmd = [sys.executable, "-m", "so101_cli.dume", "run", subcmd, *args]
    pretty = " ".join(["dume", "run", subcmd, *args])
    with app.suspend():
        print(f"\n[dume] $ {pretty}\n", flush=True)
        try:
            rc = subprocess.call(cmd)
        except FileNotFoundError:
            print("[dume] No pude lanzar el subproceso. ¿Estás en el repo con .venv creado?")
            rc = 127
        try:
            input("\n[dume] Comando terminado. Enter para volver al cockpit...")
        except (EOFError, KeyboardInterrupt):
            pass
    return rc
