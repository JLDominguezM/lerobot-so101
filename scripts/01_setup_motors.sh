#!/usr/bin/env bash
# Asigna IDs (1..6) y baudrate a los motores de un brazo recién armado.
# Solo necesario UNA VEZ por motor (los settings quedan en la EEPROM).
#
# Uso:
#   bash scripts/01_setup_motors.sh follower
#   bash scripts/01_setup_motors.sh leader
#
# El comando es interactivo: te pide conectar UN motor a la vez al bus,
# le asigna el ID correspondiente al joint, y avanza al siguiente.

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-setup-motors

WHICH="${1:-}"
if [ "${WHICH}" != "follower" ] && [ "${WHICH}" != "leader" ]; then
    echo "Uso: $0 follower|leader" >&2
    exit 2
fi

load_arm_config "${WHICH}"

if [ "${WHICH}" = "follower" ]; then
    echo "==> Setup de motores del FOLLOWER (puerto ${ARM_PORT})"
    exec lerobot-setup-motors \
        --robot.type="${ARM_TYPE}" \
        --robot.port="${ARM_PORT}"
else
    echo "==> Setup de motores del LEADER (puerto ${ARM_PORT})"
    exec lerobot-setup-motors \
        --teleop.type="${ARM_TYPE}" \
        --teleop.port="${ARM_PORT}"
fi
