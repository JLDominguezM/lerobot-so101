"""Persistencia de waypoints y trayectorias en JSON.

Formatos:

Waypoints (lista de poses estáticas en orden):
{
  "type": "waypoints",
  "joints": ["shoulder_pan", ...],
  "points": [
    {"name": "wp1", "positions": [0, -50, 30, 0, 0, 0]},
    ...
  ]
}

Trayectoria (muestreo temporal):
{
  "type": "trajectory",
  "joints": ["shoulder_pan", ...],
  "rate_hz": 30,
  "duration_s": 12.5,
  "samples": [
    {"t": 0.000, "positions": [...]},
    {"t": 0.033, "positions": [...]},
    ...
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .poses import JOINTS


Kind = Literal["waypoints", "trajectory"]


def save_waypoints(path: Path, points: list[dict]) -> None:
    """`points` es lista de {'name': str, 'positions': [6 floats]}."""
    data = {
        "type": "waypoints",
        "joints": JOINTS,
        "points": points,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def save_trajectory(path: Path, samples: list[dict], rate_hz: float) -> None:
    """`samples` es lista de {'t': float, 'positions': [6 floats]}."""
    duration = samples[-1]["t"] if samples else 0.0
    data = {
        "type": "trajectory",
        "joints": JOINTS,
        "rate_hz": rate_hz,
        "duration_s": duration,
        "samples": samples,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load(path: Path) -> dict:
    with path.open() as f:
        data = json.load(f)
    if data.get("type") not in ("waypoints", "trajectory"):
        raise ValueError(f"{path}: tipo desconocido {data.get('type')!r}")
    if data.get("joints") != JOINTS:
        raise ValueError(
            f"{path}: orden/nombre de joints no coincide. "
            f"Esperaba {JOINTS}, archivo tiene {data.get('joints')}"
        )
    return data
