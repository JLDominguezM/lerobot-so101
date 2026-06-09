"""Inventario local: datasets, modelos, calibraciones y resumen de configs.

Todo es lectura de disco — no toca hardware. Directorios ausentes (outputs/train,
models) se tratan como vacíos, NO como error (todavía pueden no existir).

Reusa constantes/helpers de so101_cli (sin tocarlos):
  - record_dataset._count_episodes, LEROBOT_CACHE
  - config.REPO_DIR, config.load_arm_config
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ...config import REPO_DIR, load_arm_config
from ...record_dataset import LEROBOT_CACHE, _count_episodes

CALIB_DIR = REPO_DIR / "calibrations"
HF_HUB_CACHE = Path.home() / ".cache" / "huggingface" / "hub"


@dataclass(frozen=True)
class DatasetInfo:
    name: str
    episodes: int


@dataclass(frozen=True)
class ModelInfo:
    name: str
    source: str  # "outputs/train", "models", "hf-cache"


@dataclass(frozen=True)
class ArmInfo:
    which: str
    port: str
    id: str
    calib_present: bool
    calib_age_days: float | None


def list_datasets(cache: Path = LEROBOT_CACHE) -> list[DatasetInfo]:
    """Datasets LeRobot en cache (dir con meta/info.json), org/name o name a secas."""
    if not cache.exists():
        return []
    roots: set[Path] = set()
    for pattern in ("*/meta/info.json", "*/*/meta/info.json"):
        for info in cache.glob(pattern):
            roots.add(info.parent.parent)
    out = []
    for root in sorted(roots):
        try:
            name = str(root.relative_to(cache))
        except ValueError:
            name = root.name
        out.append(DatasetInfo(name=name, episodes=_count_episodes(root)))
    return out


def list_models() -> list[ModelInfo]:
    """Checkpoints locales (outputs/train, ./models) + modelos en cache de HF Hub."""
    out: list[ModelInfo] = []
    for base, src in ((REPO_DIR / "outputs" / "train", "outputs/train"),
                      (REPO_DIR / "models", "models")):
        if base.exists():
            for d in sorted(p for p in base.iterdir() if p.is_dir()):
                out.append(ModelInfo(name=d.name, source=src))
    if HF_HUB_CACHE.exists():
        for d in sorted(HF_HUB_CACHE.glob("models--*")):
            name = d.name[len("models--"):].replace("--", "/")
            out.append(ModelInfo(name=name, source="hf-cache"))
    return out


def arm_summary(which: str) -> ArmInfo:
    """Puerto + id + estado de calibración de un brazo. Seguro si falta el config."""
    try:
        cfg = load_arm_config(which)
    except Exception:
        return ArmInfo(which=which, port="?", id="?", calib_present=False, calib_age_days=None)
    port = str(cfg.get("port", "?"))
    arm_id = str(cfg.get("id", "?"))
    calib = CALIB_DIR / f"{arm_id}.json"
    present = calib.exists()
    age = (time.time() - calib.stat().st_mtime) / 86400.0 if present else None
    return ArmInfo(which=which, port=port, id=arm_id, calib_present=present, calib_age_days=age)
