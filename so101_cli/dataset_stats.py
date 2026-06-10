"""Subcomando top-level: dume run dataset-stats

Muestra el balance del dataset local: episodios y frames por tarea (color).
Úsalo ANTES de gastar una noche de entrenamiento para verificar que cada color
está representado de forma pareja.

NOTA: la posición de la terminal NO se graba en el dataset — solo el color va en
el task string ("pick the <color> cable..."). Por eso el balance por terminal no
se puede calcular aquí; revisa tu protocolo de grabación para esa parte.

Ejemplos:
    dume run dataset-stats
    dume run dataset-stats --repo-id armando/so101_terminal_sort
    dume run dataset-stats --root /ruta/al/dataset
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

LEROBOT_CACHE   = Path.home() / ".cache" / "huggingface" / "lerobot"
DEFAULT_REPO_ID = "armando/so101_terminal_sort"

# Umbral de aviso: si el color con menos episodios está por debajo de este
# porcentaje del color con más, marcamos el dataset como desbalanceado.
_BALANCE_WARN_RATIO = 0.80


def add_dataset_stats_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "dataset-stats",
        help="Balance del dataset local: episodios y frames por color/tarea.",
        description=(
            "Cuenta episodios y frames por tarea (color) leyendo meta/episodes/.\n"
            "Útil para verificar que cada color está parejo antes de entrenar.\n\n"
            "La posición de la terminal NO está en el dataset, así que solo se\n"
            "reporta el balance por color.\n\n"
            "Ejemplos:\n"
            "  dume run dataset-stats\n"
            "  dume run dataset-stats --repo-id armando/so101_terminal_sort\n"
        ),
    )
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                   help=f"Dataset local a inspeccionar (default: {DEFAULT_REPO_ID}).")
    p.add_argument("--root", type=Path, default=None,
                   help="Ruta local del dataset. Si omites se deriva de --repo-id.")
    p.set_defaults(func=cmd_dataset_stats)


def _color_of(task: str) -> str:
    """Extrae el color del task string para ordenar/etiquetar (best-effort)."""
    for c in ("black", "green", "red", "negro", "verde", "rojo"):
        if c in task.lower():
            return c
    return task


def cmd_dataset_stats(args: argparse.Namespace) -> int:
    import pandas as pd

    root = args.root if args.root is not None else (LEROBOT_CACHE / args.repo_id)
    if not root.exists():
        print(f"ERROR: no existe el dataset en {root}")
        print(f"  ¿--repo-id correcto? ¿O pasa --root con la ruta exacta?")
        return 2

    info_path = root / "meta" / "info.json"
    if not info_path.exists():
        print(f"ERROR: no se encontró {info_path}")
        return 2

    info         = json.loads(info_path.read_text())
    total_eps    = info.get("total_episodes", 0)
    total_frames = info.get("total_frames", 0)
    fps          = info.get("fps", 30) or 30

    ep_files = sorted(glob.glob(str(root / "meta" / "episodes" / "chunk-*" / "file-*.parquet")))
    if not ep_files:
        print(f"ERROR: no hay archivos en {root / 'meta' / 'episodes'}")
        return 2

    df = pd.concat(
        (pd.read_parquet(f, columns=["episode_index", "tasks", "length"]) for f in ep_files),
        ignore_index=True,
    ).drop_duplicates("episode_index")

    # `tasks` viene como array/lista por episodio; tomamos el primero.
    def _first_task(t) -> str:
        if hasattr(t, "__len__") and not isinstance(t, str) and len(t) > 0:
            return str(t[0])
        return str(t)

    df["task"]  = df["tasks"].apply(_first_task)
    df["color"] = df["task"].apply(_color_of)

    grp = (
        df.groupby("task")
        .agg(episodes=("episode_index", "count"), frames=("length", "sum"))
        .reset_index()
    )
    grp["color"] = grp["task"].apply(_color_of)
    grp = grp.sort_values("color").reset_index(drop=True)

    sep = "=" * 64
    print(sep)
    print(f"  DATASET-STATS — {args.repo_id}")
    print(sep)
    print(f"  root          : {root}")
    print(f"  total episodes: {total_eps}   (en meta/episodes: {len(df)})")
    print(f"  total frames  : {total_frames}   (~{total_frames / fps / 60:.1f} min @ {fps}fps)")
    print(f"  tareas        : {len(grp)}")
    print(sep)

    max_eps = int(grp["episodes"].max()) if len(grp) else 0
    bar_w   = 28
    print(f"\n  {'tarea (color)':<14} {'episodios':>10} {'frames':>9} {'~seg':>7}  reparto")
    print("  " + "-" * 62)
    for _, row in grp.iterrows():
        eps   = int(row["episodes"])
        frm   = int(row["frames"])
        secs  = frm / fps
        fill  = int(round(bar_w * eps / max_eps)) if max_eps else 0
        bar   = "█" * fill + "·" * (bar_w - fill)
        print(f"  {row['color']:<14} {eps:>10} {frm:>9} {secs:>6.0f}s  {bar}")

    # Veredicto de balance
    print()
    if len(grp) >= 2:
        min_eps = int(grp["episodes"].min())
        ratio   = min_eps / max_eps if max_eps else 1.0
        under   = grp.loc[grp["episodes"].idxmin(), "color"]
        over    = grp.loc[grp["episodes"].idxmax(), "color"]
        if ratio >= _BALANCE_WARN_RATIO:
            print(f"  ✓ Balanceado: el color con menos ({under}, {min_eps}) está al "
                  f"{ratio*100:.0f}% del que más ({over}, {max_eps}).")
        else:
            faltan = max_eps - min_eps
            print(f"  ⚠ Desbalanceado: '{under}' tiene {min_eps} episodios vs '{over}' con "
                  f"{max_eps} ({ratio*100:.0f}%).")
            print(f"    Graba ~{faltan} episodio(s) más de '{under}' para emparejar.")
    else:
        print("  (Una sola tarea — nada que balancear.)")

    print()
    print("  Nota: la posición de la terminal no se registra en el dataset; este")
    print("  reporte solo cubre el balance por color. Para variar las posiciones,")
    print("  apóyate en el protocolo de record-batch (cables en terminales distintas).")
    return 0
