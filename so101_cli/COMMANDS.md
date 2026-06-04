# Cheatsheet — CLI `./cal`

Invocar con `./cal <subcomando>` desde la raíz del repo (no necesita activar el venv).

---

## follower move

Mueve el brazo follower a una pose o ángulos explícitos.

```bash
# Pose nombrada
./cal follower move --pose home
./cal follower move --pose zeros|rest|wave|open|close

# Ángulos explícitos (6 valores en grados: pan lift elbow wflex wroll gripper)
./cal follower move 0 -30 -60 0 0 0

# Listar poses disponibles
./cal follower move --list

# Modo interactivo (va a ceros y deja ajustar joint por joint con teclado)
./cal follower move --tune
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--hold-time N` | 3.0 s | Segundos que mantiene la pose antes de regresar a home |
| `--duration N` | 6.0 s | Tiempo para llegar a la pose (0 = instantáneo) |
| `--max-deg-per-s N` | 30 °/s | Velocidad angular máxima |
| `--rate N` | 50 Hz | Frecuencia de envío de waypoints |
| `--hold` | off | Mantiene torque activo al terminar (motores quedan rígidos) |

---

## follower replay

Reproduce un archivo `.json` grabado con el leader.

```bash
./cal follower replay paths/mi_trayectoria.json
./cal follower replay poses/wave.json
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--duration N` | 4.0 s | Segundos entre waypoints (solo para archivos `type: waypoints`) |
| `--hold-each N` | 1.0 s | Pausa en cada waypoint antes de continuar |
| `--max-deg-per-s N` | 30 °/s | Velocidad máxima |
| `--rate N` | 50 Hz | Hz de interpolación |
| `--no-return-home` | off | No regresar a home al terminar |

---

## leader record-waypoint

Graba poses estáticas: mueve el leader a mano y presiona `s` para capturar.

```bash
./cal leader record-waypoint paths/mi_ruta.json
./cal leader record-waypoint paths/mi_ruta.json --append   # agrega al final si ya existe
```

Teclas: `s` guardar pose · `q` terminar

---

## leader record-trajectory

Graba un movimiento continuo a N Hz.

```bash
./cal leader record-trajectory paths/mi_traj.json
./cal leader record-trajectory paths/mi_traj.json --rate 30
```

Teclas: `r` iniciar/parar grabación · `q` terminar y guardar

---

## teleop

Conecta leader → follower en vivo. Abre rerun automáticamente con cámaras y joints.

```bash
./cal teleop                           # solo visualización (nada se escribe a disco)
./cal teleop --record                  # graba trayectoria .json + .rrd a paths/teleop_<timestamp>
./cal teleop --record --out paths/demo # ruta de salida personalizada
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--rate N` | 30 Hz | Frecuencia del loop de control |
| `--record` | off | Graba la sesión a disco |
| `--out PATH` | auto | Ruta base para los archivos (sin extensión) |
| `--no-gripper` | off | No abrir la cámara OAK-D |
| `--no-external` | off | No abrir la cámara RealSense |
| `--external-index N` | auto | Forzar índice AVFoundation para la RealSense |

Teclas: `q` o `Ctrl-C` para salir

---

## record-dataset

Graba un dataset de demos en formato LeRobotDataset (envuelve `lerobot-record`).

```bash
./cal record-dataset --color red
./cal record-dataset --color blue --n 20
./cal record-dataset --color red --resume --repo-id armando/so101_clips
./cal record-dataset --color red --dry-run   # solo muestra el comando, no ejecuta
```

Flags:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--color COLOR` | **requerido** | Color del clip a quitar (e.g. `red`, `blue`) |
| `--n N` | 20 | Número de episodios |
| `--repo-id ID` | `armando/so101_clips` | HF repo id (formato `user/nombre`) |
| `--episode-time N` | 120 s | Techo máximo por episodio |
| `--reset-time N` | 60 s | Techo máximo de pausa entre episodios |
| `--fps N` | 30 | FPS de grabación |
| `--cam-index N` | 0 | Índice OpenCV de la cámara |
| `--no-push` | off | No subir a HF Hub al terminar |
| `--resume` | off | Reanudar un dataset existente |
| `--task "..."` | auto | Prompt explícito (default: `remove the <color> clip`) |

Control con teclado durante la grabación: `→` termina fase actual · `←` descarta episodio · `Esc` termina sesión

---

## record-batch  ← para el proyecto de cables caimán

Sesión estructurada de M batches de 3 episodios (negro / verde / rojo en orden aleatorio dentro de cada batch). Llama `lerobot-record` una vez por episodio con el task correcto.

```bash
# Sesión estándar: 10 batches = 30 episodios
./cal record-batch

# Batches configurables
./cal record-batch --batches 5          # 15 episodios (5 batches)
./cal record-batch --batches 20         # 60 episodios (20 batches)

# Ver el plan y el primer comando sin ejecutar nada
./cal record-batch --dry-run

# Continuar una sesión anterior (auto-detecta episodios ya grabados)
./cal record-batch --batches 20

# Subir a HF Hub al terminar
./cal record-batch --batches 10 --push
```

**Flujo por episodio:**
1. CLI muestra el color a recoger y espera ENTER
2. lerobot-record arranca con el task `"pick the <color> cable and place it in the <color> box"`
3. Controla la grabación: `→` terminar episodio · `←` descartar y rehacer · `Esc` abortar sesión
4. Al terminar los 3 del batch, CLI pide reset del environment y espera ENTER

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--batches N` | 10 | Número de batches de 3 (= N×3 episodios) |
| `--repo-id ID` | `armando/so101_terminal_sort` | HF repo id |
| `--episode-time N` | 120 s | Techo máximo por episodio |
| `--fps N` | 30 | FPS de grabación |
| `--no-lateral` | off | No grabar la cámara lateral (OAK-D) |
| `--front-index N` | 0 | Índice OpenCV de la cámara front |
| `--push` | off | Subir a HF Hub al terminar |
| `--dry-run` | off | Mostrar plan + primer comando, sin ejecutar |

---

## Ver un dataset grabado

```bash
source .venv/bin/activate
lerobot-dataset-viz --repo-id armando/so101_clips --episode-index 0
lerobot-dataset-viz --repo-id armando/so101_clips --episode-index 1
lerobot-dataset-viz --repo-id armando/so101_clips --episode-index 2
```

El viewer abre rerun con el video de la cámara `front` y las señales de `action`/`observation.state`.

---

## Joints (orden de los 6 valores posicionales)

```
1: shoulder_pan   2: shoulder_lift   3: elbow_flex
4: wrist_flex     5: wrist_roll      6: gripper
```

Ejemplo: `./cal follower move 0 -104 91 41 0 1` = pose `home`
