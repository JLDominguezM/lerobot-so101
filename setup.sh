#!/usr/bin/env bash
# Bootstrap del repo so101:
#   1. Verifica que uv esté instalado.
#   2. Asegura Python 3.12 (uv lo instala si falta).
#   3. Clona huggingface/lerobot como hermano (../lerobot) si no existe.
#   4. Crea el venv y resuelve dependencias con uv sync.
#   5. Recuerda configurar permisos de USB y udev rules.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${REPO_DIR}/.." && pwd)"
LEROBOT_DIR="${WORKSPACE_DIR}/lerobot"

echo "==> Repo so101:    ${REPO_DIR}"
echo "==> Workspace:     ${WORKSPACE_DIR}"
echo "==> LeRobot clone: ${LEROBOT_DIR}"
echo

# --- 1. uv -------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
    cat <<'EOF'
ERROR: 'uv' no está instalado.

Instálalo con (oficial, recomendado):
    curl -LsSf https://astral.sh/uv/install.sh | sh

Luego reinicia la terminal (o haz `source ~/.bashrc`) y vuelve a correr este script.
EOF
    exit 1
fi
echo "==> uv $(uv --version)"

# --- 2. Python 3.12 ----------------------------------------------------------
echo "==> Asegurando Python 3.12 (uv lo gestiona)"
uv python install 3.12

# --- 3. Clone de LeRobot -----------------------------------------------------
if [ ! -d "${LEROBOT_DIR}/.git" ]; then
    echo "==> Clonando huggingface/lerobot en ${LEROBOT_DIR}"
    git clone https://github.com/huggingface/lerobot.git "${LEROBOT_DIR}"
else
    echo "==> LeRobot ya existe en ${LEROBOT_DIR} (no se vuelve a clonar)"
    echo "    Para actualizar: cd ${LEROBOT_DIR} && git pull"
fi

# --- 4. uv sync --------------------------------------------------------------
cd "${REPO_DIR}"
echo "==> Resolviendo dependencias con uv sync"

# Si la red no alcanza download.pytorch.org, LeRobot falla porque pinea
# torch al index pytorch-cu128. Detectamos el timeout y aplicamos un patch
# que cambia torch/torchvision a PyPI estándar.
patch_lerobot_torch_source() {
    local pyp="${LEROBOT_DIR}/pyproject.toml"
    if grep -q '^torch = \[{ index = "pytorch-cu128"' "${pyp}"; then
        echo "==> Aplicando patch: deshabilitando pin torch->pytorch-cu128 en LeRobot"
        sed -i.bak \
            -e 's|^torch = \[{ index = "pytorch-cu128"|# (patched, red bloquea pytorch.org)\n# torch = [{ index = "pytorch-cu128"|' \
            -e 's|^torchvision = \[{ index = "pytorch-cu128"|# torchvision = [{ index = "pytorch-cu128"|' \
            "${pyp}"
    fi
}

if ! uv sync; then
    echo "==> uv sync falló — probablemente la red no alcanza download.pytorch.org"
    patch_lerobot_torch_source
    echo "==> Reintentando uv sync"
    uv sync
fi

# --- 5. Recordatorios manuales -----------------------------------------------
cat <<EOF

==> Bootstrap completo.

Próximos pasos (manuales):

  1. Activar entorno:
         source .venv/bin/activate

  2. Permisos USB (una sola vez):
         sudo usermod -aG dialout \$USER
         # cerrar sesión y volver a entrar para que aplique el grupo

  3. Detectar puertos de los brazos:
         bash scripts/00_find_ports.sh

  4. (Opcional pero recomendado) instalar udev rules para puertos estables
     /dev/so101_follower y /dev/so101_leader:
         # primero edita udev/99-so101.rules con los seriales detectados
         sudo cp udev/99-so101.rules /etc/udev/rules.d/
         sudo udevadm control --reload-rules && sudo udevadm trigger

  5. Asignar IDs a los motores (una vez por brazo nuevo):
         bash scripts/01_setup_motors.sh follower
         bash scripts/01_setup_motors.sh leader

  6. Calibrar rangos:
         bash scripts/02_calibrate.sh

  7. Teleoperar:
         bash scripts/03_teleoperate.sh

Documentación oficial SO-101: https://huggingface.co/docs/lerobot/so101
EOF
