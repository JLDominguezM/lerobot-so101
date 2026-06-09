"""Punto de entrada de la TUI DUM-E.

Uso:
  python -m so101_cli.dume [vista] [--ascii]
  dume [vista] [--ascii]          (vía wrapper ./dume o el console-script)

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
        description="DUM-E: TUI rica en iconos para el SO-101 (front-end de cal).",
    )
    p.add_argument(
        "view", nargs="?", default="home", choices=[v.key for v in VIEWS],
        help="Vista inicial (default: home).",
    )
    p.add_argument(
        "--ascii", action="store_true",
        help="Modo ASCII: sin Nerd Font ni imágenes ricas (equivale a DUME_ASCII=1).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .app import DumeApp

    app = DumeApp(start_view=args.view, ascii_mode=args.ascii)
    app.run()
    return int(app.return_code or 0)


if __name__ == "__main__":
    sys.exit(main())
