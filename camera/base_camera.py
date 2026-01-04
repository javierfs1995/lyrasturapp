from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np


class BaseCameraManager(ABC):
    """
    Interfaz común para cámara real (ZWO) y simulador.
    get_frame() devuelve np.ndarray uint8:
      - Mono: shape (H, W)
      - Color: shape (H, W, 3) en RGB
    """

    def __init__(self):
        self.sdk_available: bool = False
        self.camera_connected: bool = False
        self.is_live: bool = False

    @abstractmethod
    def start_live(self) -> bool:
        ...

    @abstractmethod
    def stop_live(self) -> None:
        ...

    @abstractmethod
    def get_frame(self, timeout_ms: int = 200) -> Optional[np.ndarray]:
        ...

    @abstractmethod
    def set_gain(self, value: int) -> None:
        ...

    @abstractmethod
    def set_exposure(self, ms: float) -> None:
        ...

    @abstractmethod
    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        ...

    @abstractmethod
    def get_sensor_size(self) -> Tuple[int, int]:
        ...


class SimulatedCameraManager(BaseCameraManager):
    """
    Simulador simple: estrellas en fondo negro.
    Ideal para probar pipeline (FrameBus, overlays, etc.)
    """

    def __init__(self, width: int = 1280, height: int = 720):
        super().__init__()
        self.sdk_available = True
        self.camera_connected = True
        self._w = width
        self._h = height

        self._gain = 100
        self._exp_ms = 30.0
        self._roi = (0, 0, width, height)

        self._t = 0

    def get_sensor_size(self):
        return self._w, self._h

    def start_live(self) -> bool:
        self.is_live = True
        return True

    def stop_live(self) -> None:
        self.is_live = False

    def set_gain(self, value: int) -> None:
        self._gain = int(value)

    def set_exposure(self, ms: float) -> None:
        self._exp_ms = float(ms)

    def set_roi(self, x: int, y: int, w: int, h: int) -> None:
        # No recortamos de verdad: solo guardamos para compatibilidad
        self._roi = (int(x), int(y), int(w), int(h))

    def get_frame(self, timeout_ms: int = 200):
        if not self.is_live:
            return None

        self._t += 1
        x, y, w, h = self._roi

        img = np.zeros((h, w), dtype=np.uint8)

        # estrellas pseudo-aleatorias
        rng = np.random.default_rng(self._t)
        n = 250
        xs = rng.integers(0, w, size=n)
        ys = rng.integers(0, h, size=n)
        br = rng.integers(120, 255, size=n)

        img[ys, xs] = br

        # una "polaris" brillante
        cx = w // 2 + int(40 * np.cos(self._t / 20))
        cy = h // 2 + int(30 * np.sin(self._t / 25))
        cx = max(5, min(w - 6, cx))
        cy = max(5, min(h - 6, cy))
        img[cy - 2:cy + 3, cx - 2:cx + 3] = 255

        return img
