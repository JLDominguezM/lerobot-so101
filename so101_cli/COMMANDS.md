# Cheatsheet — CLI `dume run`

Invocar con `dume run <subcomando>` (o `python -m so101_cli.dume run <subcomando>` sin
instalar). Es el modo CLI scriptable de DUM-E; `dume` a secas abre la TUI.

---

## follower move

Mueve el brazo follower a una pose o ángulos explícitos.

```bash
# Pose nombrada
dume run follower move --pose home
dume run follower move --pose zeros|rest|wave|open|close

# Ángulos explícitos (6 valores en grados: pan lift elbow wflex wroll gripper)
dume run follower move 0 -30 -60 0 0 0

# Listar poses disponibles
dume run follower move --list

# Modo interactivo (va a ceros y deja ajustar joint por joint con teclado)
dume run follower move --tune
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
dume run follower replay paths/mi_trayectoria.json
dume run follower replay poses/wave.json
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
dume run leader record-waypoint paths/mi_ruta.json
dume run leader record-waypoint paths/mi_ruta.json --append   # agrega al final si ya existe
```

Teclas: `s` guardar pose · `q` terminar

---

## leader record-trajectory

Graba un movimiento continuo a N Hz.

```bash
dume run leader record-trajectory paths/mi_traj.json
dume run leader record-trajectory paths/mi_traj.json --rate 30
```

Teclas: `r` iniciar/parar grabación · `q` terminar y guardar

---

## teleop

Conecta leader → follower en vivo. Abre rerun automáticamente con cámaras y joints.

```bash
dume run teleop                           # solo visualización (nada se escribe a disco)
dume run teleop --record                  # graba trayectoria .json + .rrd a paths/teleop_<timestamp>
dume run teleop --record --out paths/demo # ruta de salida personalizada
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

Teclas:
- `espacio` — pausa/reanuda. En pausa el follower **mantiene la pose** (torque activo, re-afirma el último goal); el leader queda libre para moverlo sin que el follower lo copie. Al reanudar, el follower vuelve **suavemente** a la pose actual del leader (ramp de ~0.6 s) para no saltar de golpe.
- `q` o `Ctrl-C` — salir

> En pausa no se graban muestras (si usas `--record`): así repositionas el leader sin meter esos frames al .json. Esto deja un hueco temporal en la trayectoria grabada, que en replay se ve como una pausa.

---

## record-dataset

Graba un dataset de demos en formato LeRobotDataset (envuelve `lerobot-record`).

```bash
dume run record-dataset --color red
dume run record-dataset --color blue --n 20
dume run record-dataset --color red --resume --repo-id armando/so101_clips
dume run record-dataset --color red --dry-run   # solo muestra el comando, no ejecuta
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
dume run record-batch

# Batches configurables
dume run record-batch --batches 5          # 15 episodios (5 batches)
dume run record-batch --batches 20         # 60 episodios (20 batches)

# Ver el plan y el primer comando sin ejecutar nada
dume run record-batch --dry-run

# Continuar una sesión anterior (auto-detecta episodios ya grabados)
dume run record-batch --batches 20

# Subir a HF Hub al terminar
dume run record-batch --batches 10 --push
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
| `--sounds` | off | Reactiva el TTS de lerobot. Por defecto APAGADO: el `"Stop recording"` de lerobot es **bloqueante** (espera a que macOS termine de decirlo en voz alta), lo que alentiza el corte entre episodios. |
| `--dry-run` | off | Mostrar plan + primer comando, sin ejecutar |

---

## eval

Corre la policy entrenada en el robot real. **No necesita el brazo leader conectado.**

```bash
dume run eval --color red                      # 1 rollout del cable rojo (sin grabar)
dume run eval --color black --n 3              # 3 rollouts del cable negro
dume run eval --color green --record          # corre + graba rollouts a dataset local
dume run eval --color red --n-action-steps 15 # más reactivo: re-observa más seguido
dume run eval --color red --dry-run           # muestra el comando, no ejecuta
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--policy ID` | `armandomm09/smolvla_terminal_sort` | HF repo_id de la policy |
| `--n N` | 1 | Número de rollouts |
| `--duration N` | 60 s | Segundos máximos por rollout |
| `--fps N` | 30 | FPS del loop de control |
| `--device STR` | `mps` | Dispositivo torch (`mps` en Mac, `cpu`, `cuda`) |
| `--online` | off (corre OFFLINE) | Permite peticiones a HF Hub. Ver nota abajo. |
| `--n-action-steps N` | (checkpoint=50) | Acciones del chunk a ejecutar antes de re-observar. Bajarlo (≈15) hace al robot más reactivo y le deja corregir el pick en vez de comprometerse al centro. No reentrena. |
| `--num-steps N` | (checkpoint=10) | Pasos de integración del flow-matching (solo SmolVLA). Subirlo (≈20) da acciones más nítidas. No reentrena. |
| `--no-lateral` | off | No usar la cámara OAK-D (lateral) |
| `--record` | off | Grabar rollouts al dataset local (estrategia sentry) |
| `--repo-id ID` | `<HF_USER>/eval_act_terminal_sort` | Dataset de log (solo con `--record`) |
| `--push` | off | Subir dataset a HF Hub al terminar (requiere `--record`); fuerza `--online` |
| `--dry-run` | off | Solo mostrar el comando generado |

> **Nota:** `--n-action-steps` y `--num-steps` son overrides del config del checkpoint que se aplican en inferencia (sin reentrenar). Bajar `n_action_steps` aumenta el cómputo (más forward passes); si el brazo no aguanta el FPS, súbelo o baja `--fps`.

> **OFFLINE por defecto:** `eval` corre con `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` para no tocar la red — así no crashea por DNS cuando el robot no tiene internet (`OSError: Can't load processor ...` / `Errno 8`). El modelo y el processor base de SmolVLA (`HuggingFaceTB/SmolVLM2-500M-Video-Instruct`) ya deben estar en el cache. Si entrenaste un checkpoint nuevo o aún no está cacheado, primero (con internet): `dume run pull model` y `dume run eval --color red --online` una vez para bajar lo que falte; después ya corre offline solo.

---

## push / pull / train  ← flujo Mac ↔ Spark

Mover datos y entrenar. El flujo típico es: grabas en la Mac → `push dataset` → en el Spark `pull dataset` + `train` → vuelves a la Mac → `eval` (que baja el modelo solo).

```bash
# Subir / bajar el DATASET
dume run push dataset                  # sube el dataset local grabado con record-batch
dume run push dataset --dry-run        # muestra info sin subir nada
dume run pull dataset                  # baja el dataset al cache local

# Subir / bajar el MODELO (train ya sube solo; eval ya baja solo — esto es manual)
dume run push model                    # sube outputs/train/<policy>/checkpoints/last/pretrained_model
dume run push model --path <carpeta>   # sube un checkpoint específico
dume run pull model                    # baja el checkpoint al cache de HF

# Entrenar
dume run train                         # SmolVLA sobre <HF_USER>/so101_terminal_sort, device cuda
dume run train --type act              # entrena ACT (sin language conditioning)
dume run train --device mps            # forzar Mac (LENTO para SmolVLA)
dume run train --dry-run               # muestra el comando lerobot-train, no ejecuta

# Fine-tuning: continuar desde un checkpoint en vez de entrenar desde cero
dume run train --finetune <HF_USER>/smolvla_terminal_sort \
            --dataset so101_terminal_sort_ext --steps 20000
```

**`dume run train`** (default) entrena `<HF_USER>/smolvla_terminal_sort` — el mismo repo que `eval` usa por defecto, así que después de entrenar puedes hacer `dume run eval --color red` directo.

Flags de `train`:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--dataset NAME` | `so101_terminal_sort` | Dataset (sin user): se usa `<HF_USER>/<dataset>` |
| `--policy NAME` | `smolvla_terminal_sort` / `act_terminal_sort` | Nombre del repo de salida (coincide con eval) |
| `--type {smolvla,act}` | `smolvla` | Tipo de policy. SmolVLA añade `load_vlm_weights=true` automáticamente |
| `--device STR` | `cuda` | `cuda` (Spark), `mps` (Mac, lento), `cpu` |
| `--steps N` | (config) | Pasos de entrenamiento (fine-tune: ~15000-25000 basta) |
| `--finetune CHECKPOINT` | off | Continúa desde un checkpoint (HF repo_id o carpeta). Se pasa como `--policy.path`; ignora `--type`/`load_vlm_weights` (los hereda). Sin `--policy`, la salida se nombra `<base>_ft` para no pisar el base |
| `--dry-run` | off | Solo mostrar el comando |

**Fine-tuning** (p.ej. tras cambiar el gripper): graba pocas demos nuevas a un dataset **fresco** (`record-batch --repo-id <HF_USER>/so101_terminal_sort_ext --push`) y reancla la policy partiendo del checkpoint actual en vez de re-entrenar desde cero. Es mucho más rápido y conserva las skills (color/place) que ya sabe. **No grabes sobre el dataset viejo** (`record-batch` por defecto apunta a `armando/so101_terminal_sort`): mezclaría demos del gripper viejo con el nuevo.

Flags de `push dataset` (mismos que el viejo `push-dataset`): `--hf-repo-id`, `--local-repo-id`, `--root`, `--private`, `--no-large`, `--dry-run`.

> **Datasets grandes:** `push dataset` usa `upload_large_folder` por defecto — sube en paralelo y **se reanuda** si se corta (vuelve a correr el mismo comando y continúa). El `upload_folder` clásico se atora con muchos GB/archivos; úsalo solo con `--no-large` si lo necesitas.
Flags de `push model`: `--path`, `--repo-id`, `--policy`, `--private`, `--dry-run`.
Flags de `pull dataset` / `pull model`: `--repo-id`.

---

## dataset-stats

Muestra el balance del dataset local: episodios y frames por color/tarea. Úsalo **antes de gastar una noche de entrenamiento** para confirmar que cada color está parejo.

```bash
dume run dataset-stats                                  # balance de armando/so101_terminal_sort
dume run dataset-stats --repo-id armando/mi_dataset     # otro dataset
dume run dataset-stats --root /ruta/al/dataset          # ruta explícita
```

Salida: tabla con episodios/frames/segundos por color, una barra de reparto, y un veredicto (✓ balanceado / ⚠ desbalanceado con cuántos episodios faltan para emparejar).

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--repo-id ID` | `armando/so101_terminal_sort` | Dataset local a inspeccionar |
| `--root PATH` | (deriva de `--repo-id`) | Ruta local exacta del dataset |

> **Nota:** la posición de la terminal **no** se graba en el dataset (solo el color va en el task string), así que el balance por terminal no se puede calcular aquí — eso depende de tu protocolo de grabación (`record-batch` pide poner los cables en terminales distintas entre batches).

---

## delete-batch

Borra los 3 episodios (negro/verde/rojo) de un batch completo del dataset local.

**Fórmula:** batch N (1-indexado) → episodios `(N-1)×3`, `(N-1)×3+1`, `(N-1)×3+2`

```bash
dume run delete-batch 21              # borra episodios 60, 61, 62
dume run delete-batch 5 --dry-run     # muestra qué borraría sin ejecutar
dume run delete-batch 21 --push       # borra y sube el dataset modificado a HF Hub
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

Igual que `eval` pero abre rerun para visualizar la policy en vivo. El tipo de policy se **detecta automáticamente** del `config.json` del checkpoint:

- **ACT (ResNet-18):** muestra un heatmap de activaciones por cámara (rojo = alta activación). Útil para ver si el modelo mira el cable o el fondo.
  - `attention/<cam>/image` — imagen raw
  - `attention/<cam>/attention` — heatmap
  - `attention/<cam>/overlay` — mezcla 50/50
- **SmolVLA (SigLIP + transformer):** el heatmap ResNet **no aplica** a esta arquitectura, así que solo se muestran los streams de cámara crudos (`cameras/<cam>`) mientras la policy corre. Sigue siendo útil para ver qué ven las cámaras en el momento de decidir el pick.

```bash
dume run eval-viz --color red
dume run eval-viz --color black --n 3 --fps 15
dume run eval-viz --color green --no-lateral
dume run eval-viz --color red --n-action-steps 15   # más reactivo (SmolVLA)
```

Flags opcionales:

| Flag | Default | Descripción |
|------|---------|-------------|
| `--policy ID` | `armandomm09/smolvla_terminal_sort` | HF repo_id de la policy |
| `--n N` | 1 | Número de episodios |
| `--duration N` | 60 s | Segundos máximos por episodio |
| `--fps N` | 15 | FPS del loop (más bajo = más margen CPU) |
| `--no-lateral` | off | No usar la cámara OAK-D |
| `--device STR` | `cpu` | Dispositivo torch (`cpu`, `mps`, `cuda`) |
| `--online` | off (corre OFFLINE) | Permite peticiones a HF Hub. Por defecto offline (solo cache), igual que `eval`. |
| `--n-action-steps N` | (checkpoint=50) | Acciones del chunk antes de re-observar. Bajarlo = más reactivo. No reentrena. |
| `--num-steps N` | (checkpoint=10) | Pasos de flow-matching (solo SmolVLA). Subirlo = acciones más nítidas. No reentrena. |

> **Nota técnica (ACT):** el heatmap no es atención transformer — es la magnitud L2 de los canales de la última capa conv del ResNet-18. Es un proxy de "dónde reacciona la CNN". Para SmolVLA no existe equivalente directo aquí; ver la atención del transformer requeriría un extractor específico.

---

## Diagnóstico / setup de hardware

Comandos que NO mueven el brazo: solo identifican puertos, configuran motores o
verifican que todo esté conectado. Útiles antes de teleoperar, grabar o entrenar.
Son ports a nivel CLI de los scripts sueltos en `scripts/`.

```bash
# Identificar qué puerto USB es cada brazo (interactivo: desconecta un USB a la vez)
dume run find-ports

# Asignar IDs 1..6 a los motores de un brazo recién armado (interactivo, uno a la vez)
dume run setup-motors follower
dume run setup-motors leader

# Reconfigurar UN solo motor (recovery: si setup-motors crasheó a la mitad)
dume run setup-motors follower --motor gripper

# Ping al bus de un brazo: ver qué motor IDs (1..6) responden
dume run scan-bus follower
dume run scan-bus leader

# Chequeo integral: pinga ambos brazos y abre ambas cámaras un instante
dume run check
dume run check --no-leader          # solo follower + cámaras (p.ej. en eval, sin leader)
dume run check --no-lateral         # salta la OAK-D (si no está montada)
```

`check` imprime un resumen con ✓/✗ por componente (follower, leader, front, lateral)
y **termina con código ≠ 0 si algo no responde** — sirve como gate en scripts.

| Comando | Default | Descripción |
|---------|---------|-------------|
| `find-ports` | — | Envuelve `lerobot-find-port`. Anota los puertos en `configs/{follower,leader}.yaml`. |
| `setup-motors W` | los 6 | Envuelve `lerobot-setup-motors` para el brazo `W`. |
| `setup-motors W --motor N` | — | Configura solo el motor `N` (nombre de joint). |
| `scan-bus W` | — | `broadcast_ping`; reporta presentes, faltantes e inesperados. |
| `check` | todo | `--no-leader`, `--no-front`, `--no-lateral` para saltar componentes. |

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

Ejemplo: `dume run follower move 0 -104 91 41 0 1` = pose `home`
