# Troubleshooting

## `Permission denied: '/dev/ttyACM0'`

Tu usuario no está en `dialout`:

```bash
sudo usermod -aG dialout $USER
# Cierra sesión y vuelve a entrar (o reinicia). `newgrp dialout` funciona solo en la shell actual.
groups | grep dialout   # verifica
```

Workaround temporal (NO sobrevive a reconexión del USB):

```bash
sudo chmod 666 /dev/ttyACM0 /dev/ttyACM1
```

## Los puertos `/dev/ttyACM*` se intercambian al reconectar

Los nombres `ttyACM0`/`ttyACM1` los asigna el kernel en orden de detección. Si desconectas y reconectas, pueden cambiar. Solución: instalar las udev rules de este repo (`udev/99-so101.rules`) que crean symlinks estables por serial.

## `lerobot-find-port` no detecta cambio

Asegúrate de:

1. Tener UN solo USB conectado al principio.
2. Cuando el script te pida desconectar, realmente sacar el cable USB (no apagar el brazo).
3. Esperar 2-3 segundos antes de presionar Enter.

## El follower no se mueve, pero el leader sí lee posiciones

Suele ser uno de tres:

- **Fuente de poder del follower apagada** — los motores leen, pero no tienen torque.
- **Calibración mala del follower** — los límites le dicen que está fuera de rango y se autobloquea.
- **Joints físicamente bloqueados** — choca con su soporte/mesa.

Revisa logs de `lerobot-teleoperate` por mensajes de "overload" o "torque off".

## `uv sync` falla por path source de lerobot

`pyproject.toml` asume que `../lerobot/` existe. Si te brincaste `setup.sh`:

```bash
cd ..
git clone https://github.com/huggingface/lerobot.git
cd so101
uv sync
```

## Entrenamiento `lerobot-train` falla con "CUDA out of memory"

Reduce el batch size:

```bash
bash scripts/07_train_act.sh pick_red_cube  # ver script, agregar:
# --policy.batch_size=4
```

O fuerza CPU (lentísimo, solo para debug):

```bash
# editar 07_train_act.sh y cambiar --policy.device=cuda por --policy.device=cpu
```

## `hf auth login` no encuentra token

Define el token en `.env` (`HUGGINGFACE_TOKEN=hf_...`) o usa el CLI directamente:

```bash
hf auth login
# pega el token cuando lo pida
```

Obtén el token en https://huggingface.co/settings/tokens (necesita permiso `write` para subir datasets).

## La API cambió y un comando del README no existe

LeRobot v0.5+ usa entry points instalados con pip (`lerobot-*`). Si ves tutoriales viejos con `python lerobot/scripts/control_robot.py …`, **están obsoletos**. La traducción aproximada:

| Viejo                                              | Nuevo               |
|----------------------------------------------------|---------------------|
| `python lerobot/scripts/control_robot.py …`        | `lerobot-teleoperate` / `lerobot-record` / `lerobot-replay` (según `--control.type`) |
| `python lerobot/scripts/train.py …`                | `lerobot-train`     |
| `huggingface-cli login`                            | `hf auth login`     |
