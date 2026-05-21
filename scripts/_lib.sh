# Funciones compartidas por los scripts/. Hace `source` desde cada wrapper.
# No ejecutar directamente.

set -euo pipefail

# Directorio del repo (un nivel arriba de scripts/).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Carga .env si existe (HUGGINGFACE_TOKEN, HF_USER).
if [ -f "${REPO_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${REPO_DIR}/.env"
    set +a
fi

# Lee un campo de un YAML simple (key: value). No soporta YAML anidado —
# nuestros configs son planos a propósito.
yaml_get() {
    local file="$1" key="$2"
    awk -F': *' -v k="${key}" '$1 == k { sub(/^[^:]+: */, ""); sub(/[[:space:]]+$/, ""); print; exit }' "${file}"
}

# Verifica que el comando exista en el entorno (típicamente dentro del .venv).
require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: '$1' no encontrado en PATH." >&2
        echo "       ¿Activaste el venv?  source ${REPO_DIR}/.venv/bin/activate" >&2
        exit 1
    fi
}

# Carga configs/follower.yaml o configs/leader.yaml en variables del shell:
#   ARM_TYPE, ARM_PORT, ARM_ID
load_arm_config() {
    local which="$1"   # "follower" o "leader"
    local cfg="${REPO_DIR}/configs/${which}.yaml"
    if [ ! -f "${cfg}" ]; then
        echo "ERROR: no existe ${cfg}" >&2
        exit 1
    fi
    ARM_TYPE="$(yaml_get "${cfg}" type)"
    ARM_PORT="$(yaml_get "${cfg}" port)"
    ARM_ID="$(yaml_get "${cfg}" id)"
    if [ -z "${ARM_TYPE}" ] || [ -z "${ARM_PORT}" ] || [ -z "${ARM_ID}" ]; then
        echo "ERROR: ${cfg} debe definir type, port, id" >&2
        exit 1
    fi
}
