#!/usr/bin/env bash
# Graba episodios de teleoperación a un dataset LeRobot (Parquet + videos).
# El dataset se sube automáticamente al HF Hub bajo ${HF_USER}/<nombre>.
#
# Uso:
#   bash scripts/05_record.sh "Pick the red cube" 10 pick_red_cube
#                              ^ descripción       ^ episodios   ^ nombre del dataset
#
# Sin cámaras por ahora: solo se graban estados de joints y acciones.

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-record

TASK_DESC="${1:-}"
NUM_EP="${2:-10}"
DATASET_NAME="${3:-}"

if [ -z "${TASK_DESC}" ] || [ -z "${DATASET_NAME}" ]; then
    cat <<'EOF' >&2
Uso: $0 "<task description>" <num_episodes> <dataset_name>

Ejemplo:
    bash scripts/05_record.sh "Pick the red cube and place it in the bin" 10 pick_red_cube

EOF
    exit 2
fi

if [ -z "${HF_USER:-}" ]; then
    echo "ERROR: HF_USER no está definido. Copia .env.example a .env y rellénalo," >&2
    echo "       o corre  hf auth login  y exporta HF_USER manualmente." >&2
    exit 1
fi

load_arm_config follower
F_TYPE="${ARM_TYPE}"; F_PORT="${ARM_PORT}"; F_ID="${ARM_ID}"

load_arm_config leader
L_TYPE="${ARM_TYPE}"; L_PORT="${ARM_PORT}"; L_ID="${ARM_ID}"

REPO_ID="${HF_USER}/${DATASET_NAME}"
echo "==> Grabando ${NUM_EP} episodios -> ${REPO_ID}"
echo "    Tarea: ${TASK_DESC}"

exec lerobot-record \
    --robot.type="${F_TYPE}" \
    --robot.port="${F_PORT}" \
    --robot.id="${F_ID}" \
    --teleop.type="${L_TYPE}" \
    --teleop.port="${L_PORT}" \
    --teleop.id="${L_ID}" \
    --dataset.repo_id="${REPO_ID}" \
    --dataset.num_episodes="${NUM_EP}" \
    --dataset.single_task="${TASK_DESC}"
