import numpy as np
import cv2
from typing import Tuple


def generate_synthetic_sky(
    width: int = 640,
    height: int = 480,
    star_count: int = 100,
    noise_level: float = 5.0,
    seed: int = 42
) -> np.ndarray:
    """
    Genera una imagen sintética de cielo con estrellas.
    """
    rng = np.random.default_rng(seed)

    frame = np.zeros((height, width), dtype=np.float32)

    for _ in range(star_count):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)
        intensity = rng.uniform(150, 255)
        sigma = rng.uniform(0.8, 1.5)

        xx, yy = np.meshgrid(
            np.arange(width),
            np.arange(height)
        )

        gaussian = intensity * np.exp(
            -((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2)
        )

        frame += gaussian

    # Añadir ruido
    noise = rng.normal(0, noise_level, frame.shape)
    frame += noise

    # Normalizar
    frame = np.clip(frame, 0, 255)
    return frame.astype(np.uint8)


def rotate_frame(
    frame: np.ndarray,
    angle_deg: float,
    center: Tuple[float, float] | None = None
) -> np.ndarray:
    """
    Rota la imagen simulando giro de RA.
    """
    h, w = frame.shape[:2]
    if center is None:
        center = (w / 2, h / 2)

    M = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rotated = cv2.warpAffine(
        frame,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderValue=0
    )

    return rotated
