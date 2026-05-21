# SO-101 con LeRobot

Repositorio de operación del brazo robótico **SO-101** (leader + follower) usando exclusivamente el framework [LeRobot](https://github.com/huggingface/lerobot) de Hugging Face. Sin ROS2.

## Hardware

- **Follower** (5 joints + gripper, 6 DOF): 6× Feetech STS3215 con reducción 1/345.
- **Leader** (manija de teleoperación, misma geometría): 6× STS3215 con engranajes mixtos (1/191, 1/345, 1/147 según joint) para que se mueva con poca fuerza.
- 2× adaptadores USB-to-TTL Waveshare → dos `/dev/ttyACM*` en Linux.

Más detalles y guía de armado: [docs/armado.md](docs/armado.md).

## Estructura

```
so101/
├── setup.sh              # bootstrap: uv + clone lerobot + uv sync
├── pyproject.toml        # define lerobot como path source editable
├── configs/              # puerto e id de cada brazo
├── calibrations/         # JSONs de calibración versionados
├── scripts/              # wrappers numerados sobre lerobot-* CLIs
├── udev/                 # reglas para puertos estables /dev/so101_*
├── src/                  # código propio del proyecto (vacío inicialmente)
└── docs/                 # armado, calibración, troubleshooting
```

El clone editable de LeRobot vive como hermano: `../lerobot/`.

## Quickstart

### 1. Bootstrap

```bash
bash setup.sh
source .venv/bin/activate
cp .env.example .env  # rellena HUGGINGFACE_TOKEN y HF_USER
```

`setup.sh` instala `uv`, asegura Python 3.12, clona LeRobot en `../lerobot/`, y resuelve dependencias.

### 2. Permisos USB

Solo una vez:

```bash
sudo usermod -aG dialout $USER
# cerrar sesión y volver a entrar
```

### 3. Detectar puertos

```bash
bash scripts/00_find_ports.sh
```

Anota cuál puerto es follower y cuál leader, y edita `configs/follower.yaml` y `configs/leader.yaml`.

### 4. (Opcional) Puertos estables

Edita `udev/99-so101.rules` con los seriales de tus adaptadores (instrucciones dentro del archivo), luego:

```bash
sudo cp udev/99-so101.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Ahora los YAMLs pueden usar `/dev/so101_follower` y `/dev/so101_leader` directamente.

### 5. Asignar IDs a motores (una vez por brazo)

```bash
bash scripts/01_setup_motors.sh follower
bash scripts/01_setup_motors.sh leader
```

### 6. Calibrar

```bash
bash scripts/02_calibrate.sh both
```

Ver [docs/calibracion.md](docs/calibracion.md).

### 7. Teleoperar

```bash
bash scripts/03_teleoperate.sh
```

### 8. Grabar dataset → entrenar policy → evaluar

```bash
# Grabar 10 episodios y subirlos al HF Hub
bash scripts/05_record.sh "Pick the red cube" 10 pick_red_cube

# Reproducir un episodio (verificar calidad)
bash scripts/06_replay.sh pick_red_cube 0

# Entrenar ACT (requiere GPU)
bash scripts/07_train_act.sh pick_red_cube

# Evaluar policy en el robot real
bash scripts/08_eval.sh act_pick_red_cube "Pick the red cube" 5
```

## ¿Qué NO hace este repo?

- **No usa ROS2.** Decisión deliberada — LeRobot ya cubre teleop, recording, training y eval, y meter ROS2 implicaría re-implementar drivers que ya existen.
- **No integra cámaras todavía.** Cuando se necesiten, se añade un `configs/cameras.yaml` y los scripts ganan el flag `--robot.cameras=...`. El framework soporta OpenCV y RealSense nativamente.
- **No incluye CI ni tests.** Es un repo de operación de hardware; los tests reales son ejecuciones físicas.

## Recursos

- Repo LeRobot: https://github.com/huggingface/lerobot
- Docs oficial SO-101: https://huggingface.co/docs/lerobot/so101
- Tutorial end-to-end: https://huggingface.co/docs/lerobot/il_robots
- Hardware/CAD/BOM: https://github.com/TheRobotStudio/SO-ARM100
