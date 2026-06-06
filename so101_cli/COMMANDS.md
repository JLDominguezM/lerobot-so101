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
| `--no-lateral` | off | No abrir la cámara OAK-D (lateral) |
| `--no-front` | off | No abrir la cámara RealSense (front) |
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

## eval

Corre la policy entrenada en el robot real. **No necesita el brazo leader conectado.**

```bash
./cal eval --color red               # 1 rollout del cable rojo (sin grabar)
./cal eval --color black --n 3       # 3 rollouts del cable negro
./cal eval --color green --record    # corre + graba rollouts a dataset local
./cal eval --color red --dry-run     # muestra el comando, no ejecuta
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--policy ID` | `armandomm09/act_terminal_sort` | HF repo_id de la policy |
| `--n N` | 1 | Número de rollouts |
| `--duration N` | 60 s | Segundos máximos por rollout |
| `--fps N` | 30 | FPS del loop de control |
| `--no-lateral` | off | No usar la cámara OAK-D (lateral) |
| `--record` | off | Grabar rollouts al dataset local (estrategia sentry) |
| `--repo-id ID` | `<HF_USER>/eval_act_terminal_sort` | Dataset de log (solo con `--record`) |
| `--push` | off | Subir dataset a HF Hub al terminar (requiere `--record`) |
| `--dry-run` | off | Solo mostrar el comando generado |

---

## push-dataset

Sube el dataset local a HuggingFace Hub.

```bash
./cal push-dataset                           # sube armando/so101_terminal_sort
./cal push-dataset --repo-id armando/mi_ds   # repo_id explícito
./cal push-dataset --dry-run                 # muestra info sin subir nada
./cal push-dataset --private                 # sube como repositorio privado
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--repo-id ID` | `armando/so101_terminal_sort` | Dataset a subir |
| `--private` | off | Subir como repo privado en HF Hub |
| `--dry-run` | off | Muestra info del dataset sin subir nada |

---

## delete-batch

Borra los 3 episodios (negro/verde/rojo) de un batch completo del dataset local.

**Fórmula:** batch N (1-indexado) → episodios `(N-1)×3`, `(N-1)×3+1`, `(N-1)×3+2`

```bash
./cal delete-batch 21              # borra episodios 60, 61, 62
./cal delete-batch 5 --dry-run     # muestra qué borraría sin ejecutar
./cal delete-batch 21 --push       # borra y sube el dataset modificado a HF Hub
```

El dataset original queda respaldado automáticamente por `lerobot-edit-dataset` antes de modificar.

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--repo-id ID` | `armando/so101_terminal_sort` | Dataset a editar |
| `--push` | off | Subir a HF Hub al terminar |
| `--dry-run` | off | Mostrar plan sin borrar nada |

---

## eval-viz

Igual que `eval` pero abre rerun y muestra en tiempo real un heatmap de activaciones del backbone ResNet-18 por cámara. Útil para ver si el modelo está mirando el cable o el fondo.

Tres streams en rerun por cámara:
- `attention/<cam>/image` — imagen raw
- `attention/<cam>/attention` — heatmap (rojo = alta activación ResNet)
- `attention/<cam>/overlay` — mezcla 50/50

```bash
./cal eval-viz --color red
./cal eval-viz --color black --n 3 --fps 15
./cal eval-viz --color green --no-lateral
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--policy ID` | `armandomm09/act_terminal_sort` | HF repo_id de la policy |
| `--n N` | 1 | Número de episodios |
| `--duration N` | 60 s | Segundos máximos por episodio |
| `--fps N` | 15 | FPS del loop (más bajo = más margen CPU) |
| `--no-lateral` | off | No usar la cámara OAK-D |
| `--device STR` | `cpu` | Dispositivo torch (`cpu` o `cuda`) |

> **Nota técnica:** No es atención transformer — es la magnitud L2 de los canales de la última capa conv del ResNet-18. Es un proxy bueno de "dónde está reaccionando la CNN" antes de que el transformer mezcle los tokens.

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
