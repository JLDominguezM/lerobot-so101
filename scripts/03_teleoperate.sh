#!/usr/bin/env bash
# Teleoperación: el LEADER controla al FOLLOWER en tiempo real.
# Ctrl-C para salir.
#
# Uso:
#   bash scripts/03_teleoperate.sh
#   bash scripts/03_teleoperate.sh --display_data=true     # visualización rerun

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-teleoperate

load_arm_config follower
F_TYPE="${ARM_TYPE}"; F_PORT="${ARM_PORT}"; F_ID="${ARM_ID}"

load_arm_config leader
L_TYPE="${ARM_TYPE}"; L_PORT="${ARM_PORT}"; L_ID="${ARM_ID}"

echo "==> Teleoperando: leader=${L_ID}(${L_PORT}) -> follower=${F_ID}(${F_PORT})"

exec lerobot-teleoperate \
    --robot.type="${F_TYPE}" \
    --robot.port="${F_PORT}" \
    --robot.id="${F_ID}" \
    --teleop.type="${L_TYPE}" \
    --teleop.port="${L_PORT}" \
    --teleop.id="${L_ID}" \
    "$@"
