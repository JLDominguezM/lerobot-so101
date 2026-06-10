"""Subcomando top-level: dume run delete-batch N

Borra los episodios de un batch (negro/verde/rojo) del dataset local.
Batch N (1-indexado) corresponde a los episodios (N-1)*3 .. (N-1)*3+2.
Si el batch está parcialmente grabado (p.ej. solo 1 de 3 episodios),
borra solo los que existan.

Usa `lerobot-edit-dataset --operation.type=delete_episodes` internamente.
La operación es in-place: guarda un backup automático antes de modificar.

Ejemplos:
    dume run delete-batch 21
    dume run delete-batch 21 --repo-id armando/so101_terminal_sort
    dume run delete-batch 21 --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BATCH_REPO_ID  = "armando/so101_terminal_sort"
LEROBOT_CACHE  = Path.home() / ".cache" / "huggingface" / "lerobot"
BATCH_SIZE     = 3


def _episode_indices(batch: int) -> list[int]:
    """Episodios 0-indexados que pertenecen al batch N (1-indexado)."""
    base = (batch - 1) * BATCH_SIZE
    return list(range(base, base + BATCH_SIZE))


def add_delete_batch_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "delete-batch",
        help="Borra los episodios de un batch del dataset local (soporta batches parciales).",
        description=(
            "Batch N (1-indexado) → episodios (N-1)×3, (N-1)×3+1, (N-1)×3+2.\n"
            "Si el batch quedó parcialmente grabado, borra solo los que existan.\n\n"
            "Ejemplos:\n"
            "  dume run delete-batch 21\n"
            "  dume run delete-batch 5 --dry-run\n"
        ),
    )
    p.add_argument("batch", type=int,
                   help="Número de batch a borrar (1-indexado).")
    p.add_argument("--repo-id", default=BATCH_REPO_ID,
                   help=f"Dataset local a editar (default: {BATCH_REPO_ID}).")
    p.add_argument("--root", type=Path, default=None,
                   help="Ruta local del dataset. Si omites se deriva de --repo-id.")
    p.add_argument("--push", action="store_true",
                   help="Subir el dataset modificado a HF Hub al terminar.")
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra qué se borraría sin ejecutar nada.")
    p.set_defaults(func=cmd_delete_batch)


def cmd_delete_batch(args: argparse.Namespace) -> int:
    all_episodes = _episode_indices(args.batch)
    root = args.root if args.root is not None else (LEROBOT_CACHE / args.repo_id)

    if not root.exists():
        print(f"ERROR: no existe el dataset en {root}")
        print(f"  ¿Usaste el --repo-id correcto?")
        return 2

    info_path = root / "meta" / "info.json"
    total_eps = json.loads(info_path.read_text()).get("total_episodes", 0)

    # Filtra solo los episodios que realmente existen en el dataset
    existing = [ep for ep in all_episodes if ep < total_eps]

    if not existing:
        print(f"El batch {args.batch} no tiene episodios grabados en el dataset.")
        print(f"  Episodios esperados : {all_episodes}")
        print(f"  Total en dataset    : {total_eps} episodios (0–{total_eps - 1})")
        print()
        print("No hay nada que borrar.")
        return 0

    missing = [ep for ep in all_episodes if ep not in existing]

    print(f"=== delete-batch ===")
    print(f"  batch             : {args.batch}")
    print(f"  episodios a borrar: {existing}", end="")
    if missing:
        print(f"  (parcial — {missing} no grabados)", end="")
    print()
    print(f"  dataset           : {args.repo_id}")
    print(f"  root              : {root}")
    print(f"  total actual      : {total_eps} episodios → quedarán {total_eps - len(existing)}")
    print(f"  push              : {'sí' if args.push else 'no'}")
    print()

    # Muestra task de cada episodio a borrar
    try:
        import pandas as pd
        tasks_parquet = root / "meta" / "tasks.parquet"
        tasks_df = pd.read_parquet(tasks_parquet) if tasks_parquet.exists() else None
        for ep_idx in existing:
            ep_file = root / "data" / "chunk-000" / f"file-{ep_idx:03d}.parquet"
            if ep_file.exists():
                df = pd.read_parquet(ep_file)
                task_idx = df["task_index"].iloc[0]
                task_str = ""
                if tasks_df is not None:
                    # tasks.parquet tiene el task como índice
                    for task_name, row in tasks_df.iterrows():
                        if row.iloc[0] == task_idx:
                            task_str = f"  → {task_name!r}"
                            break
                print(f"  ep {ep_idx:3d}: task_index={task_idx}{task_str}")
        print()
    except Exception:
        pass

    if args.dry_run:
        print("(--dry-run: nada fue borrado)")
        return 0

    confirm = input(
        f"¿Confirmar borrado de {len(existing)} episodio(s) del batch {args.batch}? [s/N] "
    ).strip().lower()
    if confirm not in ("s", "si", "sí", "y", "yes"):
        print("Cancelado.")
        return 0

    cmd = [
        sys.executable, "-m", "lerobot.scripts.lerobot_edit_dataset",
        f"--repo_id={args.repo_id}",
        f"--root={root}",
        f"--new_repo_id={args.repo_id}",
        f"--new_root={root}",
        "--operation.type=delete_episodes",
        f"--operation.episode_indices={json.dumps(existing)}",
        f"--push_to_hub={'true' if args.push else 'false'}",
    ]

    print("Ejecutando:")
    print("  " + " \\\n    ".join(cmd))
    print()

    rc = subprocess.call(cmd)
    if rc == 0:
        print(f"\nBatch {args.batch} borrado ({len(existing)} episodio(s)).")
        print("El dataset original quedó respaldado automáticamente por lerobot.")
    return rc
