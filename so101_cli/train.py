"""Subcomando top-level: ./cal train

Entrena una policy (SmolVLA por defecto) sobre un dataset grabado, envolviendo
`lerobot-train`. Equivalente a scripts/09_train_smolvla.sh pero integrado al CLI.

SmolVLA recibe el task string como input real (language conditioning), a
diferencia de ACT. El checkpoint final se sube a <HF_USER>/<policy> y queda
local en outputs/train/<policy>/.

Requiere GPU (CUDA en el Spark). En Mac (mps) es MUY lento para SmolVLA.

Ejemplos:
    ./cal train                                  # smolvla sobre <HF_USER>/so101_terminal_sort
    ./cal train --dataset so101_terminal_sort
    ./cal train --policy smolvla_v2
    ./cal train --type act                       # entrena ACT (sin language)
    ./cal train --device mps                     # forzar Mac (lento)
    ./cal train --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

DEFAULT_DATASET = "so101_terminal_sort"

# Nombre de la policy por tipo. Coincide con el default de `eval` / `eval-viz`
# (armandomm09/smolvla_terminal_sort) para que train → eval apunten al mismo repo.
DEFAULT_POLICY = {
    "smolvla": "smolvla_terminal_sort",
    "act":     "act_terminal_sort",
}


def _hf_user() -> str:
    return os.environ.get("HF_USER", "").strip() or "armandomm09"


def add_train_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "train",
        help="Entrena una policy (SmolVLA por defecto) sobre un dataset.",
        description=(
            "Envuelve lerobot-train. SmolVLA usa el task string como input real.\n\n"
            "Ejemplos:\n"
            "  ./cal train\n"
            "  ./cal train --dataset so101_terminal_sort --policy smolvla_v2\n"
            "  ./cal train --device mps      # Mac (lento)\n"
            "  ./cal train --dry-run\n"
        ),
    )
    p.add_argument("--dataset", default=DEFAULT_DATASET,
                   help=f"Nombre del dataset (sin user). Se usa <HF_USER>/<dataset>. "
                        f"(default: {DEFAULT_DATASET})")
    p.add_argument("--policy", default=None,
                   help="Nombre de la policy de salida (default: smolvla_terminal_sort / "
                        "act_terminal_sort, igual que el default de eval).")
    p.add_argument("--type", default="smolvla", choices=["smolvla", "act"],
                   help="Tipo de policy (default: smolvla).")
    p.add_argument("--device", default="cuda",
                   help="Dispositivo de entrenamiento: cuda (Spark, default), mps, cpu.")
    p.add_argument("--steps", type=int, default=None,
                   help="Número de pasos de entrenamiento (default: el del policy config).")
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra el comando lerobot-train que se ejecutaría, sin correrlo.")
    p.set_defaults(func=cmd_train)


def cmd_train(args: argparse.Namespace) -> int:
    hf_user      = _hf_user()
    policy_name  = args.policy or DEFAULT_POLICY[args.type]
    dataset_repo = f"{hf_user}/{args.dataset}"
    policy_repo  = f"{hf_user}/{policy_name}"
    output_dir   = f"outputs/train/{policy_name}"

    cmd = [
        sys.executable, "-m", "lerobot.scripts.lerobot_train",
        f"--dataset.repo_id={dataset_repo}",
        f"--policy.type={args.type}",
        f"--policy.device={args.device}",
        f"--policy.repo_id={policy_repo}",
        f"--output_dir={output_dir}",
        f"--job_name={policy_name}",
    ]
    # SmolVLA: carga los pesos preentrenados del VLM (si no, el backbone arranca
    # en random y entrena malísimo). ACT no tiene este flag.
    if args.type == "smolvla":
        cmd.append("--policy.load_vlm_weights=true")
    if args.steps is not None:
        cmd.append(f"--steps={args.steps}")

    print("=== train ===")
    print(f"  tipo    : {args.type}")
    print(f"  dataset : {dataset_repo}")
    print(f"  policy  : {policy_repo}")
    print(f"  device  : {args.device}")
    print(f"  output  : {output_dir}")
    if args.steps is not None:
        print(f"  steps   : {args.steps}")
    print()
    print("Comando lerobot-train:")
    print("  " + " \\\n    ".join(cmd))
    print()

    if args.dry_run:
        return 0

    return subprocess.call(cmd, env=os.environ.copy())
