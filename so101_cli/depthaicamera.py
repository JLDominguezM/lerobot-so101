"""Cámara OAK-D Pro como cámara nativa de LeRobot (tipo `depthai`).

La OAK-D NO es un dispositivo UVC: habla el protocolo DepthAI de Luxonis por
USB, así que `lerobot-record` no la ve con sus tipos `opencv` / `intelrealsense`.
Aquí la envolvemos en el interfaz `Camera` de LeRobot para que el robot la lea
dentro de su `get_observation()` igual que cualquier otra cámara — con eso queda
sincronizada en el tiempo con los motores y la RealSense por el mismo loop de
grabación (no inventamos sincronización aparte).

Registro / descubrimiento:
  - `DepthAICameraConfig` se registra como subclase `"depthai"` de `CameraConfig`,
    así draccus puede parsear `--robot.cameras='{lateral:{type:depthai,...}}'`.
  - El nombre del módulo (`depthaicamera`) y el de la clase (`DepthAICamera`) están
    elegidos a propósito para que `make_device_from_device_class` de LeRobot
    localice la clase sin que haya que tocar el código vendorizado.

OJO: este módulo importa `depthai`, que es pesado. NO lo importes desde
`so101_cli/__init__.py`; solo se carga por la ruta de grabación (vía el shim
`so101_cli._record_entry`).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import CameraConfig, ColorMode


@CameraConfig.register_subclass("depthai")
@dataclass
class DepthAICameraConfig(CameraConfig):
    """Config de una OAK-D vía DepthAI.

    fps / width / height se heredan de CameraConfig. width/height definen el
    tamaño del frame que el sensor entrega (y por tanto la forma que el dataset
    registra para esta cámara). `mxid` permite fijar un dispositivo concreto si
    hay varias OAK conectadas.
    """

    mxid: str | None = None
    color_mode: ColorMode = ColorMode.RGB

    def __post_init__(self) -> None:
        self.color_mode = ColorMode(self.color_mode)
        if self.fps is None or self.width is None or self.height is None:
            raise ValueError(
                "DepthAICameraConfig requiere fps, width y height explícitos "
                f"(recibí fps={self.fps}, width={self.width}, height={self.height})."
            )


class DepthAICamera(Camera):
    """OAK-D Pro (socket CAM_A, sensor color) como cámara de LeRobot.

    Un hilo en background drena continuamente la cola del dispositivo (maxSize=1,
    no bloqueante, así siempre es el frame más reciente) y guarda el último frame
    listo. Los lectores (`read` / `async_read` / `read_latest`) devuelven ese
    frame sin acumular latencia.
    """

    def __init__(self, config: DepthAICameraConfig):
        super().__init__(config)
        self.config = config
        self.mxid = config.mxid
        self.color_mode = config.color_mode
        self.fps = int(config.fps)
        self.width = int(config.width)
        self.height = int(config.height)

        self._pipeline: Any = None
        self._queue: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._latest: NDArray[Any] | None = None
        self._latest_t: float = 0.0
        self._new_frame = threading.Event()

    # ----------------------------------------------------------- interfaz

    @property
    def is_connected(self) -> bool:
        return self._pipeline is not None and self._thread is not None and self._thread.is_alive()

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        import depthai as dai

        out: list[dict[str, Any]] = []
        for d in dai.Device.getAllAvailableDevices():
            out.append({"type": "depthai", "id": d.getMxId(), "name": d.name, "state": d.state.name})
        return out

    def connect(self, warmup: bool = True) -> None:
        if self.is_connected:
            raise RuntimeError(f"{self} ya está conectada.")

        import depthai as dai

        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        output = cam.requestOutput(
            size=(self.width, self.height),
            type=dai.ImgFrame.Type.NV12,
            fps=self.fps,
        )
        # maxSize=1 + no bloqueante: la cola guarda solo el frame más reciente.
        self._queue = output.createOutputQueue(maxSize=1, blocking=False)
        pipeline.start()
        self._pipeline = pipeline

        self._stop.clear()
        self._new_frame.clear()
        self._thread = threading.Thread(target=self._loop, name="depthai-read", daemon=True)
        self._thread.start()

        if warmup:
            self._wait_first_frame(timeout_s=5.0)

    def _wait_first_frame(self, timeout_s: float) -> None:
        deadline = time.perf_counter() + timeout_s
        while time.perf_counter() < deadline:
            with self._lock:
                if self._latest is not None:
                    return
            time.sleep(0.01)
        raise TimeoutError(f"{self}: no llegó ningún frame en {timeout_s:.0f}s tras connect().")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                pkt = self._queue.tryGet()
            except Exception:
                break
            if pkt is None:
                time.sleep(0.001)
                continue
            frame = self._to_output(pkt.getCvFrame())
            with self._lock:
                self._latest = frame
                self._latest_t = time.perf_counter()
            self._new_frame.set()

    def _to_output(self, frame_bgr: NDArray[Any]) -> NDArray[Any]:
        # getCvFrame() de un NV12 devuelve BGR. Ajustamos tamaño y color al
        # contrato de LeRobot (por defecto RGB, forma exacta (H, W, 3)).
        if frame_bgr.shape[1] != self.width or frame_bgr.shape[0] != self.height:
            frame_bgr = cv2.resize(frame_bgr, (self.width, self.height), interpolation=cv2.INTER_AREA)
        if self.color_mode == ColorMode.RGB:
            return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return frame_bgr

    def read(self) -> NDArray[Any]:
        """Bloquea hasta tener un frame y devuelve el más reciente."""
        return self.async_read()

    def async_read(self, timeout_ms: float = 200) -> NDArray[Any]:
        """Devuelve el último frame nuevo, esperando hasta timeout_ms si hace falta."""
        if not self.is_connected:
            raise RuntimeError(f"{self} no está conectada.")
        if not self._new_frame.wait(timeout=timeout_ms / 1000.0):
            raise TimeoutError(f"{self}: sin frame nuevo en {timeout_ms:.0f}ms.")
        with self._lock:
            self._new_frame.clear()
            assert self._latest is not None
            return self._latest.copy()

    def read_latest(self, max_age_ms: int = 500) -> NDArray[Any]:
        """Devuelve el último frame en buffer sin bloquear (lo que usa el robot)."""
        if not self.is_connected:
            raise RuntimeError(f"{self} no está conectada.")
        with self._lock:
            if self._latest is None:
                raise RuntimeError(f"{self}: aún no hay ningún frame capturado.")
            age_ms = (time.perf_counter() - self._latest_t) * 1e3
            if age_ms > max_age_ms:
                raise TimeoutError(f"{self}: el último frame tiene {age_ms:.0f}ms (>{max_age_ms}ms).")
            return self._latest.copy()

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
            self._queue = None
        with self._lock:
            self._latest = None

    def __str__(self) -> str:
        tag = self.mxid or "auto"
        return f"DepthAICamera({tag}, {self.width}x{self.height}@{self.fps})"
