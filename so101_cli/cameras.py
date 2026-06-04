"""Camera utilities for the SO-101 setup (preview en vivo de `./cal teleop`).

Dos cámaras físicas con roles distintos y APIs muy distintas:

  - LateralCamera   : OAK-D Pro montada al lado (lateral). Habla el protocolo
                      DepthAI de Luxonis por USB (NO es UVC), así que nunca
                      aparece en AVFoundation / cv2.VideoCapture. Usa la API
                      de pipeline de depthai v3.

  - FrontCamera     : Intel RealSense como cámara frontal / tercera persona.
                      Expone varias interfaces UVC en macOS; elegimos sola la
                      de color (las de depth/IR dan la vista monocroma lado a
                      lado).

OJO: estas clases son SOLO para el preview de teleop (las logueamos a rerun).
La grabación del dataset NO las usa — va por `lerobot-record`, que abre la OAK-D
vía nuestro tipo de cámara `depthai` (so101_cli/depthaicamera.py) y la RealSense
vía su tipo `opencv`. Los nombres `front` / `lateral` coinciden a propósito con
las llaves de cámara del dataset.

Both classes implement the same minimal interface:

    cam.start()
    frame_bgr = cam.read()   # numpy ndarray (H, W, 3) BGR, or None
    cam.stop()

and support `with cam: ...`. Frames come back in OpenCV BGR convention
(what cv2.imshow expects). Convert to RGB before handing to viz.log_image.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import depthai as dai


# Names reported by macOS for RealSense UVC interfaces. The color stream's
# device name on Apple Silicon is usually something like
# "Intel(R) RealSense(TM) Depth Camera 435  RGB Camera" — we match loosely.
REALSENSE_NAME_HINTS = ("realsense", "intel(r) realsense", "d4", "RealSense(TM)", 'Intel(R) RealSense(TM) Depth Camera 435i Depth')
RGB_NAME_HINTS = ("rgb", "color")


# ---------------------------------------------------------------- Lateral

class LateralCamera:
    """OAK-D Pro montada al lado (lateral), vía depthai v3.

    Construye un nodo Camera en el socket CAM_A (sensor color de la OAK-D Pro),
    pide salida NV12 al tamaño/fps elegido y la expone como cola del host.
    `read()` es no bloqueante — devuelve el frame más reciente si hay uno listo,
    si no None, así el caller maneja el loop.
    """
    name = "lateral"

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self._pipeline: "dai.Pipeline | None" = None
        self._queue = None

    def start(self) -> None:
        # Lazy import — depthai is a heavy native dep and we don't want to
        # require it for code paths that only use the external camera.
        import depthai as dai

        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        output = cam.requestOutput(
            size=(self.width, self.height),
            type=dai.ImgFrame.Type.NV12,
            fps=self.fps,
        )
        # maxSize=1 + non-blocking: la cola guarda solo el frame más reciente y
        # descarta los viejos. Con el default (maxSize=16) los frames se
        # acumulan y read() devuelve el más viejo, así que el feed se atrasa
        # ~0.5 s y el retraso crece si el loop consume a menos de los fps.
        self._queue = output.createOutputQueue(maxSize=1, blocking=False)
        pipeline.start()
        self._pipeline = pipeline

    def read(self) -> np.ndarray | None:
        if self._queue is None:
            return None
        pkt = self._queue.tryGet()
        return pkt.getCvFrame() if pkt is not None else None

    def stop(self) -> None:
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
            self._queue = None

    def __enter__(self) -> "LateralCamera":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


# ----------------------------------------------------------------- Front

class FrontCamera:
    """RealSense color stream via AVFoundation.

    On macOS the RealSense advertises multiple UVC interfaces (depth, IR
    left, IR right, color). cv2.VideoCapture(0) usually picks the depth
    interface, which renders as a side-by-side grayscale view. We
    enumerate cameras via system_profiler, prefer the RealSense-named
    color one, and force MJPG (only the color interface advertises it).
    """
    name = "front"

    # La interfaz color de la RealSense D435i por UVC en macOS solo entrega
    # bien 640x480: al pedir resoluciones mayores AVFoundation reserva el
    # buffer grande pero el stream solo llena la parte de arriba y el resto
    # se queda congelado en el primer frame (imagen "rota" a la mitad).
    def __init__(self,
                 index: int | None = None,
                 width: int = 640,
                 height: int = 480) -> None:
        self.index = index           # None = auto-detect on start()
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        idx = self.index
        if idx is None:
            idx = _find_realsense_rgb_index(self.width, self.height)
            if idx is None:
                raise RuntimeError(
                    "Could not auto-detect RealSense RGB stream. "
                    "Pass index= explicitly (use realsense_rgb.py --list "
                    "to see what's enumerated)."
                )
        print("* "*5, idx)
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open AVFoundation camera at index {idx}")
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        # Drain a few warm-up frames so the first read() returns a real frame.
        for _ in range(5):
            cap.read()
        self._cap = cap
        self.index = idx

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "FrontCamera":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


# --------------------------------------------------------- Detect helpers

def list_av_cameras() -> list[tuple[int, str]]:
    """Return [(av_index, device_name)] from system_profiler.

    AVFoundation enumerates cameras in the same order system_profiler
    reports them, so the index here matches cv2.VideoCapture(index).
    """
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPCameraDataType", "-json"],
            text=True, timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    data = json.loads(out)
    return [(i, c.get("_name", f"camera_{i}"))
            for i, c in enumerate(data.get("SPCameraDataType", []))]


def _find_realsense_rgb_index(width: int, height: int) -> int | None:
    cams = list_av_cameras()
    realsense = [(i, n) for i, n in cams
                 if any(h in n.lower() for h in REALSENSE_NAME_HINTS)]
    print("* "*5," CAMS", cams)
    pool = realsense or cams

    by_name = next(
        (i for i, n in pool if any(h in n.lower() for h in RGB_NAME_HINTS)),
        None,
    )
    if by_name is not None:
        return by_name
    if len(realsense) >= 2:
        # No clear "RGB" in the name but the color one is conventionally
        # the second interface advertised.
        return realsense[1][0]
    # Fallback: probe each candidate index, keep the first that delivers
    # an actually-color (non-monochrome) frame at MJPG.
    candidates = [i for i, _ in cams] or list(range(5))
    for i in candidates:
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            continue
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        frame = None
        for _ in range(15):
            ok, frame = cap.read()
            if ok:
                break
        cap.release()
        if frame is not None and not _looks_grayscale(frame):
            return i
    return None


def _looks_grayscale(frame: np.ndarray) -> bool:
    b, g, r = cv2.split(frame)
    return cv2.absdiff(b, g).mean() < 1.5 and cv2.absdiff(g, r).mean() < 1.5
