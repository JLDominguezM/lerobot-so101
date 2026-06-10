"""Punto de entrada de DUM-E: dos modos sobre los mismos módulos `so101_cli`.

Uso:
  dume [vista] [--ascii]          # modo TUI (cockpit rica en iconos)
  dume run <subcomando> [flags]   # modo CLI scriptable (move, teleop, record, eval, train, ...)

  python -m so101_cli.dume ...    # equivalente sin el console-script

`dume run` reemplaza 1:1 al antiguo `cal`: delega en el árbol de subcomandos de
`so101_cli.cli`. `dume`/`dume <vista>` abren la TUI. Interceptamos el token `run`
antes de parsear, porque las vistas (teleop/eval/train) comparten nombre con
subcomandos del CLI.

`main()` es top-level a propósito: sirve tanto para `python -m` como para el
entry point `[project.scripts] dume = "so101_cli.dume.__main__:main"`.
"""

from __future__ import annotations

import argparse
import sys

from .widgets.sidebar import VIEWS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dume",
        description="DUM-E: TUI rica en iconos para el SO-101 (modo TUI), "
                    "más el CLI scriptable `dume run <subcomando>`.",
        epilog="Modo CLI: `dume run <subcomando> [flags]` (p.ej. `dume run teleop --rate 30`, "
               "`dume run eval --color red`). Corre `dume run --help` para la lista completa.",
    )
    p.add_argument(
        "view", nargs="?", default="home", choices=[v.key for v in VIEWS],
        help="Vista inicial de la TUI (default: home).",
    )
    p.add_argument(
        "--ascii", action="store_true",
        help="Modo ASCII: sin Nerd Font ni imágenes ricas (equivale a DUME_ASCII=1).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Modo CLI: `dume run <subcomando> ...` delega en el árbol de so101_cli.cli
    # (el antiguo `cal`). Se intercepta antes de parsear la TUI porque varias
    # vistas comparten nombre con subcomandos (teleop/eval/train).
    if argv and argv[0] == "run":
        from ..cli import main as cli_main
        return cli_main(argv[1:])

    # Modo TUI.
    args = build_parser().parse_args(argv)
    from .app import DumeApp

    app = DumeApp(start_view=args.view, ascii_mode=args.ascii)
    app.run()
    return int(app.return_code or 0)


if __name__ == "__main__":
    sys.exit(main())
