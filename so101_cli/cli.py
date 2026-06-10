"""Árbol de subcomandos del CLI `dume run` (modo scriptable de DUM-E).

`build_parser()` es puro wiring: importa los `add_*_parser()` de cada módulo de
subcomando (la lógica vive en esos módulos, no acá). Lo invoca
`so101_cli.dume.__main__` cuando el primer argumento es `run`.
"""

from __future__ import annotations

import argparse
import sys

from .dataset_stats import add_dataset_stats_parser
from .delete_batch import add_delete_batch_parser
from .diagnostics import (
    add_check_parser,
    add_find_ports_parser,
    add_scan_bus_parser,
    add_setup_motors_parser,
)
from .eval import add_eval_parser
from .eval_viz import add_eval_viz_parser
from .follower import add_move_parser, add_replay_parser
from .leader import add_record_trajectory_parser, add_record_waypoint_parser
from .record_dataset import add_record_batch_parser, add_record_dataset_parser
from .teleop import add_teleop_parser
from .train import add_train_parser
from .transfer import add_pull_parser, add_push_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dume run",
        description="CLI scriptable del SO-101: move/replay (follower), record (leader), "
                    "teleop, record-dataset, train, eval y utilidades de hardware.",
    )
    top = parser.add_subparsers(dest="device", required=True,
                                metavar="{follower,leader,teleop,record-dataset,eval,eval-viz,"
                                        "find-ports,setup-motors,scan-bus,check}")

    # follower ...
    follower = top.add_parser("follower", help="Comandos del brazo follower (ejecuta movimientos).")
    fsub = follower.add_subparsers(dest="command", required=True, metavar="{move,replay}")
    add_move_parser(fsub)
    add_replay_parser(fsub)

    # leader ...
    leader = top.add_parser("leader", help="Comandos del brazo leader (teleoperación / grabación).")
    lsub = leader.add_subparsers(dest="command", required=True,
                                 metavar="{record-waypoint,record-trajectory}")
    add_record_waypoint_parser(lsub)
    add_record_trajectory_parser(lsub)

    # teleop (top-level: usa ambos brazos)
    add_teleop_parser(top)

    # record-dataset (top-level: wrapper sobre lerobot-record)
    add_record_dataset_parser(top)

    # record-batch (top-level: sesión estructurada negro/verde/rojo en batches de 3)
    add_record_batch_parser(top)

    # eval (top-level: corre una policy entrenada en el robot)
    add_eval_parser(top)

    # eval-viz (top-level: igual que eval pero con heatmap de activaciones en rerun)
    add_eval_viz_parser(top)

    # delete-batch (top-level: borra los 3 episodios de un batch del dataset)
    add_delete_batch_parser(top)

    # push / pull (top-level: mueve dataset o modelo a/desde HF Hub)
    add_push_parser(top)
    add_pull_parser(top)

    # train (top-level: entrena SmolVLA/ACT envolviendo lerobot-train)
    add_train_parser(top)

    # dataset-stats (top-level: balance de episodios/frames por color)
    add_dataset_stats_parser(top)

    # diagnóstico/setup de hardware (top-level: no mueven el brazo)
    add_find_ports_parser(top)      # qué USB es cada brazo
    add_setup_motors_parser(top)    # asigna IDs 1..6 (todos o uno con --motor)
    add_scan_bus_parser(top)        # ping al bus de un brazo
    add_check_parser(top)           # chequeo integral: ambos brazos + ambas cámaras

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
