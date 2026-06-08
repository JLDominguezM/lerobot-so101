"""Subcomandos top-level: ./cal record-dataset  y  ./cal record-batch

record-dataset : sesión libre de N episodios con un solo color/tarea.
record-batch   : sesión estructurada de M batches de 3 episodios (negro/verde/rojo
                 en orden aleatorio), con pausa entre episodios y entre batches.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import load_arm_config


LEROBOT_CACHE = Path.home() / ".cache" / "huggingface" / "lerobot"

DEFAULT_REPO_ID       = "armando/so101_clips"
DEFAULT_TASK_TEMPLATE = "remove the {color} clip"

BATCH_COLORS     = ["black", "green", "red"]
BATCH_TASK       = "pick the {color} cable and place it in the {color} box"
BATCH_REPO_ID    = "armando/so101_terminal_sort"

# Etiquetas visuales para la terminal
_COLOR_LABEL = {
    "black": "NEGRO  [■■■]",
    "green": "VERDE  [GGG]",
    "red":   "ROJO   [RRR]",
}

_W = 54  # ancho del banner


def _set_terminal_title(title: str) -> None:
    """Cambia el título de la pestaña/ventana del terminal (ANSI OSC 0)."""
    print(f"\033]0;{title}\007", end="", flush=True)


def _print_color_banner(color: str, ep: int, total: int, batch: int, n_batches: int) -> None:
    label = _COLOR_LABEL[color]
    task  = BATCH_TASK.format(color=color)
    sep   = "=" * _W
    mid   = f"  CABLE A RECOGER: {label}"
    ep_ln = f"  Episodio {ep}/{total}  (batch {batch}/{n_batches})"
    tsk   = f"  \"{task}\""
    print(f"\n{sep}")
    print(ep_ln)
    print(sep)
    print(mid)
    print(tsk)
    print(sep, flush=True)
    _set_terminal_title(f"[EP {ep}/{total}] {label.strip()}")


def _reminder_thread(color: str, ep: int, total: int, batch: int, n_batches: int,
                     delay: float) -> threading.Thread:
    """Devuelve un thread (daemon) que imprime el banner del color tras `delay` segundos."""
    def _run():
        time.sleep(delay)
        print(f"\n{'·' * _W}")
        print(f"  RECORDATORIO — grabando ahora:")
        _print_color_banner(color, ep, total, batch, n_batches)
        print("  (→ terminar ep  /  ← descartar  /  Esc abortar sesión)\n", flush=True)
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _count_episodes(root: Path) -> int:
    info = root / "meta" / "info.json"
    if not info.exists():
        return 0
    try:
        return json.loads(info.read_text()).get("total_episodes", 0)
    except Exception:
        return 0


def _flush_stdin() -> None:
    """Descarta caracteres residuales en el buffer de stdin.

    Cuando lerobot-record termina, las flechas que el usuario presionó al final
    quedan en el buffer del terminal. Sin este flush, la siguiente llamada a
    input() las consume automáticamente (o se las pasa al próximo subprocess).
    """
    try:
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass  # no es una tty (tests, pipes), ignorar sin ruido


# Fragmentos que identifican ruido de librerías C/ObjC que van directo a stderr
# y no se pueden suprimir con Python logging.
_STDERR_NOISE = re.compile(
    r"objc\["                        # ObjC runtime: duplicate dylib warnings
    r"|AVFFrameReceiver"
    r"|AVFAudioReceiver"
    r"|^Svt\["                       # SVT-AV1 encoder info
    r"|resource_tracker"             # multiprocess ResourceTracker cleanup (macOS/py3.12)
    r"|_recursion_count"
    r"|ResourceTracker\.__del__"
    r"|leaked semaphore"
)


def _run_lerobot_filtered(cmd: list, env: dict) -> int:
    """Lanza lerobot-record y filtra el ruido de stderr conocido.

    stderr se lee en un thread aparte; las líneas que no coinciden con
    _STDERR_NOISE se reenvían a nuestro stderr (visible para el usuario).
    stdout queda conectado directamente al terminal (teclado/flechas funcionan).
    """
    proc = subprocess.Popen(cmd, env=env, stderr=subprocess.PIPE, text=True)

    def _drain():
        prev_suppressed = False
        for line in proc.stderr:
            suppress = bool(_STDERR_NOISE.search(line))
            # "Traceback (most recent call last):" es genérico; suprimirlo solo
            # cuando la línea anterior ya fue suprimida (es parte del mismo traceback).
            if not suppress and prev_suppressed and line.startswith("Traceback"):
                suppress = True
            prev_suppressed = suppress
            if not suppress:
                sys.stderr.write(line)
                sys.stderr.flush()

    t = threading.Thread(target=_drain, daemon=True)
    t.start()
    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
        raise
    t.join(timeout=3)
    return rc


def _build_lerobot_cmd(
    follower: dict,
    leader: dict,
    cameras: dict,
    repo_id: str,
    root: Path,
    task: str,
    fps: int,
    episode_time: float,
    reset_time: float,
    resume: bool,
    display_data: bool = True,
    play_sounds: bool = False,
) -> list[str]:
    """Construye el comando lerobot-record para UN episodio (--n 1).

    play_sounds=False (default) evita el TTS bloqueante de lerobot: el `finally`
    de cada episodio llama `log_say("Stop recording", blocking=True)`, que en
    macOS ejecuta `say` de forma síncrona y espera a que termine de hablar antes
    de continuar. Apagarlo acelera notablemente el corte entre episodios.
    """
    return [
        sys.executable, "-m", "so101_cli._record_entry",
        f"--robot.type={follower['type']}",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        f"--robot.cameras={json.dumps(cameras)}",
        f"--teleop.type={leader['type']}",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
        f"--dataset.repo_id={repo_id}",
        f"--dataset.root={root}",
        f"--dataset.single_task={task}",
        "--dataset.num_episodes=1",
        f"--dataset.fps={fps}",
        f"--dataset.episode_time_s={episode_time}",
        f"--dataset.reset_time_s={reset_time}",
        "--dataset.push_to_hub=false",
        f"--resume={'true' if resume else 'false'}",
        f"--display_data={'true' if display_data else 'false'}",
        f"--play_sounds={'true' if play_sounds else 'false'}",
    ]


def add_record_dataset_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record-dataset",
        help="Graba demos para entrenar VLA (envuelve lerobot-record).",
        description=(
            "Graba demos del leader+follower+cámara en formato LeRobotDataset. "
            "Usa los puertos/IDs de configs/{follower,leader}.yaml.\n\n"
            "Control manual con flechas (NO por tiempo):\n"
            "  →  termina la fase actual (reset O grabación) y pasa a la siguiente.\n"
            "  ←  descarta el episodio recién grabado y rehace.\n"
            "  Esc  termina la sesión completa.\n\n"
            "Los flags --episode-time y --reset-time son solo TECHOS de seguridad — "
            "por defecto están altos para que controles todo con →."
        ),
    )
    p.add_argument("--color", required=True,
                   help="Color del cable a quitar (ej. red, blue, green). "
                        "Se inserta en el prompt: 'remove the <color> clip'.")
    p.add_argument("--n", type=int, default=20,
                   help="Número de episodios a grabar (default 20).")
    p.add_argument("--episode-time", type=float, default=120.0,
                   help="Techo máx por episodio en segundos (default 120). "
                        "Termina antes presionando →.")
    p.add_argument("--reset-time", type=float, default=60.0,
                   help="Techo máx de la pausa entre episodios en segundos (default 60). "
                        "Sáltala presionando → cuando estés listo para grabar.")
    p.add_argument("--fps", type=int, default=30, help="FPS de grabación (default 30).")
    # Cámara 'front': RealSense por OpenCV/AVFoundation (la D435i color sale en
    # 640x480; pedir más rompe el frame, ver cameras.py).
    p.add_argument("--front-index", type=int, default=0,
                   help="Índice OpenCV de la cámara 'front' (RealSense) (default 0).")
    p.add_argument("--front-width", type=int, default=640)
    p.add_argument("--front-height", type=int, default=480)
    # Cámara 'lateral': OAK-D Pro vía DepthAI (no es UVC; va por nuestro tipo
    # de cámara 'depthai' registrado en el shim _record_entry).
    p.add_argument("--no-lateral", action="store_true",
                   help="No grabar la cámara lateral (OAK-D); deja solo 'front'.")
    p.add_argument("--lateral-width", type=int, default=640)
    p.add_argument("--lateral-height", type=int, default=480)
    p.add_argument("--lateral-mxid", default=None,
                   help="MxId de una OAK-D concreta si hay varias conectadas.")
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID,
                   help=f"Hugging Face dataset repo_id estilo 'user/dataset' "
                        f"(default {DEFAULT_REPO_ID}). NO uses rutas absolutas.")
    p.add_argument("--root", type=Path, default=None,
                   help="Carpeta local del dataset. Si omites, se deriva de --repo-id "
                        "como ~/.cache/huggingface/lerobot/<repo_id>. "
                        "OBLIGATORIO usar este path correcto cuando --resume.")
    p.add_argument("--task", default=None,
                   help="Prompt explícito. Si no se da, usa "
                        "'remove the <color> clip'.")
    p.add_argument("--no-push", action="store_true",
                   help="No subir el dataset a HF Hub al terminar.")
    p.add_argument("--resume", action="store_true",
                   help="Reanudar grabación sobre un dataset existente (mismo repo_id).")
    p.add_argument("--dry-run", action="store_true",
                   help="Imprime el comando lerobot-record que se ejecutaría y sale.")
    p.set_defaults(func=cmd_record_dataset)


def cmd_record_dataset(args: argparse.Namespace) -> int:
    follower = load_arm_config("follower")
    leader = load_arm_config("leader")
    task = args.task or DEFAULT_TASK_TEMPLATE.format(color=args.color)

    if "/" in args.repo_id and Path(args.repo_id).is_absolute():
        print(f"ERROR: --repo-id debe ser tipo 'usuario/nombre', no una ruta absoluta.")
        print(f"  Recibí: {args.repo_id!r}")
        print(f"  Si quieres reanudar un dataset que está en disco, dale el repo_id "
              f"(ej. 'armando/so101_clips_20260526_205109') y --resume.")
        return 2

    root = args.root if args.root is not None else (LEROBOT_CACHE / args.repo_id)

    if args.resume and not root.exists():
        print(f"ERROR: --resume pero no existe {root}")
        print(f"  Verifica el --repo-id o pasa --root con el path correcto.")
        return 2

    if not args.resume and root.exists():
        print(f"ERROR: ya existe un dataset en {root}")
        print(f"  - Para uno NUEVO: usa otro --repo-id (ej. {args.repo_id}_v2).")
        print(f"  - Para añadir episodios al existente: pasa --resume")
        print(f"    (OJO: --resume exige el MISMO esquema de cámaras; un dataset")
        print(f"     grabado solo con 'front' no acepta episodios con 'front'+'lateral').")
        return 2

    cameras = {
        "front": {
            "type": "opencv",
            "index_or_path": args.front_index,
            "width": args.front_width,
            "height": args.front_height,
            "fps": args.fps,
        }
    }
    if not args.no_lateral:
        cameras["lateral"] = {
            "type": "depthai",
            "width": args.lateral_width,
            "height": args.lateral_height,
            "fps": args.fps,
        }
        if args.lateral_mxid is not None:
            cameras["lateral"]["mxid"] = args.lateral_mxid

    cmd = [
        # Shim propio en vez de lerobot.scripts.lerobot_record: registra el tipo
        # de cámara 'depthai' (OAK-D) antes de que draccus parsee --robot.cameras.
        sys.executable, "-m", "so101_cli._record_entry",
        f"--robot.type={follower['type']}",
        f"--robot.port={follower['port']}",
        f"--robot.id={follower['id']}",
        f"--robot.cameras={json.dumps(cameras)}",
        f"--teleop.type={leader['type']}",
        f"--teleop.port={leader['port']}",
        f"--teleop.id={leader['id']}",
        f"--dataset.repo_id={args.repo_id}",
        f"--dataset.root={root}",
        f"--dataset.single_task={task}",
        f"--dataset.num_episodes={args.n}",
        f"--dataset.fps={args.fps}",
        f"--dataset.episode_time_s={args.episode_time}",
        f"--dataset.reset_time_s={args.reset_time}",
        f"--dataset.push_to_hub={'false' if args.no_push else 'true'}",
        f"--resume={'true' if args.resume else 'false'}",
        "--display_data=true",
    ]

    print("=== record-dataset ===")
    print(f"  color    : {args.color}")
    print(f"  prompt   : {task!r}")
    print(f"  episodios: {args.n}  ({args.episode_time}s cada uno)")
    print(f"  repo_id  : {args.repo_id}  (push={'no' if args.no_push else 'sí'})")
    print(f"  root     : {root}  (resume={'sí' if args.resume else 'no'})")
    print(f"  front    : opencv idx={args.front_index}  {args.front_width}x{args.front_height} @ {args.fps}fps")
    if args.no_lateral:
        print(f"  lateral  : (desactivada)")
    else:
        print(f"  lateral  : depthai (OAK-D)  {args.lateral_width}x{args.lateral_height} @ {args.fps}fps")
    print()
    print("Comando lerobot-record:")
    print("  " + " \\\n    ".join(cmd))
    print()

    if args.dry_run:
        return 0

    env = os.environ.copy()
    return subprocess.call(cmd, env=env)


# ---------------------------------------------------------------------------
# record-batch
# ---------------------------------------------------------------------------

def add_record_batch_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record-batch",
        help="Sesión estructurada: batches de 3 episodios (negro/verde/rojo en orden aleatorio).",
        description=(
            "Graba M batches de 3 episodios, uno por color (negro, verde, rojo).\n"
            "Dentro de cada batch el orden es aleatorio e independiente entre batches.\n\n"
            "Flujo por episodio:\n"
            "  1. CLI muestra el color que toca y espera ENTER.\n"
            "  2. lerobot-record abre con ese task (1 episodio).\n"
            "  3. Controla la grabación con → (terminar) / ← (descartar) / Esc (abortar todo).\n\n"
            "Al terminar los 3 del batch, el CLI pide resetear el environment\n"
            "antes de arrancar el siguiente batch.\n\n"
            "El dataset NO se sube a HF Hub automáticamente; usa `--push` para subir al final."
        ),
    )
    p.add_argument("--batches", type=int, default=10,
                   help="Número de batches de 3 episodios (default 10 = 30 episodios total).")
    p.add_argument("--repo-id", default=BATCH_REPO_ID,
                   help=f"HF dataset repo_id (default {BATCH_REPO_ID}).")
    p.add_argument("--root", type=Path, default=None,
                   help="Carpeta local del dataset. Default: ~/.cache/huggingface/lerobot/<repo_id>.")
    p.add_argument("--episode-time", type=float, default=120.0,
                   help="Techo máximo por episodio en segundos (default 120). Termina antes con →.")
    p.add_argument("--fps", type=int, default=30, help="FPS de grabación (default 30).")
    p.add_argument("--front-index", type=int, default=0,
                   help="Índice OpenCV de la cámara 'front' (RealSense) (default 0).")
    p.add_argument("--front-width", type=int, default=640)
    p.add_argument("--front-height", type=int, default=480)
    p.add_argument("--no-lateral", action="store_true",
                   help="No grabar la cámara lateral (OAK-D).")
    p.add_argument("--lateral-width", type=int, default=640)
    p.add_argument("--lateral-height", type=int, default=480)
    p.add_argument("--lateral-mxid", default=None,
                   help="MxId de una OAK-D concreta si hay varias conectadas.")
    p.add_argument("--push", action="store_true",
                   help="Subir el dataset a HF Hub al terminar la sesión completa.")
    p.add_argument("--sounds", action="store_true",
                   help="Reactiva el TTS de lerobot ('Stop recording', etc.). Por defecto "
                        "está APAGADO porque el 'Stop recording' es bloqueante (espera a que "
                        "el sistema termine de hablar) y alentiza el corte entre episodios.")
    p.add_argument("--dry-run", action="store_true",
                   help="Muestra el plan de batches y el primer comando; no ejecuta nada.")
    p.set_defaults(func=cmd_record_batch)


def cmd_record_batch(args: argparse.Namespace) -> int:
    follower = load_arm_config("follower")
    leader   = load_arm_config("leader")
    root     = args.root if args.root is not None else (LEROBOT_CACHE / args.repo_id)

    cameras: dict = {
        "front": {
            "type": "opencv",
            "index_or_path": args.front_index,
            "width": args.front_width,
            "height": args.front_height,
            "fps": args.fps,
        }
    }
    if not args.no_lateral:
        cameras["lateral"] = {
            "type": "depthai",
            "width": args.lateral_width,
            "height": args.lateral_height,
            "fps": args.fps,
        }
        if args.lateral_mxid is not None:
            cameras["lateral"]["mxid"] = args.lateral_mxid

    total_target  = args.batches * len(BATCH_COLORS)
    already_done  = _count_episodes(root)
    # Si hay episodios de una sesión anterior, avisamos y arrancamos desde ahí.
    # Los batches parciales anteriores quedan en el dataset; continuamos con batches nuevos.
    completed_batches  = already_done // len(BATCH_COLORS)
    orphaned_episodes  = already_done % len(BATCH_COLORS)

    sep = "=" * 60

    print(sep)
    print("  RECORD-BATCH — cables caimán (negro / verde / rojo)")
    print(sep)
    print(f"  batches        : {args.batches}  ({total_target} episodios totales)")
    print(f"  repo_id        : {args.repo_id}")
    print(f"  root           : {root}")
    print(f"  episodios ya grabados: {already_done}")
    if orphaned_episodes:
        print(f"  AVISO: {orphaned_episodes} episodio(s) de un batch incompleto en el dataset.")
        print(f"  Se arrancará un batch nuevo desde el episodio {already_done + 1}.")
    print(f"  front  : opencv idx={args.front_index}  {args.front_width}x{args.front_height} @ {args.fps}fps")
    if args.no_lateral:
        print(f"  lateral: (desactivada)")
    else:
        print(f"  lateral: depthai (OAK-D)  {args.lateral_width}x{args.lateral_height} @ {args.fps}fps")
    print(sep)

    if args.dry_run:
        print("\n--- Plan de batches (orden de ejemplo) ---")
        for b in range(min(3, args.batches)):
            order = random.sample(BATCH_COLORS, len(BATCH_COLORS))
            print(f"  Batch {b + 1}: {' → '.join(order)}")
        print("  ...")
        first_task = BATCH_TASK.format(color=BATCH_COLORS[0])
        first_cmd = _build_lerobot_cmd(
            follower, leader, cameras, args.repo_id, root,
            first_task, args.fps, args.episode_time, reset_time=5,
            resume=False, display_data=False, play_sounds=args.sounds,
        )
        print("\n--- Primer comando (ejemplo) ---")
        print("  " + " \\\n    ".join(first_cmd))
        return 0

    # Número de batch a partir del que arrancamos en esta sesión
    batch_start = completed_batches + (1 if orphaned_episodes else 0)
    batches_remaining = args.batches - batch_start

    if batches_remaining <= 0:
        print(f"\nYa hay {already_done} episodios grabados, lo que cubre los {args.batches} batches pedidos.")
        print("Usa --batches con un número mayor o un --repo-id distinto para continuar.")
        return 0

    print(f"\n  Batches restantes en esta sesión: {batches_remaining}")
    print(f"  Presiona ENTER para comenzar (o Ctrl-C para cancelar)...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 0

    global_ep = already_done  # índice 0-based del próximo episodio a grabar

    for batch_num in range(batch_start, batch_start + batches_remaining):
        order = random.sample(BATCH_COLORS, len(BATCH_COLORS))

        print(f"\n{sep}")
        print(f"  BATCH {batch_num + 1} / {args.batches}   "
              f"(episodios {global_ep + 1}–{global_ep + 3} de {total_target})")
        print(f"  Orden: {' → '.join(order)}")
        print(sep)

        for ep_in_batch, color in enumerate(order):
            global_ep += 1
            task  = BATCH_TASK.format(color=color)
            is_first_ever = (global_ep == 1 and not root.exists())

            # Flush stdin antes de mostrar el prompt: elimina flechas residuales
            # que lerobot-record dejó en el buffer del episodio anterior.
            _flush_stdin()

            _print_color_banner(color, global_ep, total_target, batch_num + 1, args.batches)
            print("  Prepara el cable y presiona ENTER cuando estés listo...", flush=True)
            try:
                input()
            except KeyboardInterrupt:
                print("\n\nInterrumpido por el usuario. El dataset queda en:", root)
                _set_terminal_title("cal record-batch — detenido")
                return 0

            # Flush de nuevo: descarta flechas/Esc que se hayan colado junto al Enter
            _flush_stdin()

            # Thread que recuerda el color ~12s después (cuando termina el init de hardware)
            _reminder_thread(color, global_ep, total_target, batch_num + 1, args.batches,
                             delay=12.0)

            env = os.environ.copy()
            env["SO101_QUIET"] = "1"  # silencia logging INFO de lerobot en el subproceso
            cmd = _build_lerobot_cmd(
                follower, leader, cameras, args.repo_id, root,
                task, args.fps, args.episode_time,
                reset_time=5,
                resume=(not is_first_ever),
                display_data=False,
                play_sounds=args.sounds,
            )

            try:
                rc = _run_lerobot_filtered(cmd, env)
            except KeyboardInterrupt:
                print("\n\nInterrumpido durante la grabación. El dataset queda en:", root)
                _set_terminal_title("cal record-batch — detenido")
                return 0

            if rc != 0:
                print(f"\nERROR: lerobot-record terminó con código {rc} (episodio {global_ep}).")
                print("El dataset queda en:", root)
                _set_terminal_title("cal record-batch — ERROR")
                return rc
            print(f"\n  Episodio {global_ep} guardado.")
            _set_terminal_title(f"cal record-batch — ep {global_ep}/{total_target} listo")

        # Fin de batch — pedir reset del environment (excepto si es el último batch)
        if batch_num < batch_start + batches_remaining - 1:
            _flush_stdin()
            print(f"\n{sep}")
            print(f"  FIN DEL BATCH {batch_num + 1}")
            print(f"  Pon los 3 cables de vuelta en posiciones DIFERENTES en las terminales.")
            print(f"  Presiona ENTER cuando el environment esté listo para el siguiente batch...")
            print(sep)
            try:
                input()
            except KeyboardInterrupt:
                print("\n\nInterrumpido. El dataset queda en:", root)
                return 0

    print(f"\n{sep}")
    print(f"  SESION COMPLETA: {global_ep} episodios en {root}")
    print(sep)

    if args.push:
        print("\nSubiendo dataset a HF Hub...")
        push_cmd = [
            sys.executable, "-c",
            f"from lerobot.common.datasets.lerobot_dataset import LeRobotDataset; "
            f"ds = LeRobotDataset('{args.repo_id}', root='{root}'); "
            f"ds.push_to_hub()"
        ]
        subprocess.call(push_cmd, env=os.environ.copy())

    return 0
