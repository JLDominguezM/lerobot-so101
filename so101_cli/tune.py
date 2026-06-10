"""Bucle interactivo para ajustar joints en vivo (modo --tune)."""

from __future__ import annotations

from .motion import interpolate_move, read_current
from .poses import JOINTS

TUNE_HELP = """\
Comandos:
  <joint> <±delta>       p.ej.  j5 +10   |  wrist_roll -5
  <joint> = <abs>        p.ej.  j2 =-30  |  shoulder_lift =0
  all v1 v2 v3 v4 v5 v6  pose completa absoluta
  show                   lee posición actual de los motores
  speed <N>              cambia max °/s (actual: {speed})
  dur <S>                cambia duración por movimiento (actual: {dur}s)
  step <N>               delta por defecto cuando solo das signo (actual: {step}°)
  save                   imprime un comando one-shot para reproducir esta pose
  hold                   sale manteniendo torque activo (pose rígida)
  q | quit               sale liberando torque
  h | help               muestra esta ayuda
Joints: j1..j6  o  shoulder_pan/shoulder_lift/elbow_flex/wrist_flex/wrist_roll/gripper
"""


def _resolve_joint(token: str) -> str | None:
    token = token.lower()
    if token.startswith("j") and token[1:].isdigit():
        idx = int(token[1:]) - 1
        if 0 <= idx < len(JOINTS):
            return JOINTS[idx]
    if token in JOINTS:
        return token
    return None


def tune_loop(robot, max_speed: float, duration: float, rate: float) -> bool:
    """Bucle interactivo. Devuelve True si se debe mantener torque al salir."""
    current = read_current(robot)
    default_step = 5.0
    hold_after = False

    def show():
        pretty = "  ".join(f"{j}={current[j]:+.1f}°" for j in JOINTS)
        print(f"  pose: {pretty}")

    print("\n=== modo TUNE ===")
    print(TUNE_HELP.format(speed=max_speed, dur=duration, step=default_step))
    show()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("q", "quit", "exit"):
            break
        if cmd == "hold":
            hold_after = True
            break
        if cmd in ("h", "help", "?"):
            print(TUNE_HELP.format(speed=max_speed, dur=duration, step=default_step))
            continue
        if cmd == "show":
            current = read_current(robot)
            show()
            continue
        if cmd == "save":
            vals = " ".join(f"{current[j]:.1f}" for j in JOINTS)
            print(f"  dume run follower move {vals} --duration {duration} --max-deg-per-s {max_speed}")
            continue
        if cmd == "speed" and len(parts) == 2:
            max_speed = float(parts[1]); print(f"  max_deg_per_s = {max_speed}"); continue
        if cmd == "dur" and len(parts) == 2:
            duration = float(parts[1]); print(f"  duration = {duration}s"); continue
        if cmd == "step" and len(parts) == 2:
            default_step = float(parts[1]); print(f"  default_step = {default_step}°"); continue
        if cmd == "all" and len(parts) == 7:
            target = {j: float(v) for j, v in zip(JOINTS, parts[1:])}
            interpolate_move(robot, target, duration, rate, max_speed)
            current = target
            show()
            continue

        joint = _resolve_joint(parts[0])
        if joint is None:
            print(f"  comando no reconocido: {line!r}. Escribe 'help'.")
            continue
        if len(parts) < 2:
            print("  falta valor. Ej: j5 +10   o   j5 =0")
            continue
        arg = "".join(parts[1:])
        try:
            if arg.startswith("="):
                target_val = float(arg[1:])
            elif arg in ("+", "-"):
                target_val = current[joint] + (default_step if arg == "+" else -default_step)
            else:
                target_val = current[joint] + float(arg)
        except ValueError:
            print(f"  valor inválido: {arg!r}")
            continue
        target = dict(current); target[joint] = target_val
        interpolate_move(robot, target, duration, rate, max_speed)
        current = target
        show()

    return hold_after
