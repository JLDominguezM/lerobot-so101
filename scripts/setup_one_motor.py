#!/usr/bin/env python
"""Configura UN solo motor del SO-101 (leader o follower).

Útil cuando `lerobot-setup-motors` crashea a la mitad: no tienes que
re-empezar desde 0, solo retry del motor que falló.

Uso (con el venv activado):
    python scripts/setup_one_motor.py leader   wrist_flex
    python scripts/setup_one_motor.py follower gripper

motor_name: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper

Lee el puerto desde configs/{leader,follower}.yaml.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

JOINT_IDS = {
    "shoulder_pan": 1,
    "shoulder_lift": 2,
    "elbow_flex": 3,
    "wrist_flex": 4,
    "wrist_roll": 5,
    "gripper": 6,
}


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)

    which, motor_name = sys.argv[1], sys.argv[2]
    if which not in ("leader", "follower"):
        sys.exit(f"ERROR: primer arg debe ser 'leader' o 'follower', no '{which}'")
    if motor_name not in JOINT_IDS:
        sys.exit(
            f"ERROR: motor_name '{motor_name}' inválido. "
            f"Opciones: {', '.join(JOINT_IDS)}"
        )

    repo_dir = Path(__file__).resolve().parent.parent
    cfg_path = repo_dir / "configs" / f"{which}.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    port = cfg["port"]

    motors = {
        name: Motor(id_, "sts3215", MotorNormMode.RANGE_M100_100)
        for name, id_ in JOINT_IDS.items()
    }
    bus = FeetechMotorsBus(port=port, motors=motors, calibration=None)

    print(f"Bus: {port}")
    print(f"Motor a configurar: '{motor_name}' (ID destino = {JOINT_IDS[motor_name]})")
    input(
        f"Conecta SOLO el motor '{motor_name}' al bus (data + power) y presiona Enter..."
    )

    bus.setup_motor(motor_name)
    print(f"OK: '{motor_name}' configurado con ID={JOINT_IDS[motor_name]}")


if __name__ == "__main__":
    main()
