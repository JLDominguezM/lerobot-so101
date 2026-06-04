"""Nombres de joints y poses predefinidas."""

from __future__ import annotations

JOINTS: list[str] = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# Pose de reposo segura: brazo plegado, listo para apagar la fuente.
HOME: list[float] = [0, -104, 91, 41, 0, 1]

POSES: dict[str, list[float]] = {
    "home":  HOME,
    "zeros": [0, 0, 0, 0, 0, 0],
    "rest":  [0,  90,  90,  0, 0,  0],
    "wave":  [0, -30, -60,  0, 0,  0],
    "open":  [0,   0,   0,  0, 0, 40],
    "close": [0,   0,   0,  0, 0,  0],
}


def positions_to_action(values: list[float] | dict[str, float]) -> dict[str, float]:
    """Convierte una lista en orden de JOINTS o un dict joint->val en {joint.pos: val}."""
    if isinstance(values, dict):
        return {f"{j}.pos": values[j] for j in JOINTS}
    if len(values) != len(JOINTS):
        raise ValueError(f"Esperaba {len(JOINTS)} valores, recibí {len(values)}")
    return {f"{j}.pos": v for j, v in zip(JOINTS, values)}


def action_to_positions(action: dict[str, float]) -> list[float]:
    """Inversa de positions_to_action: extrae lista en orden de JOINTS."""
    return [action[f"{j}.pos"] for j in JOINTS]
