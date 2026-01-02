from __future__ import annotations
from dataclasses import dataclass
from typing import Dict


@dataclass
class Telescope:
    name: str
    focal_mm: float


@dataclass
class Camera:
    name: str
    pixel_um: float


@dataclass
class EquipmentProfile:
    name: str
    telescope: Telescope
    camera: Camera
    focal_multiplier: float = 1.0

    @property
    def effective_focal(self) -> float:
        return self.telescope.focal_mm * self.focal_multiplier


# ─────────────────────────────────────────────
# Perfiles por defecto (editables)
# ─────────────────────────────────────────────

DEFAULT_PROFILES: Dict[str, EquipmentProfile] = {
    "Newton 76/700 + ASI678MC": EquipmentProfile(
        name="Newton 76/700 + ASI678MC",
        telescope=Telescope(
            name="Newton 76/700",
            focal_mm=700.0
        ),
        camera=Camera(
            name="ZWO ASI678MC",
            pixel_um=2.0   # valor real de la ASI678MC
        ),
        focal_multiplier=1.0
    ),

    "Refractor genérico 80/480": EquipmentProfile(
        name="Refractor 80/480 + Cámara genérica",
        telescope=Telescope(
            name="Refractor 80/480",
            focal_mm=480.0
        ),
        camera=Camera(
            name="Genérica",
            pixel_um=3.76
        ),
        focal_multiplier=1.0
    ),
}
