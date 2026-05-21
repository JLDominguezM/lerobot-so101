#!/usr/bin/env bash
# Detecta qué puerto USB corresponde a cuál brazo.
# Corre `lerobot-find-port`, que pide desconectar uno de los USB y por
# diferencia identifica cuál es el follower y cuál el leader.
#
# Anota los puertos detectados y edita configs/follower.yaml y configs/leader.yaml
# (o configura udev rules para puertos estables — ver udev/99-so101.rules).

source "$(dirname "$0")/_lib.sh"
require_cmd lerobot-find-port

echo "==> Corriendo lerobot-find-port"
echo "    Sigue las instrucciones interactivas."
echo
exec lerobot-find-port
