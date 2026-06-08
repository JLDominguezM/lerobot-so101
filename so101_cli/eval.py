"""Subcomando top-level: ./cal eval

Corre una policy entrenada en el robot real usando lerobot-rollout.
No necesita el brazo leader conectado — la policy maneja el robot.

Estrategias:
  base    → corre N veces durante --duration segundos sin grabar (default)
  sentry  → igual pero graba cada rollout al dataset local

Ejemplo:
    ./cal eval --color red
    ./cal eval --color black --n 3 --duration 45
    ./cal eval --color green --record
    ./cal eval --color red --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .config import load_arm_config

POLICY_DEFAULT = "armandomm09/smolvla_terminal_sort"
TASK_TEMPLATE  = "pick the {color} cable and place it in the {color} box"
LEROBOT_CACHE  = Path.home() / ".cache" / "huggingface" / "lerobot"


def add_eval_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "eval",
        help="Corre una policy entrenada en el robot real.",
        description=(
            "Ejecuta la policy sobre el follower. No necesita el brazo leader.\n\n"
            "Ejemplos:\n"
            "  ./cal eval --color red\n"
            "  ./cal eval --color black --n 3 --duration 45\n"
            "  ./cal eval --color green --record   # guarda rollouts a disco\n"
        ),
    )
    p.add_argument(
        "--color", required=True, choices=["black", "green", "red"],
        help="Color del cable a recoger (black, green, red).",
    )
    p.add_argument(
        "--policy", default=POLICY_DEFAULT,
        help=f"HF repo_id de la policy (default: {POLICY_DEFAULT}).",
    )
    p.add_argument("--n", type=int, default=1,
                   help="Número de rollouts (default 1).")
    p.add_argument("--duration", type=float, default=60.0,
                   help="Segundos máximos por rollout (default 60).")
    p.add_argument("--fps", type=int, default=30,
                   help="FPS del loop de control (default 30).")
    p.add_argument("--front-index", type=int, default=0,
                   help="Índice OpenCV de la cámara 'front' (RealSense) (default 0).")
    p.add_argument("--no-lateral", action="store_true",
                   help="No usar la cámara lateral (OAK-D).")
    p.add_argument("--record", action="store_true",
                   help="Grabar rollouts al dataset local (estrategia sentry).")
    p.add_argument(
        "--repo-id", default=None,
        help="HF repo_id para el dataset de eval cuando --record "
             "(default: <HF_USER>/eval_act_terminal_sort).",
    )
    p.add_argument("--push", action="store_true",
                   help="Subir el dataset de eval a HF Hub al terminar (requiere --record).")
    p.add_argument("--device", default="mps",
                   help="Dispositivo torch para inferencia: mps (Mac, default), cpu, cuda.")
    p.add_argument(
        "--n-action-steps", type=int, default=None,
        help="Cuántas acciones del chunk ejecutar antes de re-observar (override del "
             "checkpoint, que trae 50). Bajarlo (p.ej. 15) hace al robot más reactivo: "
             "vuelve a mirar las cámaras más seguido y puede corregir el pick en vez de "
             "comprometerse a una trayectoria al centro. No requiere reentrenar.",
    )
    p.add_argument(
        "--num-steps", type=int, default=None,
        help="Pasos de integración del flow-matching en inferencia (override del "
             "checkpoint, que trae 10). Subirlo (p.ej. 20) produce acciones más nítidas "
             "y menos promediadas. No requiere reentrenar.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra el comando que se ejecutaría, sin correrlo.")
    p.set_defaults(func=cmd_eval)


def cmd_eval(args: argparse.Namespace) -> int:
    follower = load_arm_config("follower")
    task     = TASK_TEMPLATE.format(color=args.color)

    cameras: dict = {
        "front": {
            "type": "opencv",
            "index_or_path": args.front_index,
            "width": 640,
            "height": 480,
            "fps": args.fps,
        }
    }
    if not args.no_lateral:
        cameras["lateral"] = {
            "type": "depthai",
            "width": 640,
            "height": 480,
            "fps": args.fps,
        }

    # Base: solo corre, no graba. Sentry: corre + graba a dataset local.
    if args.record:
        hf_user = os.environ.get("HF_USER", "armandomm09")
        repo_id = args.repo_id or f"{hf_user}/eval_act_terminal_sort"
        root    = LEROBOT_CACHE / repo_id
        already_exists = root.exists()
        strategy = "sentry"
    else:
        strategy = "base"

    cmd = [
        sys.executable, "-m", "so101_cli._rollout_entry",
        f"--strategy.type={strategy}",
        f"--policy.path={args.policy}",
        f"--policy.device={args.device}",
        f"--robot.type={follower['type']}",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        f"--robot.cameras={json.dumps(cameras)}",
        f"--task={task}",
        f"--duration={args.duration}",
        f"--fps={args.fps}",
    ]

    # Overrides opcionales del config del checkpoint (draccus los aplica encima
    # de lo que trae el modelo, ver rollout/configs.py::_load_policy_config).
    if args.n_action_steps is not None:
        cmd.append(f"--policy.n_action_steps={args.n_action_steps}")
    if args.num_steps is not None:
        cmd.append(f"--policy.num_steps={args.num_steps}")

    if strategy == "sentry":
        cmd += [
            f"--dataset.repo_id={repo_id}",
            f"--dataset.root={root}",
            f"--dataset.single_task={task}",
            f"--dataset.num_episodes={args.n}",
            f"--dataset.fps={args.fps}",
            f"--dataset.push_to_hub={'true' if args.push else 'false'}",
            f"--resume={'true' if already_exists else 'false'}",
        ]

    print("=== eval ===")
    print(f"  color    : {args.color}")
    print(f"  task     : {task!r}")
    print(f"  policy   : {args.policy}")
    print(f"  strategy : {strategy}")
    print(f"  rollouts : {args.n}  (max {args.duration}s c/u)")
    if strategy == "sentry":
        print(f"  repo_id  : {repo_id}  (push={'sí' if args.push else 'no'})")
        print(f"  root     : {root}  (resume={'sí' if already_exists else 'no'})")
    print(f"  device   : {args.device}")
    if args.n_action_steps is not None:
        print(f"  n_action_steps : {args.n_action_steps}  (override; checkpoint=50)")
    if args.num_steps is not None:
        print(f"  num_steps      : {args.num_steps}  (override; checkpoint=10)")
    print(f"  front    : opencv idx={args.front_index}  640x480 @ {args.fps}fps")
    print(f"  lateral  : {'(desactivada)' if args.no_lateral else 'depthai (OAK-D)  640x480'}")
    print()
    print("Comando:")
    print("  " + " \\\n    ".join(cmd))
    print()

    if args.dry_run:
        return 0

    env = os.environ.copy()
    return subprocess.call(cmd, env=env)
