#!/usr/bin/env bash
# Enlaza los archivos de calibración versionados en calibrations/ al directorio
# que LeRobot usa por default (~/.cache/huggingface/lerobot/calibration/).
#
# Hace symlinks (no copias) para que cualquier recalibración nueva quede
# automáticamente reflejada en el repo si se hace git add.
#
# Convención de nombres: el archivo calibrations/<id>.json se enlaza a
#   ~/.cache/huggingface/lerobot/calibration/so101_follower/<id>.json
#   ~/.cache/huggingface/lerobot/calibration/so101_leader/<id>.json
# según el config (follower.yaml o leader.yaml) que defina ese id.

source "$(dirname "$0")/_lib.sh"

CACHE_DIR="${HOME}/.cache/huggingface/lerobot/calibration"

install_one() {
    local which="$1"       # follower o leader
    local arm_type="$2"    # so101_follower o so101_leader
    load_arm_config "${which}"

    local src="${REPO_DIR}/calibrations/${ARM_ID}.json"
    if [ ! -f "${src}" ]; then
        echo "    (skip ${which}: no existe ${src})"
        return 0
    fi

    local dst_dir="${CACHE_DIR}/${arm_type}"
    local dst="${dst_dir}/${ARM_ID}.json"

    mkdir -p "${dst_dir}"

    if [ -e "${dst}" ] && [ ! -L "${dst}" ]; then
        echo "    WARNING: ${dst} ya existe y NO es symlink. Renombrando a .bak"
        mv "${dst}" "${dst}.bak"
    fi

    ln -sf "${src}" "${dst}"
    echo "==> ${which} (${ARM_ID}): ${dst} -> ${src}"
}

install_one follower so101_follower
install_one leader   so101_leader

echo
echo "Calibraciones enlazadas. LeRobot las leerá automáticamente cuando uses"
echo "el id correspondiente en --robot.id / --teleop.id."
