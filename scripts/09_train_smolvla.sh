#!/usr/bin/env bash
# Entrena una policy SmolVLA (VLM con language conditioning) sobre un dataset grabado.
# A diferencia de ACT, SmolVLA recibe el task string como input real — el modelo
# distingue "pick the red cable" de "pick the black cable".
#
# Uso:
#   bash scripts/09_train_smolvla.sh <dataset_name> [policy_name]
#
# Ejemplo:
#   bash scripts/09_train_smolvla.sh so101_terminal_sort smolvla_terminal_sort
#
# El checkpoint final se sube a ${HF_USER}/<policy_name> y queda local en
# outputs/train/<policy_name>/.
#
# Requiere GPU NVIDIA (o MPS en Mac, aunque MPS es mucho más lento).
# Para Mac local: añade --policy.device=mps

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-train

DATASET_NAME="${1:-}"
POLICY_NAME="${2:-smolvla_${DATASET_NAME}}"

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

echo "==> Entrenando SmolVLA (language-conditioned)"
echo "    Dataset: ${DATASET_REPO}"
echo "    Policy:  ${POLICY_REPO}"
echo "    Output:  ${OUTPUT_DIR}"
echo ""
echo "    SmolVLA usa el task string como input real al transformer."
echo "    El modelo aprende a distinguir colores por instrucción de lenguaje."

exec lerobot-train \
    --dataset.repo_id="${DATASET_REPO}" \
    --policy.type=smolvla \
    --policy.device=cuda \
    --policy.load_vlm_weights=true \
    --policy.repo_id="${POLICY_REPO}" \
    --output_dir="${OUTPUT_DIR}" \
    --job_name="${POLICY_NAME}"
