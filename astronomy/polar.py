from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


# Polaris (J2000) aproximada, suficiente para guiado de retículo
# RA 02h 31m 49s  -> 37.9541667 deg
# Dec +89° 15' 51" -> 89.2641667 deg
POLARIS_RA_DEG = 37.9541667
POLARIS_DEC_DEG = 89.2641667


def _julian_date(dt_utc: datetime) -> float:
    """Julian Date for a timezone-aware UTC datetime."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_utc = dt_utc.astimezone(timezone.utc)

    year = dt_utc.year
    month = dt_utc.month
    day = dt_utc.day
    hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600 + dt_utc.microsecond / 3.6e9

    if month <= 2:
        year -= 1
        month += 12

    A = year // 100
    B = 2 - A + (A // 4)

    JD = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    JD += hour / 24.0
    return JD


def gmst_degrees(dt_utc: datetime) -> float:
    """
    Greenwich Mean Sidereal Time (degrees).
    Good accuracy for polar alignment guidance.
    """
    JD = _julian_date(dt_utc)
    T = (JD - 2451545.0) / 36525.0

    gmst = (
        280.46061837
        + 360.98564736629 * (JD - 2451545.0)
        + 0.000387933 * (T ** 2)
        - (T ** 3) / 38710000.0
    )
    return gmst % 360.0


def lst_degrees(dt_utc: datetime, lon_deg: float) -> float:
    """Local Sidereal Time (degrees). Longitude: East positive, West negative."""
    return (gmst_degrees(dt_utc) + lon_deg) % 360.0


def hour_angle_degrees(dt_utc: datetime, lon_deg: float, ra_deg: float) -> float:
    """Hour angle = LST - RA (degrees), normalized 0..360."""
    ha = (lst_degrees(dt_utc, lon_deg) - ra_deg) % 360.0
    return ha


@dataclass
class PolarisPosition:
    dt_utc: datetime
    lst_deg: float
    ha_deg: float
    # ángulo de retículo tipo “reloj”
    # 0° = arriba (12 en punto), aumenta en sentido horario
    reticle_angle_deg: float
    clock_hours: float  # 0..12


def polaris_position(dt_local: datetime, lon_deg: float) -> PolarisPosition:
    """
    Devuelve la posición de Polaris en el retículo como "reloj".
    Retículo:
      - 12 en punto = arriba
      - gira en sentido horario
    """
    if dt_local.tzinfo is None:
        raise ValueError("dt_local must be timezone-aware (with tzinfo).")

    dt_utc = dt_local.astimezone(timezone.utc)
    lst = lst_degrees(dt_utc, lon_deg)
    ha = hour_angle_degrees(dt_utc, lon_deg, POLARIS_RA_DEG)

    # Para un visor polar típico:
    # HA=0° => Polaris arriba (12 en punto)
    # Aumenta HA => gira alrededor del polo
    reticle_angle = ha % 360.0

    # Convertir a “horas de reloj”: 360° = 12h, 30° = 1h
    clock_h = (reticle_angle / 30.0) % 12.0

    return PolarisPosition(
        dt_utc=dt_utc,
        lst_deg=lst,
        ha_deg=ha,
        reticle_angle_deg=reticle_angle,
        clock_hours=clock_h,
    )
