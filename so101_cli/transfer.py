"""Subcomandos top-level: dume run push {dataset,model}  y  dume run pull {dataset,model}

Mueve datasets y modelos entre tu máquina y HuggingFace Hub:

    dume run push dataset      # sube el dataset local grabado con record-batch
    dume run push model        # sube un checkpoint entrenado local
    dume run pull dataset      # baja el dataset al cache local (~/.cache/.../lerobot)
    dume run pull model        # baja un checkpoint a tu cache de HF Hub

`push dataset` reutiliza la lógica de push-dataset (ver push_dataset.py).
Para los modelos: `train` ya sube el modelo al terminar y `eval` ya lo baja
solo — push/pull model son por si quieres hacerlo manualmente.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .push_dataset import add_push_dataset_parser

LEROBOT_CACHE      = Path.home() / ".cache" / "huggingface" / "lerobot"
DEFAULT_DATASET    = "so101_terminal_sort"
DEFAULT_MODEL      = "smolvla_terminal_sort"


def _hf(name: str) -> str:
    """Construye <HF_USER>/<name> con fallback conocido."""
    user = os.environ.get("HF_USER", "").strip() or "armandomm09"
    return f"{user}/{name}"


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def add_push_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "push",
        help="Sube un dataset o un modelo a HuggingFace Hub.",
        description="Sube a HF Hub:\n  dume run push dataset\n  dume run push model",
    )
    what = p.add_subparsers(dest="what", required=True, metavar="{dataset,model}")

    # push dataset → reutiliza el parser de push-dataset con nombre "dataset"
    add_push_dataset_parser(what, name="dataset")

    # push model
    pm = what.add_parser(
        "model",
        help="Sube un checkpoint entrenado local a HF Hub.",
        description=(
            "Sube la carpeta de un checkpoint (formato lerobot) a HF Hub.\n\n"
            "Ejemplos:\n"
            "  dume run push model\n"
            "  dume run push model --path outputs/train/smolvla_terminal_sort/checkpoints/last/pretrained_model\n"
            "  dume run push model --repo-id armandomm09/smolvla_terminal_sort\n"
        ),
    )
    pm.add_argument(
        "--path", type=Path, default=None,
        help="Carpeta del checkpoint a subir. Default: el último checkpoint en "
             "outputs/train/<policy>/checkpoints/last/pretrained_model.",
    )
    pm.add_argument(
        "--repo-id", default=None,
        help=f"Repo de HF donde subir (default: <HF_USER>/{DEFAULT_MODEL}).",
    )
    pm.add_argument("--policy", default=DEFAULT_MODEL,
                    help=f"Nombre de la policy para derivar el path default (default: {DEFAULT_MODEL}).")
    pm.add_argument("--private", action="store_true", help="Subir como repo privado.")
    pm.add_argument("--dry-run", action="store_true", help="Muestra qué se subiría, sin subir.")
    pm.set_defaults(func=cmd_push_model)


def cmd_push_model(args: argparse.Namespace) -> int:
    from huggingface_hub import HfApi

    repo_id = args.repo_id or _hf(args.policy)
    path    = args.path or Path(
        f"outputs/train/{args.policy}/checkpoints/last/pretrained_model"
    )
    exists  = path.exists()

    print("=== push model ===")
    print(f"  local : {path}" + ("" if exists else "   (aviso: no existe aún)"))
    print(f"  → HF  : https://huggingface.co/{repo_id}  (privado={'sí' if args.private else 'no'})")
    print()
    if args.dry_run:
        print("(--dry-run: nada fue subido)")
        return 0

    if not exists:
        print(f"ERROR: no existe el checkpoint en {path}")
        print(f"  Pasa --path con la carpeta correcta (la que tiene config.json + model.safetensors).")
        return 2

    api = HfApi()
    api.create_repo(repo_id, repo_type="model", private=args.private, exist_ok=True)
    print(f"Subiendo {path} → {repo_id} ...")
    api.upload_folder(folder_path=str(path), repo_id=repo_id, repo_type="model")
    print("¡Listo!")
    return 0


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

def add_pull_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "pull",
        help="Baja un dataset o un modelo desde HuggingFace Hub.",
        description="Baja de HF Hub:\n  dume run pull dataset\n  dume run pull model",
    )
    what = p.add_subparsers(dest="what", required=True, metavar="{dataset,model}")

    # pull dataset
    pd = what.add_parser(
        "dataset",
        help="Baja el dataset al cache local.",
        description=(
            "Descarga el dataset de HF Hub a ~/.cache/huggingface/lerobot/<repo-id>.\n\n"
            "Ejemplos:\n"
            "  dume run pull dataset\n"
            "  dume run pull dataset --repo-id armandomm09/so101_terminal_sort\n"
        ),
    )
    pd.add_argument("--repo-id", default=None,
                    help=f"Repo del dataset en HF (default: <HF_USER>/{DEFAULT_DATASET}).")
    pd.set_defaults(func=cmd_pull_dataset)

    # pull model
    pm = what.add_parser(
        "model",
        help="Baja un checkpoint al cache de HF Hub.",
        description=(
            "Descarga un modelo de HF Hub al cache (~/.cache/huggingface/hub).\n"
            "Nota: `eval` ya baja el modelo solo; esto es para pre-descargarlo.\n\n"
            "Ejemplos:\n"
            "  dume run pull model\n"
            "  dume run pull model --repo-id armandomm09/smolvla_terminal_sort\n"
        ),
    )
    pm.add_argument("--repo-id", default=None,
                    help=f"Repo del modelo en HF (default: <HF_USER>/{DEFAULT_MODEL}).")
    pm.set_defaults(func=cmd_pull_model)


def cmd_pull_dataset(args: argparse.Namespace) -> int:
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    repo_id = args.repo_id or _hf(DEFAULT_DATASET)
    print("=== pull dataset ===")
    print(f"  repo : {repo_id}")
    print(f"  Bajando a {LEROBOT_CACHE / repo_id} ...")
    print()
    ds = LeRobotDataset(repo_id)
    print(f"¡Listo! {ds.meta.total_episodes} episodios en {ds.root}")
    return 0


def cmd_pull_model(args: argparse.Namespace) -> int:
    from huggingface_hub import snapshot_download

    repo_id = args.repo_id or _hf(DEFAULT_MODEL)
    print("=== pull model ===")
    print(f"  repo : {repo_id}")
    print()
    path = snapshot_download(repo_id)
    print(f"¡Listo! Modelo en {path}")
    return 0
