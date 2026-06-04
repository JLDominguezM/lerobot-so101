"""Subcomandos del leader: record-waypoint, record-trajectory."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from lerobot.teleoperators.so_leader import SOLeaderTeleopConfig
from lerobot.teleoperators.so_leader.so_leader import SOLeader

from . import io as traj_io
from . import viz
from .config import load_arm_config
from .keys import cbreak, read_key
from .poses import JOINTS, action_to_positions


def add_record_waypoint_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record-waypoint",
        help="Graba poses estáticas: mueve el leader a mano, presiona 's' para capturar.",
    )
    p.add_argument("file", type=Path, help="Archivo .json de salida", default="./paths/path1.json")
    p.add_argument("--append", action="store_true",
                   help="Si el archivo existe, agrega waypoints al final en vez de sobreescribir")
    p.set_defaults(func=cmd_record_waypoint)


def add_record_trajectory_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record-trajectory",
        help="Graba un movimiento continuo: presiona 'r' para start/stop.",
    )
    p.add_argument("file", type=Path, help="Archivo .json de salida")
    p.add_argument("--rate", type=float, default=30.0, help="Hz de muestreo (default 30)")
    p.set_defaults(func=cmd_record_trajectory)


def _connect_leader() -> SOLeader:
    cfg = load_arm_config("leader")
    teleop_cfg = SOLeaderTeleopConfig(port=cfg["port"], id=cfg["id"], use_degrees=True)
    leader = SOLeader(teleop_cfg)
    print(f"Conectando al leader en {cfg['port']} (id={cfg['id']})...")
    leader.connect(calibrate=False)
    # connect() ya llama a configure() que deshabilita torque. Lo refuerzo por las dudas.
    leader.disable_torque()
    print("Leader conectado. Torque DESHABILITADO — puedes moverlo libremente con la mano.")
    return leader


def _read_positions(leader: SOLeader) -> list[float]:
    pos = action_to_positions(leader.get_action())
    viz.log_positions(pos, source="leader")
    return pos


def _pretty(positions: list[float]) -> str:
    return "  ".join(f"{j}={v:+6.1f}°" for j, v in zip(JOINTS, positions))


# ----- record-waypoint -----

def cmd_record_waypoint(args: argparse.Namespace) -> int:
    existing: list[dict] = []
    if args.append and args.file.exists():
        data = traj_io.load(args.file)
        if data["type"] != "waypoints":
            print(f"Error: {args.file} no es un archivo de waypoints (es {data['type']!r})")
            return 2
        existing = data["points"]
        print(f"Modo append: cargados {len(existing)} waypoints previos.")

    viz.init("leader.record-waypoint")
    leader = _connect_leader()
    points: list[dict] = list(existing)

    print()
    print("=== RECORD WAYPOINTS ===")
    print("  s  -> guardar pose actual como waypoint")
    print("  p  -> mostrar pose actual (sin guardar)")
    print("  u  -> deshacer último waypoint")
    print("  q  -> terminar y guardar archivo")
    print()

    try:
        with cbreak():
            last_show = 0.0
            while True:
                # Refresca la línea de status cada 100ms.
                now = time.perf_counter()
                if now - last_show > 0.1:
                    pos = _read_positions(leader)
                    print(f"\r  live: {_pretty(pos)}   [{len(points)} wp]   ", end="", flush=True)
                    last_show = now

                ch = read_key(timeout=0.05)
                if ch is None:
                    continue
                if ch in ("q", "\x03"):  # q o Ctrl-C
                    print()
                    break
                if ch == "s":
                    pos = _read_positions(leader)
                    name = f"wp{len(points) + 1}"
                    points.append({"name": name, "positions": [round(v, 2) for v in pos]})
                    print(f"\n  [+] capturado {name}: {_pretty(pos)}")
                    viz.log_event(f"captured {name}")
                elif ch == "p":
                    pos = _read_positions(leader)
                    print(f"\n  pose: {_pretty(pos)}")
                elif ch == "u":
                    if points:
                        removed = points.pop()
                        print(f"\n  [-] deshecho {removed.get('name')}")
                    else:
                        print("\n  (nada que deshacer)")
    finally:
        leader.disconnect()

    if not points:
        print("No se grabó ningún waypoint, no escribo el archivo.")
        return 0

    traj_io.save_waypoints(args.file, points)
    print(f"\nGuardados {len(points)} waypoints en {args.file}")
    return 0


# ----- record-trajectory -----

def cmd_record_trajectory(args: argparse.Namespace) -> int:
    viz.init("leader.record-trajectory")
    leader = _connect_leader()
    period = 1.0 / args.rate
    samples: list[dict] = []
    recording = False

    print()
    print("=== RECORD TRAJECTORY ===")
    print(f"  rate: {args.rate} Hz  (período {period*1000:.0f} ms)")
    print("  r  -> START / STOP grabación")
    print("  q  -> terminar (descarta si no hay datos)")
    print()

    try:
        with cbreak():
            t0 = None
            next_sample = 0.0
            last_show = 0.0
            while True:
                now = time.perf_counter()

                # Status line.
                if now - last_show > 0.1:
                    pos = _read_positions(leader)
                    state = "REC" if recording else "idle"
                    extra = f" t={now - t0:5.2f}s n={len(samples)}" if recording else ""
                    print(f"\r  [{state}] {_pretty(pos)}{extra}   ", end="", flush=True)
                    last_show = now

                # Sampling.
                if recording and now >= next_sample:
                    pos = _read_positions(leader)
                    samples.append({"t": round(now - t0, 4),
                                    "positions": [round(v, 2) for v in pos]})
                    next_sample = (t0 + len(samples) * period)

                ch = read_key(timeout=0.005)
                if ch is None:
                    continue
                if ch in ("q", "\x03"):
                    print()
                    break
                if ch == "r":
                    if not recording:
                        recording = True
                        t0 = time.perf_counter()
                        next_sample = t0
                        samples = []
                        print("\n  >>> grabando")
                        viz.log_event("REC start")
                    else:
                        recording = False
                        viz.log_event("REC stop")
                        print(f"\n  <<< stop  ({len(samples)} muestras, "
                              f"{samples[-1]['t']:.2f}s)" if samples else "\n  <<< stop (vacío)")
                        break
    finally:
        leader.disconnect()

    if not samples:
        print("No hay muestras, no escribo el archivo.")
        return 0

    traj_io.save_trajectory(args.file, samples, rate_hz=args.rate)
    print(f"\nGuardada trayectoria en {args.file}  ({len(samples)} muestras, "
          f"{samples[-1]['t']:.2f}s @ {args.rate} Hz)")
    return 0
