"""Visualiza un episodio de un LeRobotDataset en rerun, forzando el backend pyav.

Por qué este script y no `lerobot-dataset-viz` directo: en este Mac `torchcodec`
está roto (ABI incompatible con el torch instalado, y su ffmpeg no está en el
rpath). El tool oficial elige torchcodec por default solo porque está instalado
y truena al decodificar. `pyav` (paquete `av`, ya instalado) decodifica los mismos
videos sin problema, así que aquí construimos el dataset con `video_backend="pyav"`
y reusamos la MISMA función de visualización de LeRobot (motores + ambas cámaras
en rerun).

Uso:
  python view_dataset.py --repo-id armando/so101_clips_v3 --episode 0
  python view_dataset.py --repo-id armando/so101_clips_v3 --episode 2 --root <ruta>

Tip: corre con el venv activado (`source .venv/bin/activate`) para que rerun
encuentre su viewer.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.scripts.lerobot_dataset_viz import visualize_dataset


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-id", required=True,
                    help="repo_id del dataset (ej. armando/so101_clips_v3).")
    ap.add_argument("--episode", type=int, default=0,
                    help="Índice del episodio a visualizar (default 0).")
    ap.add_argument("--root", type=Path, default=None,
                    help="Carpeta local del dataset. Si se omite, se usa "
                         "~/.cache/huggingface/lerobot/<repo_id>.")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--save", action="store_true",
                    help="En vez de abrir el visor en vivo, escribe un .rrd en --output-dir "
                         "(determinista: luego lo abres con `rerun archivo.rrd`). "
                         "Recomendado en macOS, donde el visor en vivo a veces queda vacío "
                         "porque el proceso termina antes de vaciar el stream.")
    ap.add_argument("--output-dir", type=Path, default=Path("outputs/dataset_viz"),
                    help="Carpeta donde escribir el .rrd cuando --save (default outputs/dataset_viz).")
    args = ap.parse_args()

    print(f"Cargando {args.repo_id} (episodio {args.episode}) con backend pyav...")
    dataset = LeRobotDataset(
        args.repo_id,
        episodes=[args.episode],
        root=args.root,
        video_backend="pyav",
    )
    cams = [k for k in dataset.features if "image" in k]
    print(f"  episodios={dataset.num_episodes}  frames={dataset.num_frames}  cámaras={cams}")
    rrd = visualize_dataset(
        dataset,
        episode_index=args.episode,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        save=args.save,
        output_dir=args.output_dir if args.save else None,
    )
    if args.save and rrd is not None:
        print(f"\n.rrd guardado en: {rrd}")
        print(f"Ábrelo con:   rerun {rrd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
