#!/usr/bin/env bash
# Evalúa una policy entrenada corriéndola en el robot real.
# Reusa `lerobot-record` (con --policy.path) — graba un dataset con prefijo
# `eval_` que sirve como log de la corrida.
#
# Uso:
#   bash scripts/08_eval.sh <policy_name> "<task description>" [num_episodes]
#
# Ejemplo:
#   bash scripts/08_eval.sh act_pick_red_cube "Pick the red cube" 5

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-record

POLICY_NAME="${1:-}"
TASK_DESC="${2:-}"
NUM_EP="${3:-5}"

if [ -z "${POLICY_NAME}" ] || [ -z "${TASK_DESC}" ]; then
    echo "Uso: $0 <policy_name> \"<task description>\" [num_episodes]" >&2
    exit 2
fi

if [ -z "${HF_USER:-}" ]; then
    echo "ERROR: HF_USER no está definido." >&2
    exit 1
fi

load_arm_config follower

POLICY_REPO="${HF_USER}/${POLICY_NAME}"
EVAL_DATASET="${HF_USER}/eval_${POLICY_NAME}"

echo "==> Evaluando policy ${POLICY_REPO}"
echo "    Episodios: ${NUM_EP}, log dataset: ${EVAL_DATASET}"

exec lerobot-record \
    --robot.type="${ARM_TYPE}" \
    --robot.port="${ARM_PORT}" \
    --robot.id="${ARM_ID}" \
    --dataset.repo_id="${EVAL_DATASET}" \
    --dataset.num_episodes="${NUM_EP}" \
    --dataset.single_task="${TASK_DESC}" \
    --policy.path="${POLICY_REPO}"
