#!/usr/bin/env bash
# Entrena una policy ACT (Action Chunking Transformer) sobre un dataset grabado.
#
# Uso:
#   bash scripts/07_train_act.sh <dataset_name> [policy_name]
#
# Ejemplo:
#   bash scripts/07_train_act.sh pick_red_cube act_pick_red_cube
#
# El checkpoint final se sube a ${HF_USER}/<policy_name> y queda local en
# outputs/train/<policy_name>/.
#
# Requiere GPU NVIDIA. Si no tienes, edita --policy.device=cpu (será LENTO).

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-train

DATASET_NAME="${1:-}"
POLICY_NAME="${2:-act_${DATASET_NAME}}"

if [ -z "${DATASET_NAME}" ]; then
    echo "Uso: $0 <dataset_name> [policy_name]" >&2
    exit 2
fi

if [ -z "${HF_USER:-}" ]; then
    echo "ERROR: HF_USER no está definido." >&2
    exit 1
fi

DATASET_REPO="${HF_USER}/${DATASET_NAME}"
POLICY_REPO="${HF_USER}/${POLICY_NAME}"
OUTPUT_DIR="outputs/train/${POLICY_NAME}"

echo "==> Entrenando ACT"
echo "    Dataset: ${DATASET_REPO}"
echo "    Policy:  ${POLICY_REPO}"
echo "    Output:  ${OUTPUT_DIR}"

exec lerobot-train \
    --dataset.repo_id="${DATASET_REPO}" \
    --policy.type=act \
    --policy.device=cuda \
    --policy.repo_id="${POLICY_REPO}" \
    --output_dir="${OUTPUT_DIR}" \
    --job_name="${POLICY_NAME}"
