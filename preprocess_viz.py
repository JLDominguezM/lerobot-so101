"""Compara visualmente preprocesamientos de imagen para resaltar cables vs legos.

Toma UN frame (de tu dataset, de un archivo, o de la cámara en vivo) y arma una
rejilla lado a lado: original + cada transformación de `so101_cli/preprocess.py`.
Guarda un PNG (y en macOS lo abre solo). Sirve para decidir, ANTES de re-entrenar,
si algún preprocesamiento separa de verdad el cable de los legos.

  ⚠️  Recuerda: el modelo se entrenó con imágenes crudas. Aplicar esto solo en
      eval rompe el modelo. Si una transformación te convence, hay que aplicarla
      al dataset y re-entrenar. Esto es solo el experimento previo.

Fuentes (--source):
  dataset  (default) → saca un frame del mp4 del dataset, sin tocar el robot.
  image              → un PNG/JPG cualquiera (--image ruta.png).
  camera             → captura en vivo de la cámara (--camera front|lateral).

Ejemplos:
  # frame 300 de la cámara frontal del dataset, resaltando el cable rojo:
  python preprocess_viz.py --color red --frame 300

  # cámara lateral (OAK-D), cable verde:
  python preprocess_viz.py --camera lateral --color green --frame 500

  # un PNG suelto:
  python preprocess_viz.py --source image --image mi_imagen.png --color black

  # captura en vivo (robot/cámara conectada):
  python preprocess_viz.py --source camera --camera front --color red
"""

from __future__ import annotations

import argparse
import functools
import glob
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from so101_cli import preprocess as pp

LEROBOT_CACHE = Path.home() / ".cache" / "huggingface" / "lerobot"


# --------------------------------------------------------------- fuentes

def frame_from_video(path: Path, idx: int) -> np.ndarray:
    """Decodifica el frame `idx` de un mp4 con pyav (backend que sí funciona acá)."""
    import av  # pyav; ver nota de torchcodec en view_dataset.py

    container = av.open(str(path))
    stream = container.streams.video[0]
    try:
        for i, frame in enumerate(container.decode(stream)):
            if i == idx:
                return frame.to_ndarray(format="bgr24")
    finally:
        container.close()
    raise IndexError(f"El video {path.name} no llega al frame {idx} "
                     f"(prueba un --frame más chico).")


def frame_from_dataset(repo_id: str, camera: str, idx: int) -> np.ndarray:
    base = LEROBOT_CACHE / repo_id / "videos" / f"observation.images.{camera}"
    mp4s = sorted(glob.glob(str(base / "**" / "*.mp4"), recursive=True))
    if not mp4s:
        sys.exit(f"No encontré videos en {base}\n"
                 f"¿Está el dataset en cache? Revisa `./cal dataset-stats`.")
    return frame_from_video(Path(mp4s[0]), idx)


def frame_from_camera(camera: str, front_index: int | None) -> np.ndarray:
    from so101_cli.cameras import FrontCamera, LateralCamera

    cam = (LateralCamera(width=640, height=480) if camera == "lateral"
           else FrontCamera(index=front_index))
    with cam:
        frame = None
        for _ in range(60):  # da unos intentos al feed (OAK-D es no-bloqueante)
            frame = cam.read()
            if frame is not None:
                break
    if frame is None:
        sys.exit(f"La cámara '{camera}' no entregó frame.")
    return frame


# ----------------------------------------------------------------- rejilla

def label(img: np.ndarray, text: str) -> np.ndarray:
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 28), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 20), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def grid(panels: list[np.ndarray], cols: int = 3) -> np.ndarray:
    blank = np.zeros_like(panels[0])
    rows = []
    for i in range(0, len(panels), cols):
        chunk = panels[i:i + cols]
        chunk += [blank] * (cols - len(chunk))
        rows.append(np.hstack(chunk))
    return np.vstack(rows)


# -------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--source", choices=["dataset", "image", "camera"],
                    default="dataset", help="De dónde sacar el frame (default dataset).")
    ap.add_argument("--repo-id", default="armando/so101_terminal_sort",
                    help="Dataset para --source dataset.")
    ap.add_argument("--camera", choices=["front", "lateral"], default="front",
                    help="Qué cámara (dataset o live). Default front.")
    ap.add_argument("--frame", type=int, default=300,
                    help="Índice de frame para --source dataset (default 300).")
    ap.add_argument("--image", type=Path, default=None,
                    help="Ruta de imagen para --source image.")
    ap.add_argument("--color", choices=["red", "green", "black"], default="red",
                    help="Color de cable a resaltar (default red).")
    ap.add_argument("--front-index", type=int, default=None,
                    help="Índice OpenCV de la RealSense para --source camera.")
    ap.add_argument("--out", type=Path, default=None,
                    help="PNG de salida (default outputs/preprocess_<color>_<camera>.png).")
    ap.add_argument("--show", action="store_true",
                    help="Además, abre una ventana cv2 (requiere GUI).")
    ap.add_argument("--no-open", action="store_true",
                    help="No abrir el PNG automáticamente (macOS `open`).")
    args = ap.parse_args()

    # 1) conseguir el frame base
    if args.source == "image":
        if not args.image or not args.image.exists():
            sys.exit("--source image necesita --image <ruta válida>.")
        frame = cv2.imread(str(args.image))
        if frame is None:
            sys.exit(f"No pude leer {args.image}.")
        src_desc = str(args.image)
    elif args.source == "camera":
        frame = frame_from_camera(args.camera, args.front_index)
        src_desc = f"camera:{args.camera} (live)"
    else:
        frame = frame_from_dataset(args.repo_id, args.camera, args.frame)
        src_desc = f"{args.repo_id} {args.camera} frame#{args.frame}"

    print(f"Frame base: {src_desc}  shape={frame.shape}  color={args.color}")

    # 2) aplicar cada transformación
    panels = [label(frame, "original")]
    for name, fn in pp.TRANSFORMS.items():
        # las que necesitan color se fijan con partial; enhance no lo usa.
        try:
            out = fn(frame, args.color)
        except TypeError:
            out = fn(frame)
        panels.append(label(out, f"{name} [{args.color}]"))

    board = grid(panels, cols=3)

    # 3) guardar (+ opcionalmente mostrar/abrir)
    out_path = args.out or Path("outputs") / f"preprocess_{args.color}_{args.camera}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), board)
    print(f"Guardado: {out_path}  ({board.shape[1]}x{board.shape[0]})")

    if args.show:
        cv2.imshow("preprocess", board)
        print("Cierra la ventana o presiona una tecla para salir.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    elif not args.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(out_path)], check=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
