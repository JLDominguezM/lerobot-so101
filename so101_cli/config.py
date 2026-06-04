"""Carga de configs/follower.yaml y configs/leader.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_DIR = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_DIR / "configs"


def load_arm_config(which: str) -> dict:
    """Carga el YAML de 'follower' o 'leader'."""
    if which not in ("follower", "leader"):
        raise ValueError(f"which debe ser 'follower' o 'leader', recibí {which!r}")
    path = CONFIGS_DIR / f"{which}.yaml"
    with path.open() as f:
        return yaml.safe_load(f)
