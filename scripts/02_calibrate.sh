#!/usr/bin/env bash
# Calibra rangos (homing, mid-range, max-range) de un brazo.
# La calibración la guarda LeRobot bajo el `id` configurado en configs/<arm>.yaml.
#
# Uso:
#   bash scripts/02_calibrate.sh follower
#   bash scripts/02_calibrate.sh leader
#   bash scripts/02_calibrate.sh both          # ambos en secuencia

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-calibrate

calibrate_one() {
    local which="$1"
    load_arm_config "${which}"

    if [ "${which}" = "follower" ]; then
        echo "==> Calibrando FOLLOWER (id=${ARM_ID}, puerto=${ARM_PORT})"
        lerobot-calibrate \
            --robot.type="${ARM_TYPE}" \
            --robot.port="${ARM_PORT}" \
            --robot.id="${ARM_ID}"
    else
        echo "==> Calibrando LEADER (id=${ARM_ID}, puerto=${ARM_PORT})"
        lerobot-calibrate \
            --teleop.type="${ARM_TYPE}" \
            --teleop.port="${ARM_PORT}" \
            --teleop.id="${ARM_ID}"
    fi
}

WHICH="${1:-both}"
case "${WHICH}" in
    follower|leader) calibrate_one "${WHICH}" ;;
    both)            calibrate_one follower && calibrate_one leader ;;
    *)               echo "Uso: $0 [follower|leader|both]" >&2; exit 2 ;;
esac
