#!/usr/bin/env python
"""Hace ping al bus y reporta qué motor IDs (1..6) responden.

Útil para:
  - Verificar conexión física antes de teleoperar/calibrar.
  - Después de un crash en setup_motors: saber qué IDs ya están asignados
    y cuáles faltan.

Uso (con el venv activado):
    python scripts/scan_bus.py leader
    python scripts/scan_bus.py follower
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

JOINT_NAMES = {
    1: "shoulder_pan",
    2: "shoulder_lift",
    3: "elbow_flex",
    4: "wrist_flex",
    5: "wrist_roll",
    6: "gripper",
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("leader", "follower"):
        print(__doc__)
        sys.exit(2)

    which = sys.argv[1]
    repo_dir = Path(__file__).resolve().parent.parent
    cfg_path = repo_dir / "configs" / f"{which}.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    port = cfg["port"]

    motors = {
        name: Motor(id_, "sts3215", MotorNormMode.RANGE_M100_100)
        for id_, name in JOINT_NAMES.items()
    }
    bus = FeetechMotorsBus(port=port, motors=motors, calibration=None)
    bus._connect(handshake=False)

    print(f"Escaneando bus en {port}...")
    ids_models = bus.broadcast_ping()
    bus.disconnect()

    if not ids_models:
        print("Nada en el bus. Verifica:")
        print("  - puerto correcto (ls /dev/ttyACM* o /dev/tty.usbmodem*)")
        print("  - fuente de poder de los motores")
        print("  - jumper del Waveshare en 'B' (USB)")
        print("  - JST bien encajados")
        sys.exit(1)

    print(f"\n{len(ids_models)} motor(es) respondiendo:")
    print(f"{'ID':>4}  {'Esperado':<14}  Modelo")
    print(f"{'-' * 4}  {'-' * 14}  {'-' * 8}")
    for id_, model in sorted(ids_models.items()):
        expected = JOINT_NAMES.get(id_, "?? (fuera de rango)")
        print(f"{id_:>4}  {expected:<14}  {model}")

    expected_ids = set(JOINT_NAMES.keys())
    found_ids = set(ids_models.keys())
    missing = expected_ids - found_ids
    extra = found_ids - expected_ids
    if missing:
        print(f"\nFALTANTES (esperados pero no responden): {sorted(missing)}")
    if extra:
        print(f"\nINESPERADOS (responden pero no esperados): {sorted(extra)}")
    if not missing and not extra:
        print("\n✓ Todos los motores 1..6 están presentes.")


if __name__ == "__main__":
    main()
