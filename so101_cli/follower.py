"""Subcomandos del follower: move, replay."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from lerobot.robots.so_follower import SOFollowerRobotConfig
from lerobot.robots.so_follower.so_follower import SOFollower

from . import io as traj_io
from . import viz
from .config import load_arm_config
from .motion import interpolate_move, read_current
from .poses import HOME, JOINTS, POSES, positions_to_action


def add_move_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "move",
        help="Mueve el follower a una pose (o entra a modo tune).",
        description="Mueve el follower a una pose específica con interpolación suave.",
    )
    p.add_argument("positions", nargs="*", type=float, help="6 valores en grados (orden 1..6)")
    p.add_argument("--pose", choices=sorted(POSES), help="Pose nombrada predefinida")
    p.add_argument("--list", action="store_true", help="Listar poses disponibles y salir")
    p.add_argument("--hold-time", type=float, default=3.0, help="Segundos a mantener la pose antes de regresar a home")
    p.add_argument("--duration", type=float, default=6.0, help="Segundos para llegar a la pose (0 = instantáneo)")
    p.add_argument("--rate", type=float, default=50.0, help="Hz de envío de waypoints")
    p.add_argument("--max-deg-per-s", type=float, default=30.0, help="Velocidad angular máxima (°/s)")
    p.add_argument("--hold", dest="hold_after", action="store_true",
                   help="Mantiene torque activo al salir (motores quedan rígidos en la pose)")
    p.add_argument("--tune", action="store_true",
                   help="Va a ceros y entra a modo interactivo para ajustar joints en vivo")
    p.set_defaults(func=cmd_move)


def add_replay_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "replay",
        help="Reproduce un archivo de waypoints o trayectoria grabados con el leader.",
    )
    p.add_argument("file", type=Path, help="Archivo .json grabado con `leader record-*`")
    p.add_argument("--duration", type=float, default=4.0,
                   help="Segundos entre waypoints (solo aplica a archivos de waypoints)")
    p.add_argument("--max-deg-per-s", type=float, default=30.0, help="Velocidad angular máxima")
    p.add_argument("--rate", type=float, default=50.0, help="Hz interno de interpolación")
    p.add_argument("--hold-each", type=float, default=1.0,
                   help="Segundos a mantener cada waypoint antes del siguiente")
    p.add_argument("--no-return-home", action="store_true",
                   help="No regresar a home al finalizar")
    p.set_defaults(func=cmd_replay)


def _connect_follower(keep_torque: bool) -> SOFollower:
    cfg = load_arm_config("follower")
    robot_cfg = SOFollowerRobotConfig(
        port=cfg["port"], id=cfg["id"], use_degrees=True,
        disable_torque_on_disconnect=not keep_torque,
    )
    robot = SOFollower(robot_cfg)
    print(f"Conectando al follower en {cfg['port']} (id={cfg['id']})...")
    robot.connect(calibrate=False)
    return robot


def _return_home(robot: SOFollower, duration: float, rate: float, max_speed: float) -> None:
    home_target = {j: v for j, v in zip(JOINTS, HOME)}
    pretty = ", ".join(f"{j}={v:g}°" for j, v in zip(JOINTS, HOME))
    print(f"Regresando a HOME: {pretty}")
    interpolate_move(robot, home_target, duration, rate, max_speed)


# ----- move -----

def cmd_move(args: argparse.Namespace) -> int:
    from .tune import tune_loop  # import perezoso para no requerir tty al replay

    if args.list:
        for name, vals in POSES.items():
            pretty = ", ".join(f"{j}={v:g}" for j, v in zip(JOINTS, vals))
            print(f"  {name:<6}  {pretty}")
        return 0

    if args.tune:
        positions = [0.0] * 6
    elif args.pose:
        positions = POSES[args.pose]
    elif len(args.positions) == 6:
        positions = args.positions
    else:
        print("Error: pasa 6 valores, o --pose <nombre>, o --tune.", file=sys.stderr)
        return 2

    viz.init("follower.move")
    viz.log_event(f"move start: target={positions}")
    keep_torque = args.tune or args.hold_after
    robot = _connect_follower(keep_torque=keep_torque)

    target = {j: v for j, v in zip(JOINTS, positions)}
    pretty = ", ".join(f"{j}={v:g}°" for j, v in zip(JOINTS, positions))
    print(f"Interpolando hacia: {pretty}  (duration={args.duration}s, max={args.max_deg_per_s}°/s)")
    interpolate_move(robot, target, args.duration, args.rate, args.max_deg_per_s)

    if args.tune:
        keep_torque = tune_loop(robot, args.max_deg_per_s, args.duration, args.rate)
        robot.config.disable_torque_on_disconnect = not keep_torque
    else:
        print(f"Manteniendo {args.hold_time}s...")
        time.sleep(args.hold_time)
        home_target = {j: v for j, v in zip(JOINTS, HOME)}
        if not args.hold_after and target != home_target:
            _return_home(robot, args.duration, args.rate, args.max_deg_per_s)

    if keep_torque:
        print("Saliendo con TORQUE ACTIVO — la pose se mantiene hasta apagar la fuente.")
    else:
        print("Desconectando (libera torque).")
    robot.disconnect()
    return 0


# ----- replay -----

def cmd_replay(args: argparse.Namespace) -> int:
    data = traj_io.load(args.file)
    kind = data["type"]
    viz.init(f"follower.replay.{kind}")
    viz.log_event(f"replay {kind} from {args.file.name}")
    robot = _connect_follower(keep_torque=False)

    try:
        if kind == "waypoints":
            _replay_waypoints(robot, data, args)
        elif kind == "trajectory":
            _replay_trajectory(robot, data, args)
        else:
            print(f"Tipo desconocido: {kind}", file=sys.stderr)
            return 2

        if not args.no_return_home:
            _return_home(robot, args.duration, args.rate, args.max_deg_per_s)
    finally:
        print("Desconectando (libera torque).")
        robot.disconnect()
    return 0


def _replay_waypoints(robot: SOFollower, data: dict, args) -> None:
    points = data["points"]
    print(f"Replay de {len(points)} waypoint(s) desde {args.file.name}")
    for i, wp in enumerate(points, 1):
        name = wp.get("name") or f"wp{i}"
        target = {j: v for j, v in zip(JOINTS, wp["positions"])}
        print(f"  [{i}/{len(points)}] -> {name}")
        interpolate_move(robot, target, args.duration, args.rate, args.max_deg_per_s)
        if args.hold_each > 0:
            time.sleep(args.hold_each)


def _replay_trajectory(robot: SOFollower, data: dict, args) -> None:
    samples = data["samples"]
    rate_hz = data.get("rate_hz", 30)
    duration_s = data.get("duration_s", samples[-1]["t"] if samples else 0)
    print(f"Replay de trayectoria: {len(samples)} muestras, {duration_s:.2f}s @ {rate_hz} Hz")

    # 1) Llegar suavemente a la primera muestra desde la pose actual.
    first = {j: v for j, v in zip(JOINTS, samples[0]["positions"])}
    print("  -> moviendo al primer frame de la trayectoria...")
    interpolate_move(robot, first, args.duration, args.rate, args.max_deg_per_s)

    # 2) Reproducir respetando los timestamps grabados.
    print("  -> reproduciendo...")
    t0 = time.perf_counter()
    base_t = samples[0]["t"]
    for s in samples:
        target_t = s["t"] - base_t
        now = time.perf_counter() - t0
        sleep_for = target_t - now
        if sleep_for > 0:
            time.sleep(sleep_for)
        action = positions_to_action(s["positions"])
        robot.send_action(action)
        viz.log_positions(action, source="target")
