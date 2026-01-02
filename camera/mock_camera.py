from __future__ import annotations
import numpy as np
import math
import time
from typing import Tuple

from camera.base import CameraBase


class MockCamera(CameraBase):
    def __init__(self, width: int = 960, height: int = 540):
        self.width = width
        self.height = height
        self._connected = False
        self.exposure_ms = 200
        self.gain = 50
        self.binning = 1
        self._t0 = time.time()

        # Estrellas “fijas” en el cielo (coordenadas base)
        rng = np.random.default_rng(42)
        n = 120
        self.stars = np.stack([
            rng.uniform(0, self.width, n),
            rng.uniform(0, self.height, n),
            rng.uniform(80, 255, n)  # brillo
        ], axis=1)

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_controls(self, exposure_ms: int, gain: int, binning: int = 1) -> None:
        self.exposure_ms = int(exposure_ms)
        self.gain = int(gain)
        self.binning = int(binning)

    def get_resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)

    def get_frame(self) -> np.ndarray:
        if not self._connected:
            raise RuntimeError("MockCamera not connected")

        # Simula un pequeño “movimiento” suave para que no sea estático
        t = time.time() - self._t0
        dx = 8.0 * math.sin(t / 8.0)
        dy = 6.0 * math.cos(t / 10.0)

        img = np.zeros((self.height, self.width), dtype=np.float32)

        # Añade estrellas como gaussianas
        for x, y, b in self.stars:
            xx = x + dx
            yy = y + dy
            if 0 <= xx < self.width and 0 <= yy < self.height:
                ix = int(xx)
                iy = int(yy)
                # pintar un “blob” 3x3
                for oy in range(-1, 2):
                    for ox in range(-1, 2):
                        x2 = ix + ox
                        y2 = iy + oy
                        if 0 <= x2 < self.width and 0 <= y2 < self.height:
                            dist2 = ox*ox + oy*oy
                            img[y2, x2] += b * math.exp(-dist2 / 1.2)

        # Ruido + ganancia/expo
        noise = np.random.normal(0, 6, size=img.shape).astype(np.float32)
        img = img + noise
        img = img * (0.6 + self.gain / 200.0) * (0.6 + self.exposure_ms / 800.0)

        img = np.clip(img, 0, 255).astype(np.uint8)
        return img
