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

## `uv sync` falla con timeout a `download.pytorch.org`

LeRobot por default pinea torch al index `https://download.pytorch.org/whl/cu128` (CUDA 12.8). Algunas redes (campus, corporativas) bloquean ese host. Síntoma:

```
error: Request failed after 3 retries
  Caused by: Failed to fetch: `https://download.pytorch.org/whl/cu128/torch/`
  Caused by: operation timed out
```

**Fix:** comentar el pin en `../lerobot/pyproject.toml`. Buscar las líneas:

```toml
[tool.uv.sources]
torch = [{ index = "pytorch-cu128", marker = "sys_platform == 'linux'" }]
torchvision = [{ index = "pytorch-cu128", marker = "sys_platform == 'linux'" }]
```

y comentar las dos últimas (NO comentar la línea `[tool.uv.sources]`). Después:

```bash
uv sync
```

Esto instala torch desde PyPI estándar (trae el wheel CUDA 13 + nvidia-* deps; funciona con drivers NVIDIA recientes). Si quieres una variante CUDA específica después, ver el comando documentado en el comentario de LeRobot `pyproject.toml` (~línea 314).

`setup.sh` aplica este patch automáticamente si detecta el timeout — pero también puedes correrlo manualmente con:

```bash
sed -i.bak '/^\[tool\.uv\.sources\]$/,/^$/{s|^torch = \[{ index = "pytorch-cu128"|# &|; s|^torchvision = \[{ index = "pytorch-cu128"|# &|}' ../lerobot/pyproject.toml
```

## `CUDA initialization: forward compatibility was attempted on non supported HW`

Tu driver NVIDIA está desactualizado o desincronizado con la librería NVML del sistema (`nvidia-smi` también suele fallar con "Driver/library version mismatch"). Esto es **independiente de LeRobot** — significa que el módulo del kernel y los binarios userspace de NVIDIA no concuerdan.

```bash
# Diagnóstico
nvidia-smi          # si falla con version mismatch -> confirmado
cat /proc/driver/nvidia/version
dpkg -l | grep nvidia-driver
```

Soluciones (de menos a más agresiva):

1. **Reiniciar** la máquina — recarga el módulo del kernel a la versión correcta.
2. Recargar manualmente sin reiniciar (puede no funcionar si hay procesos usando la GPU):
   ```bash
   sudo rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia
   sudo modprobe nvidia
   ```
3. Reinstalar el driver:
   ```bash
   sudo apt install --reinstall nvidia-driver-580
   sudo reboot
   ```

Mientras el driver esté roto, `torch.cuda.is_available()` es `False`. Teleop / record / replay funcionan sin problema. Solo `lerobot-train` necesita GPU (sin GPU es viable pero MUY lento).

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
