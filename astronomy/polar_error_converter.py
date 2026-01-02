from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class PolarErrorAngular:
    ok: bool
    azi_arcsec: float
    alt_arcsec: float
    total_arcsec: float
    azi_text: str
    alt_text: str
    total_text: str
    azi_move: str
    alt_move: str
    message: str


def plate_scale_arcsec_per_px(pixel_um: float, focal_mm: float) -> float:
    """
    arcsec/px = 206.265 * (pixel_um / focal_mm)
    """
    if focal_mm <= 0 or pixel_um <= 0:
        return 0.0
    return 206.265 * (pixel_um / focal_mm)


def _rot(dx: float, dy: float, deg: float) -> Tuple[float, float]:
    a = math.radians(deg)
    c = math.cos(a)
    s = math.sin(a)
    return (c * dx - s * dy, s * dx + c * dy)


def _format_arcsec(arcsec: float) -> str:
    """
    Devuelve algo como: 0° 05′ 22″
    """
    sign = "-" if arcsec < 0 else ""
    a = abs(arcsec)

    deg = int(a // 3600)
    rem = a - deg * 3600
    minutes = int(rem // 60)
    seconds = rem - minutes * 60

    return f"{sign}{deg}° {minutes:02d}′ {seconds:04.1f}″"


def convert_px_to_alt_azi(
    dx_px: float,
    dy_px: float,
    pixel_um: float,
    focal_mm: float,
    north_orientation: str = "N_ARRIBA",
) -> PolarErrorAngular:
    """
    Convierte dx/dy en píxeles a errores angulares (ALT/AZI) usando:
      - plate scale (arcsec/px)
      - orientación aproximada de 'Norte' en la imagen

    Convención base:
      - Imagen: +x derecha, +y abajo
      - Si 'N_ARRIBA': arriba = Norte (por tanto y hacia arriba es +N)

    NOTA:
      Esto es "coordenadas" (angulares). Sin plate solving, la relación exacta ALT/AZI
      depende del ángulo de campo y del framing, pero esta aproximación es útil en la práctica.
    """
    s = plate_scale_arcsec_per_px(pixel_um, focal_mm)
    if s <= 0:
        return PolarErrorAngular(
            ok=False,
            azi_arcsec=0.0,
            alt_arcsec=0.0,
            total_arcsec=0.0,
            azi_text="—",
            alt_text="—",
            total_text="—",
            azi_move="—",
            alt_move="—",
            message="Configura focal (mm) y tamaño de píxel (µm) para convertir a coordenadas.",
        )

    # Rotamos el vector de error según dónde esté el Norte en la imagen.
    # Queremos un sistema "normalizado" donde N está ARRIBA.
    # - Si N_ARRIBA: 0°
    # - Si N_DERECHA: para llevarlo a N_ARRIBA rotamos +90° (imagen girada -90)
    # - Si N_ABAJO: 180°
    # - Si N_IZQUIERDA: -90°
    rot_deg = {
        "N_ARRIBA": 0.0,
        "N_DERECHA": 90.0,
        "N_ABAJO": 180.0,
        "N_IZQUIERDA": -90.0,
    }.get(north_orientation, 0.0)

    dxr, dyr = _rot(dx_px, dy_px, rot_deg)

    # En sistema N_ARRIBA:
    # - ALT: vertical (N/S). Como +y en imagen es hacia abajo, ALT(+) es -dyr.
    # - AZI: horizontal (E/O). Usamos dxr (derecha positivo).
    alt_arcsec = (-dyr) * s
    azi_arcsec = (dxr) * s

    total_arcsec = math.sqrt(alt_arcsec * alt_arcsec + azi_arcsec * azi_arcsec)

    # Texto y sugerencia de movimiento
    azi_move = "Mover AZI →" if azi_arcsec > 0 else ("Mover AZI ←" if azi_arcsec < 0 else "AZI OK")
    alt_move = "Mover ALT ↑" if alt_arcsec > 0 else ("Mover ALT ↓" if alt_arcsec < 0 else "ALT OK")

    return PolarErrorAngular(
        ok=True,
        azi_arcsec=azi_arcsec,
        alt_arcsec=alt_arcsec,
        total_arcsec=total_arcsec,
        azi_text=_format_arcsec(azi_arcsec),
        alt_text=_format_arcsec(alt_arcsec),
        total_text=_format_arcsec(total_arcsec),
        azi_move=azi_move,
        alt_move=alt_move,
        message=f"Escala: {s:.2f}″/px (pixel={pixel_um}µm, focal={focal_mm}mm).",
    )
