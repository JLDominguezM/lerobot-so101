"""Subcomando top-level: ./cal push-dataset

Sube el dataset local a HuggingFace Hub.

El nombre de la carpeta local (derivado de cuando se grabó) no tiene que
coincidir con el repo de HF donde se sube — se pasan por separado.

Ejemplos:
    ./cal push-dataset
    ./cal push-dataset --hf-repo-id armandomm09/so101_terminal_sort
    ./cal push-dataset --hf-repo-id armandomm09/so101_v2 --root /ruta/al/dataset
    ./cal push-dataset --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

LEROBOT_CACHE  = Path.home() / ".cache" / "huggingface" / "lerobot"
DEFAULT_LOCAL_REPO = "armando/so101_terminal_sort"   # como quedó grabado


def _default_hf_repo(local_dataset_name: str) -> str:
    """Construye el repo_id de HF usando HF_USER del entorno."""
    hf_user = os.environ.get("HF_USER", "").strip()
    dataset_name = local_dataset_name.split("/")[-1]  # "so101_terminal_sort"
    if hf_user:
        return f"{hf_user}/{dataset_name}"
    return f"armandomm09/{dataset_name}"              # fallback conocido


def _find_root(hf_repo_id: str, local_repo_id: str, explicit_root: Path | None) -> Path | None:
    """Busca la ruta local del dataset probando varias ubicaciones."""
    if explicit_root is not None:
        return explicit_root
    candidates = [
        LEROBOT_CACHE / local_repo_id,
        LEROBOT_CACHE / hf_repo_id,
    ]
    for c in candidates:
        if (c / "meta" / "info.json").exists():
            return c
    return None


def add_push_dataset_parser(sub: argparse._SubParsersAction, name: str = "push-dataset") -> None:
    p = sub.add_parser(
        name,
        help="Sube el dataset local a HuggingFace Hub.",
        description=(
            "Sube el dataset grabado con record-batch a HF Hub.\n"
            "El repo local y el repo de HF pueden tener nombres distintos.\n\n"
            "Ejemplos:\n"
            "  ./cal push dataset\n"
            "  ./cal push dataset --hf-repo-id armandomm09/so101_terminal_sort\n"
            "  ./cal push dataset --dry-run\n"
        ),
    )
    p.add_argument(
        "--hf-repo-id", default=None,
        help="Repo de HF donde subir (default: <HF_USER>/so101_terminal_sort).",
    )
    p.add_argument(
        "--local-repo-id", default=DEFAULT_LOCAL_REPO,
        help=f"Repo_id con el que se grabó localmente (determina la carpeta). "
             f"(default: {DEFAULT_LOCAL_REPO})",
    )
    p.add_argument("--root", type=Path, default=None,
                   help="Ruta local del dataset. Si omites se busca automáticamente.")
    p.add_argument("--private", action="store_true",
                   help="Subir como repositorio privado.")
    p.add_argument("--no-large", action="store_true",
                   help="Usa upload_folder clásico en vez de upload_large_folder. "
                        "Por defecto se usa upload_large_folder: sube en paralelo y "
                        "SE REANUDA si se corta (necesario para datasets grandes; el "
                        "upload_folder normal se atora con muchos archivos/GB).")
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra info del dataset sin subir nada.")
    p.set_defaults(func=cmd_push_dataset)


def cmd_push_dataset(args: argparse.Namespace) -> int:
    hf_repo_id = args.hf_repo_id or _default_hf_repo(args.local_repo_id)
    root = _find_root(hf_repo_id, args.local_repo_id, args.root)

    if root is None:
        print(f"ERROR: no se encontró el dataset local.")
        print(f"  Buscado en:")
        print(f"    {LEROBOT_CACHE / args.local_repo_id}")
        print(f"    {LEROBOT_CACHE / hf_repo_id}")
        print(f"  Pasa --root con la ruta exacta.")
        return 2

    info_path = root / "meta" / "info.json"
    if not info_path.exists():
        print(f"ERROR: no se encontró meta/info.json en {root}")
        return 2

    info         = json.loads(info_path.read_text())
    total_eps    = info.get("total_episodes", "?")
    total_frames = info.get("total_frames", "?")

    print(f"=== push-dataset ===")
    print(f"  local root    : {root}")
    print(f"  → HF repo     : https://huggingface.co/datasets/{hf_repo_id}")
    print(f"  total_episodes: {total_eps}")
    print(f"  total_frames  : {total_frames}")
    print(f"  privado       : {'sí' if args.private else 'no'}")
    print()

    if args.dry_run:
        print("(--dry-run: nada fue subido)")
        return 0

    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    print("Cargando dataset local...")
    ds = LeRobotDataset(args.local_repo_id, root=root)

    # Redirige a la cuenta correcta de HF sin mover ni regrabar nada.
    ds.repo_id = hf_repo_id
    ds.meta.repo_id = hf_repo_id

    use_large = not args.no_large
    metodo    = "upload_large_folder (paralelo, reanudable)" if use_large else "upload_folder (clásico)"
    print(f"Subiendo a https://huggingface.co/datasets/{hf_repo_id} ...")
    print(f"  método: {metodo}")
    if use_large:
        print(f"  (si se corta, vuelve a correr el mismo comando y continúa donde quedó)")
    ds.push_to_hub(private=args.private, upload_large_folder=use_large)
    print("¡Listo!")
    return 0
