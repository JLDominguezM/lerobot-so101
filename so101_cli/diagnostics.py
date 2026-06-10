"""Diagnóstico y setup de hardware: puertos, motores y chequeo de conexión.

Agrupa los comandos que NO mueven el brazo, solo verifican o configuran el
hardware antes de teleoperar, grabar o entrenar. Son ports a nivel CLI de los
scripts sueltos en `scripts/` (find_ports, scan_bus, setup_one_motor,
01_setup_motors), más un chequeo integral nuevo:

  dume run find-ports                                  -> lerobot-find-port (qué USB es cada brazo)
  dume run setup-motors follower|leader                -> asigna IDs 1..6 a los 6 motores (interactivo)
  dume run setup-motors follower|leader --motor gripper -> reconfigura UN solo motor (recovery)
  dume run scan-bus follower|leader                    -> ping al bus: qué motor IDs responden
  dume run check                                       -> chequeo integral: ambos brazos + ambas cámaras
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from .config import load_arm_config
from .poses import JOINTS

# IDs en orden de la cadena daisy-chain (= índice en JOINTS, 1-based).
JOINT_IDS: dict[str, int] = {name: i for i, name in enumerate(JOINTS, start=1)}
JOINT_NAMES: dict[int, str] = {i: name for name, i in JOINT_IDS.items()}


# --------------------------------------------------------------- helpers bus

def _build_bus(port: str):
    """Construye un FeetechMotorsBus con los 6 motores esperados (sin calibración)."""
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus

    motors = {
        name: Motor(id_, "sts3215", MotorNormMode.RANGE_M100_100)
        for name, id_ in JOINT_IDS.items()
    }
    return FeetechMotorsBus(port=port, motors=motors, calibration=None)


def _ping_bus(port: str) -> dict[int, int]:
    """Abre el bus, hace broadcast_ping y devuelve {id: modelo}. Cierra al final.

    Lanza si el puerto no abre; el caller decide cómo reportarlo.
    """
    bus = _build_bus(port)
    bus._connect(handshake=False)
    try:
        return bus.broadcast_ping() or {}
    finally:
        try:
            bus.disconnect()
        except Exception:
            # disconnect falla si faltan motores — esperado, no es error fatal.
            pass


# --------------------------------------------------------------- find-ports

def cmd_find_ports(args: argparse.Namespace) -> int:
    print("==> Corriendo lerobot-find-port (sigue las instrucciones interactivas).")
    print("    Te pedirá desconectar un USB a la vez para identificar cada brazo.\n")
    try:
        return subprocess.run(["lerobot-find-port"]).returncode
    except FileNotFoundError:
        print("ERROR: no encontré 'lerobot-find-port'. ¿Activaste el venv "
              "(source .venv/bin/activate)?", file=sys.stderr)
        return 1


# -------------------------------------------------------------- setup-motors

def cmd_setup_motors(args: argparse.Namespace) -> int:
    cfg = load_arm_config(args.which)
    port = cfg["port"]
    if args.motor:
        return _setup_one_motor(args.which, port, args.motor)
    return _setup_all_motors(args.which, cfg["type"], port)


def _setup_all_motors(which: str, arm_type: str, port: str) -> int:
    """Configura los 6 motores en orden, envolviendo lerobot-setup-motors."""
    flag = "robot" if which == "follower" else "teleop"
    print(f"==> Setup de TODOS los motores del {which.upper()} (puerto {port})")
    print("    Interactivo: conecta UN motor a la vez cuando lo pida.\n")
    cmd = ["lerobot-setup-motors", f"--{flag}.type={arm_type}", f"--{flag}.port={port}"]
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        print("ERROR: no encontré 'lerobot-setup-motors'. ¿Activaste el venv?",
              file=sys.stderr)
        return 1


def _setup_one_motor(which: str, port: str, motor_name: str) -> int:
    """Reconfigura un único motor por su nombre de joint (recovery)."""
    bus = _build_bus(port)
    print(f"Bus del {which}: {port}")
    print(f"Motor a configurar: '{motor_name}' (ID destino = {JOINT_IDS[motor_name]})")
    input(f"Conecta SOLO el motor '{motor_name}' al bus (data + power) y presiona Enter...")
    bus.setup_motor(motor_name)
    print(f"OK: '{motor_name}' configurado con ID={JOINT_IDS[motor_name]}")
    return 0


# ------------------------------------------------------------------ scan-bus

def cmd_scan_bus(args: argparse.Namespace) -> int:
    cfg = load_arm_config(args.which)
    port = cfg["port"]
    print(f"Escaneando bus del {args.which} en {port}...")
    try:
        ids_models = _ping_bus(port)
    except Exception as e:
        print(f"ERROR abriendo el bus en {port}: {e}", file=sys.stderr)
        print("Verifica puerto, fuente de poder de los motores y el jumper del "
              "Waveshare en 'B' (USB).", file=sys.stderr)
        return 1

    if not ids_models:
        print("Nada en el bus. Verifica:")
        print("  - puerto correcto (configs/{follower,leader}.yaml; o dume run find-ports)")
        print("  - fuente de poder de los motores")
        print("  - jumper del Waveshare en 'B' (USB)")
        print("  - JST bien encajados")
        return 1

    print(f"\n{len(ids_models)} motor(es) respondiendo:")
    print(f"{'ID':>4}  {'Esperado':<14}  Modelo")
    print(f"{'-' * 4}  {'-' * 14}  {'-' * 8}")
    for id_, model in sorted(ids_models.items()):
        expected = JOINT_NAMES.get(id_, "?? (fuera de rango)")
        print(f"{id_:>4}  {expected:<14}  {model}")

    missing = set(JOINT_IDS.values()) - set(ids_models)
    extra = set(ids_models) - set(JOINT_IDS.values())
    if missing:
        names = ", ".join(JOINT_NAMES[i] for i in sorted(missing))
        print(f"\nFALTANTES (esperados pero no responden): {sorted(missing)} ({names})")
    if extra:
        print(f"\nINESPERADOS (responden pero no esperados): {sorted(extra)}")
    if not missing and not extra:
        print("\n✓ Todos los motores 1..6 están presentes.")
        return 0
    return 1


# --------------------------------------------------------------------- check

def cmd_check(args: argparse.Namespace) -> int:
    """Chequeo integral: pinga ambos brazos y abre ambas cámaras un instante."""
    print("Chequeo de conexión del SO-101")
    print("=" * 32)
    results: list[tuple[str, bool, str]] = []

    arms = ["follower"] + ([] if args.no_leader else ["leader"])
    for which in arms:
        print(f"\n-> {which} (motores)...")
        results.append(_check_arm(which))

    if not args.no_front:
        print("\n-> front (RealSense)...")
        results.append(_check_front())
    if not args.no_lateral:
        print("\n-> lateral (OAK-D)...")
        results.append(_check_lateral())

    print("\nResumen:")
    width = max(len(name) for name, _, _ in results)
    for name, ok, detail in results:
        print(f"  {'✓' if ok else '✗'} {name:<{width}}  {detail}")

    all_ok = all(ok for _, ok, _ in results)
    print("\n" + ("✓ Todo conectado." if all_ok
                  else "✗ Hay componentes sin responder (ver detalle arriba)."))
    return 0 if all_ok else 1


def _check_arm(which: str) -> tuple[str, bool, str]:
    label = f"{which} (motores)"
    try:
        cfg = load_arm_config(which)
        port = cfg["port"]
        ids_models = _ping_bus(port)
    except Exception as e:
        return (label, False, f"no abrió el bus: {e}")
    found = set(ids_models)
    if not found:
        return (label, False, f"{port}: nada en el bus")
    missing = set(JOINT_IDS.values()) - found
    if missing:
        names = ", ".join(JOINT_NAMES[i] for i in sorted(missing))
        return (label, False, f"{len(found)}/6 @ {port}; faltan {sorted(missing)} ({names})")
    return (label, True, f"6/6 motores @ {port}")


def _check_front() -> tuple[str, bool, str]:
    from .cameras import FrontCamera
    return _probe_camera("front (RealSense)", FrontCamera())


def _check_lateral() -> tuple[str, bool, str]:
    from .cameras import LateralCamera
    return _probe_camera("lateral (OAK-D)", LateralCamera())


def _probe_camera(label: str, cam, timeout: float = 5.0) -> tuple[str, bool, str]:
    """Abre la cámara, espera un frame real (hasta `timeout` s) y la cierra."""
    try:
        cam.start()
    except Exception as e:
        return (label, False, f"no abrió: {e}")
    try:
        deadline = time.time() + timeout
        frame = None
        while time.time() < deadline:
            frame = cam.read()
            if frame is not None:
                break
            time.sleep(0.05)
        if frame is None:
            return (label, False, f"abrió pero sin frame en {timeout:.0f}s")
        h, w = frame.shape[:2]
        return (label, True, f"frame {w}x{h}")
    finally:
        cam.stop()


# ------------------------------------------------------------------ parsers

def add_find_ports_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "find-ports",
        help="Identifica qué puerto USB es cada brazo (envuelve lerobot-find-port).",
    )
    p.set_defaults(func=cmd_find_ports)


def add_setup_motors_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "setup-motors",
        help="Asigna IDs 1..6 a los motores de un brazo (todos, o uno con --motor).",
    )
    p.add_argument("which", choices=["follower", "leader"])
    p.add_argument(
        "--motor", choices=list(JOINT_IDS),
        help="Configura SOLO este motor (recovery tras un crash). "
             "Sin esto, configura los 6 en orden.",
    )
    p.set_defaults(func=cmd_setup_motors)


def add_scan_bus_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "scan-bus",
        help="Ping al bus: reporta qué motor IDs (1..6) responden.",
    )
    p.add_argument("which", choices=["follower", "leader"])
    p.set_defaults(func=cmd_scan_bus)


def add_check_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "check",
        help="Chequeo integral: ambos brazos + ambas cámaras conectados.",
    )
    p.add_argument("--no-leader", action="store_true", help="No revisar el brazo leader.")
    p.add_argument("--no-front", action="store_true", help="No revisar la cámara front (RealSense).")
    p.add_argument("--no-lateral", action="store_true", help="No revisar la cámara lateral (OAK-D).")
    p.set_defaults(func=cmd_check)
