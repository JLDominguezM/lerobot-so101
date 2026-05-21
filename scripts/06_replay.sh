#!/usr/bin/env bash
# Reproduce un episodio grabado en el FOLLOWER (sin leader).
# Útil para verificar calidad de un episodio o repetir una demostración.
#
# Uso:
#   bash scripts/06_replay.sh <dataset_name> <episode_index>
#
# Ejemplo:
#   bash scripts/06_replay.sh pick_red_cube 0

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-replay

DATASET_NAME="${1:-}"
EPISODE="${2:-0}"

if [ -z "${DATASET_NAME}" ]; then
    echo "Uso: $0 <dataset_name> [episode_index]" >&2
    exit 2
fi

if [ -z "${HF_USER:-}" ]; then
    echo "ERROR: HF_USER no está definido." >&2
    exit 1
fi

load_arm_config follower

REPO_ID="${HF_USER}/${DATASET_NAME}"
echo "==> Replay episodio ${EPISODE} de ${REPO_ID}"

exec lerobot-replay \
    --robot.type="${ARM_TYPE}" \
    --robot.port="${ARM_PORT}" \
    --robot.id="${ARM_ID}" \
    --dataset.repo_id="${REPO_ID}" \
    --dataset.episode="${EPISODE}"
