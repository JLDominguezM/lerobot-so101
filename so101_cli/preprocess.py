"""Preprocesamiento de imagen para resaltar los cables y atenuar los legos.

IMPORTANTE — léelo antes de usar esto en el robot:
  El modelo SmolVLA se entrenó con las imágenes CRUDAS de las cámaras. Si
  aplicas cualquiera de estas transformaciones SOLO en inferencia (eval),
  creas un desajuste train/inferencia y el modelo EMPEORA, no mejora. Para
  que ayuden de verdad hay que aplicar la MISMA transformación al dataset y
  re-entrenar. Este módulo existe para experimentar y decidir si vale la pena
  ese re-entrenamiento (ver `preprocess_viz.py`).

  Además: el encoder visual de SmolVLA es un VLM preentrenado (SmolVLM2) que
  espera imágenes de aspecto natural. Las transformaciones "suaves" (`enhance`,
  `color_pop`) son más seguras para re-entrenar que las máscaras duras
  (`cable_mask`), que producen imágenes poco naturales y pueden confundir al
  encoder.

Convención: todas las funciones reciben y devuelven imágenes BGR uint8
(H, W, 3), igual que OpenCV / cv2.imshow.
"""

from __future__ import annotations

import cv2
import numpy as np

# Rangos HSV (OpenCV: H 0..180, S/V 0..255) por color de cable.
#   - red vive a ambos lados del wrap de H (cerca de 0 y de 180).
#   - green es un rango central de H.
#   - black no tiene tono útil: se aísla por V baja (oscuro), sin importar H.
# Ajusta estos rangos con `preprocess_viz.py` mirando tus frames reales.
COLOR_HSV: dict[str, list[tuple[tuple[int, int, int], tuple[int, int, int]]]] = {
    "red":   [((0, 90, 60), (10, 255, 255)), ((170, 90, 60), (180, 255, 255))],
    "green": [((35, 60, 40), (85, 255, 255))],
    "black": [((0, 0, 0), (180, 120, 55))],
}


def target_mask(bgr: np.ndarray, color: str) -> np.ndarray:
    """Máscara binaria (0/255) de los píxeles del color objetivo.

    Une los rangos HSV del color y limpia ruido con apertura+cierre
    morfológicos (quita motas, rellena huecos del cable).
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in COLOR_HSV[color]:
        mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    return mask


def keep_elongated(mask: np.ndarray,
                   min_area: int = 80,
                   min_aspect: float = 2.2) -> np.ndarray:
    """Conserva solo los blobs alargados de la máscara.

    Los cables son finos y largos; los legos son compactos. Filtrando por
    relación de aspecto del bounding box (largo/ancho) descartamos legos del
    mismo color que el cable, que el filtro por color solo no separa.
    """
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = np.zeros_like(mask)
    for i in range(1, n):  # 0 = fondo
        x, y, w, h, area = stats[i]
        if area < min_area:
            continue
        aspect = max(w, h) / max(1, min(w, h))
        if aspect < min_aspect:
            continue
        out[lbl == i] = 255
    return out


def enhance(bgr: np.ndarray) -> np.ndarray:
    """Realce suave, amigable con el VLM: CLAHE en L + boost de saturación.

    No segmenta nada; solo sube contraste local y viveza de color para que
    el cable resalte sin volver la imagen poco natural. Es la opción más
    segura para re-entrenar.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.4, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def color_pop(bgr: np.ndarray, color: str) -> np.ndarray:
    """Mantiene a todo color los píxeles del cable; el resto a gris atenuado.

    El cable conserva su color natural y todo lo demás (legos incluidos) se
    vuelve gris oscuro. La imagen sigue siendo "natural" (sin bordes duros),
    así que es razonable re-entrenar con ella.
    """
    mask = target_mask(bgr, color).astype(bool)
    gray = cv2.cvtColor(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    out = (gray * 0.55).astype(np.uint8)
    out[mask] = bgr[mask]
    return out


def cable_mask(bgr: np.ndarray, color: str) -> np.ndarray:
    """Visualización 3-canal de la máscara dura (blanco = cable detectado)."""
    return cv2.cvtColor(target_mask(bgr, color), cv2.COLOR_GRAY2BGR)


def cable_overlay(bgr: np.ndarray, color: str) -> np.ndarray:
    """Original atenuada con el cable (blobs alargados) resaltado y contorneado.

    Es la mejor vista para *diagnosticar*: ves qué considera "cable" el
    pipeline (color + forma alargada) sobre la escena real.
    """
    mask = keep_elongated(target_mask(bgr, color))
    m = mask.astype(bool)
    out = (bgr * 0.5).astype(np.uint8)
    out[m] = bgr[m]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, contours, -1, (0, 255, 255), 2)
    return out


# Registro nombre→transformación, para que el script de viz itere fácil.
# Las que toman color se envuelven con functools.partial en el caller.
TRANSFORMS = {
    "enhance": enhance,
    "color_pop": color_pop,
    "cable_mask": cable_mask,
    "cable_overlay": cable_overlay,
}
