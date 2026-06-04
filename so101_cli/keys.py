"""Lectura de teclas individuales sin presionar Enter (modo cbreak en Unix)."""

from __future__ import annotations

import select
import sys
import termios
import tty
from contextlib import contextmanager


@contextmanager
def cbreak():
    """Context manager que pone stdin en modo cbreak (lee char por char sin echo de Enter)."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key(timeout: float | None = None) -> str | None:
    """Lee un solo char de stdin. Si timeout vence, devuelve None.

    Debe llamarse dentro de `with cbreak():`.
    """
    if timeout is not None:
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return None
    ch = sys.stdin.read(1)
    return ch
