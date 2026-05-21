#!/usr/bin/env python
"""Mueve el follower a posiciones articulares específicas (en grados).

Útil para probar el follower sin tener el leader conectado.

Uso:
    # Pose individual (grados, en orden 1..6: pan, lift, elbow, wflex, wroll, gripper)
    python scripts/move_follower.py 0 0 0 0 0 0

    # Pose nombrada predefinida
    python scripts/move_follower.py --pose home
    python scripts/move_follower.py --pose rest
    python scripts/move_follower.py --pose wave

    # Listar poses disponibles
    python scripts/move_follower.py --list

Requiere calibración previa (calibrations/papu.json instalado).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import yaml

from lerobot.robots.so_follower import SOFollowerRobotConfig
from lerobot.robots.so_follower.so_follower import SOFollower

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

# Poses en grados (use_degrees=True). Ajusta según tu calibración real.
POSES: dict[str, list[float]] = {
    "home":  [0, -104,  91,  41,   0,   1],  # pose segura de reposo/apagado
    "zeros": [0,   0,   0,   0,   0,   0],
    "rest":  [0,  90,  90,   0,   0,   0],   # plegado tipo "descanso"
    "wave":  [0, -30, -60,   0,   0,   0],   # brazo arriba
    "open":  [0,   0,   0,   0,   0,  40],   # gripper abierto
    "close": [0,   0,   0,   0,   0,   0],   # gripper cerrado
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("positions", nargs="*", type=float, help="6 valores en grados (orden 1..6)")
    p.add_argument("--pose", choices=sorted(POSES), help="Pose nombrada predefinida")
    p.add_argument("--list", action="store_true", help="Listar poses disponibles y salir")
    p.add_argument("--hold-time", type=float, default=3.0, help="Segundos a mantener la pose antes de soltar torque")
    p.add_argument("--duration", type=float, default=6.0,
                   help="Segundos a tardar en llegar a la pose (interpolación suave). 0 = instantáneo.")
    p.add_argument("--rate", type=float, default=50.0,
                   help="Hz de envío de waypoints durante la interpolación.")
    p.add_argument("--max-deg-per-s", type=float, default=50.0,
                   help="Velocidad angular máxima permitida (grados/s). Si la duración pedida implica más, se extiende.")
    p.add_argument("--hold", dest="hold_after", action="store_true",
                   help="Va a la pose y mantiene torque activo al salir (motores quedan rígidos hasta apagar fuente).")
    p.add_argument("--tune", action="store_true",
                   help="Va a ceros y entra a modo interactivo para ajustar cada joint en vivo.")
    return p.parse_args()


TUNE_HELP = """\
Comandos:
  <joint> <±delta>       p.ej.  j5 +10   |  wrist_roll -5
  <joint> = <abs>        p.ej.  j2 =-30  |  shoulder_lift =0
  all v1 v2 v3 v4 v5 v6  pose completa absoluta
  show                   imprime posición actual (leída de motores)
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
    obs = robot.get_observation()
    current = {j: obs[f"{j}.pos"] for j in JOINTS}
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
            obs = robot.get_observation()
            current = {j: obs[f"{j}.pos"] for j in JOINTS}
            show()
            continue
        if cmd == "save":
            vals = " ".join(f"{current[j]:.1f}" for j in JOINTS)
            print(f"  python scripts/move_follower.py {vals} --duration {duration} --max-deg-per-s {max_speed}")
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


def interpolate_move(robot: "SOFollower", target: dict[str, float],
                     duration: float, rate: float, max_deg_per_s: float) -> None:
    """Mueve suavemente desde la posición actual hasta target en `duration` segundos."""
    obs = robot.get_observation()
    start = {j: obs[f"{j}.pos"] for j in JOINTS}

    max_delta = max(abs(target[j] - start[j]) for j in JOINTS)
    min_duration_for_speed = max_delta / max_deg_per_s if max_deg_per_s > 0 else 0.0
    if duration < min_duration_for_speed:
        print(f"  (extendiendo duración: {duration:.2f}s -> {min_duration_for_speed:.2f}s "
              f"para respetar {max_deg_per_s}°/s)")
        duration = min_duration_for_speed

    if duration <= 0:
        robot.send_action({f"{j}.pos": target[j] for j in JOINTS})
        return

    n_steps = max(2, int(duration * rate))
    dt = duration / n_steps
    for k in range(1, n_steps + 1):
        alpha = k / n_steps
        # smoothstep: suaviza inicio y final (acel/decel)
        s = alpha * alpha * (3.0 - 2.0 * alpha)
        action = {f"{j}.pos": start[j] + s * (target[j] - start[j]) for j in JOINTS}
        robot.send_action(action)
        time.sleep(dt)


def main() -> None:
    args = parse_args()

    if args.list:
        for name, vals in POSES.items():
            pretty = ", ".join(f"{j}={v:g}" for j, v in zip(JOINTS, vals))
            print(f"  {name:<6}  {pretty}")
        return

    # Determinar pose inicial
    if args.tune:
        positions = [0.0] * 6  # tune siempre empieza en ceros
    elif args.pose:
        positions = POSES[args.pose]
    elif len(args.positions) == 6:
        positions = args.positions
    else:
        print("Error: pasa 6 valores en grados, o usa --pose <nombre>, --tune, o --hold.\n", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(2)

    repo_dir = Path(__file__).resolve().parent.parent
    cfg_path = repo_dir / "configs" / "follower.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)

    keep_torque = args.tune or args.hold_after
    robot_cfg = SOFollowerRobotConfig(
        port=cfg["port"], id=cfg["id"], use_degrees=True,
        disable_torque_on_disconnect=not keep_torque,
    )
    robot = SOFollower(robot_cfg)

    print(f"Conectando al follower en {cfg['port']} (id={cfg['id']})...")
    robot.connect(calibrate=False)

    target = {j: v for j, v in zip(JOINTS, positions)}
    pretty = ", ".join(f"{j}={v:g}°" for j, v in zip(JOINTS, positions))
    print(f"Interpolando hacia: {pretty}  (duration={args.duration}s, max={args.max_deg_per_s}°/s)")
    interpolate_move(robot, target, args.duration, args.rate, args.max_deg_per_s)

    if args.tune:
        keep_torque = tune_loop(robot, args.max_deg_per_s, args.duration, args.rate)
        # Reflejar la decisión final del usuario en el config antes de disconnect
        robot.config.disable_torque_on_disconnect = not keep_torque
    else:
        print(f"Manteniendo {args.hold_time}s...")
        time.sleep(args.hold_time)
        home_target = {j: v for j, v in zip(JOINTS, POSES["home"])}
        if target != home_target:
            pretty_home = ", ".join(f"{j}={v:g}°" for j, v in zip(JOINTS, POSES["home"]))
            print(f"Regresando a HOME: {pretty_home}")
            interpolate_move(robot, home_target, args.duration, args.rate, args.max_deg_per_s)

    if keep_torque:
        print("Saliendo con TORQUE ACTIVO — motores rígidos hasta apagar fuente o correr de nuevo.")
    else:
        print("Desconectando (libera torque).")
    robot.disconnect()


if __name__ == "__main__":
    main()
