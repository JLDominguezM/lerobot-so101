"""Subcomando top-level: ./so101 teleop

Conecta leader (torque off) y follower (torque on), y a `--rate` Hz copia las
posiciones del leader al follower. Loguea ambos a rerun.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from lerobot.robots.so_follower import SOFollowerRobotConfig
from lerobot.robots.so_follower.so_follower import SOFollower
from lerobot.teleoperators.so_leader import SOLeaderTeleopConfig
from lerobot.teleoperators.so_leader.so_leader import SOLeader

import cv2

from . import io as traj_io
from . import viz
from .cameras import FrontCamera, LateralCamera
from .config import load_arm_config
from .keys import cbreak, read_key
from .motion import interpolate_move
from .poses import JOINTS, action_to_positions, positions_to_action

# Al reanudar tras una pausa, el follower vuelve suavemente a la pose actual del
# leader (que pudo moverse mientras estaba pausado) en vez de saltar de golpe.
RESUME_DURATION = 0.6        # segundos del ramp de reanudación
RESUME_MAX_DEG_PER_S = 60.0  # velocidad pico del ramp (interpolate_move la respeta)


def add_teleop_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "teleop",
        help="Teleop en vivo: el leader controla al follower.",
        description=(
            "Conecta leader y follower y copia continuamente las posiciones del leader "
            "al follower. Por defecto SOLO visualiza en rerun (no graba nada a disco). "
            "Pasa --record para guardar la sesión completa (trayectoria JSON + rerun .rrd). "
            "Mientras corre: 'espacio' pausa/reanuda (el follower mantiene la pose con "
            "torque), 'q' para salir."
        ),
    )
    p.add_argument("--rate", type=float, default=30.0, help="Hz del loop de control (default 30)")
    p.add_argument("--record", action="store_true",
                   help="Graba la sesión a disco (trayectoria .json + rerun .rrd). "
                        "Sin esta flag, rerun solo muestra en vivo y no escribe nada.")
    p.add_argument("--out", type=Path, default=None,
                   help="Ruta base para los archivos cuando --record está activo "
                        "(sin extensión). Default: paths/teleop_<timestamp>")
    p.add_argument("--no-lateral", action="store_true",
                   help="No abrir la cámara lateral (OAK-D)")
    p.add_argument("--no-front", action="store_true",
                   help="No abrir la cámara frontal (RealSense)")
    p.add_argument("--front-index", type=int, default=None,
                   help="Forzar índice AVFoundation para la RealSense (default: auto-detect)")
    p.set_defaults(func=cmd_teleop)


def _connect_leader() -> SOLeader:
    cfg = load_arm_config("leader")
    teleop_cfg = SOLeaderTeleopConfig(port=cfg["port"], id=cfg["id"], use_degrees=True)
    leader = SOLeader(teleop_cfg)
    print(f"Leader  : conectando en {cfg['port']} (id={cfg['id']})...")
    leader.connect(calibrate=False)
    leader.bus.disable_torque()
    return leader


def _connect_follower() -> SOFollower:
    cfg = load_arm_config("follower")
    robot_cfg = SOFollowerRobotConfig(
        port=cfg["port"], id=cfg["id"], use_degrees=True,
        disable_torque_on_disconnect=True,
    )
    robot = SOFollower(robot_cfg)
    print(f"Follower: conectando en {cfg['port']} (id={cfg['id']})...")
    robot.connect(calibrate=False)
    return robot


def _resolve_out_base(out: Path | None) -> Path:
    if out is not None:
        return out
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path("paths") / f"teleop_{stamp}"
    base.parent.mkdir(parents=True, exist_ok=True)
    return base


def cmd_teleop(args: argparse.Namespace) -> int:
    if args.record:
        out_base = _resolve_out_base(args.out)
        traj_path = out_base.with_suffix(".json")
        rrd_path = out_base.with_suffix(".rrd")
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        viz.init("teleop", save_path=rrd_path)
    else:
        traj_path = None
        rrd_path = None
        viz.init("teleop")

    leader = _connect_leader()
    try:
        follower = _connect_follower()
    except Exception:
        leader.disconnect()
        raise

    period = 1.0 / args.rate
    samples: list[dict] = []
    recording = args.record
    t_rec_start: float | None = time.perf_counter() if recording else None

    print()
    print("=== TELEOP en vivo ===")
    print(f"  rate: {args.rate} Hz")
    if recording:
        print(f"  grabando trayectoria a: {traj_path}")
        print(f"  grabando rerun .rrd a:  {rrd_path}")
    else:
        print("  modo: solo visualización (rerun en vivo, nada se escribe a disco)")
    print("  espacio -> pausar/reanudar (el follower mantiene la pose)")
    print("  q       -> salir")
    print()
    viz.log_event(f"teleop start @ {args.rate} Hz (record={'on' if recording else 'off'})")

    last_show = 0.0
    next_tick = time.perf_counter()
    paused = False
    last_action: dict | None = None
    leader_pos = [0.0] * len(JOINTS)

    cameras: list = []
    if not args.no_front:
        front = FrontCamera(index=args.front_index)
        front.start()
        print(f"Front  (RealSense): AVFoundation index {front.index}")
        cameras.append(front)
    if not args.no_lateral:
        lateral = LateralCamera()
        lateral.start()
        print("Lateral (OAK-D Pro): conectado")
        cameras.append(lateral)

    try:
        with cbreak():
            while True:
                now = time.perf_counter()

                for cam in cameras:
                    frame = cam.read()
                    if frame is not None:
                        viz.log_image(cam.name, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                if now >= next_tick:
                    leader_action = leader.get_action()
                    leader_pos = action_to_positions(leader_action)
                    viz.log_positions(leader_pos, source="leader")

                    if paused:
                        # Mantener la última pose: re-afirmar el goal previo cada
                        # tick (el torque ya lo sostiene; re-enviar es robusto).
                        # No copiamos el leader ni grabamos muestras.
                        if last_action is not None:
                            follower.send_action(last_action)
                            viz.log_positions(last_action, source="target")
                    else:
                        follower.send_action(leader_action)
                        viz.log_positions(leader_action, source="target")
                        last_action = leader_action

                        if recording:
                            samples.append({
                                "t": round(now - t_rec_start, 4),
                                "positions": [round(v, 2) for v in leader_pos],
                            })
                    next_tick += period
                    if next_tick < now:
                        next_tick = now + period

                if now - last_show > 0.1:
                    state = "PAUSED" if paused else ("REC" if recording else "live")
                    n = len(samples)
                    print(
                        f"\r  [{state}] "
                        + "  ".join(f"{j[:6]}={leader_pos[i]:+6.1f}" for i, j in enumerate(JOINTS))
                        + (f"  n={n}" if recording else "")
                        + "   ",
                        end="", flush=True,
                    )
                    last_show = now

                ch = read_key(timeout=0.001)
                if ch is None:
                    continue
                if ch in ("q", "\x03"):
                    print()
                    break
                if ch == " ":
                    if not paused:
                        paused = True
                        viz.log_event("teleop paused (hold)")
                        print("\n  [PAUSED] el follower mantiene la pose. "
                              "Espacio para reanudar.")
                    else:
                        # Reanudar: regresar suavemente a donde está el leader
                        # ahora (pudo moverse durante la pausa) para evitar un
                        # salto brusco, y luego seguir copiando en vivo.
                        print("\n  [RESUME] regresando suave a la pose del leader...")
                        leader_pos = action_to_positions(leader.get_action())
                        target = dict(zip(JOINTS, leader_pos))
                        interpolate_move(
                            follower, target,
                            duration=RESUME_DURATION, rate=args.rate,
                            max_deg_per_s=RESUME_MAX_DEG_PER_S, verbose=False,
                        )
                        last_action = positions_to_action(leader_pos)
                        paused = False
                        viz.log_event("teleop resumed")
                        next_tick = time.perf_counter() + period
                    continue
    finally:
        viz.log_event("teleop end")
        print("\nDesconectando follower y leader...")
        try:
            follower.disconnect()
        finally:
            leader.disconnect()
        for cam in cameras:
            cam.stop()

    if recording and samples and traj_path is not None:
        traj_io.save_trajectory(traj_path, samples, rate_hz=args.rate)
        print(f"Trayectoria guardada en {traj_path}  "
              f"({len(samples)} muestras, {samples[-1]['t']:.2f}s @ {args.rate} Hz)")
        print(f"Rerun recording guardado en {rrd_path}")

    return 0
