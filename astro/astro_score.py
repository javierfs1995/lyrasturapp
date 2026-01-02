from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # Python < 3.9


# ─────────────────────────────────────────────
# Astropy (real astronomy)
# ─────────────────────────────────────────────
_ASTROPY_OK = True
try:
    from astropy.time import Time
    from astropy.coordinates import EarthLocation, AltAz, get_sun, get_body
    import astropy.units as u
    try:
        from astropy.coordinates import moon_illumination  # type: ignore
        _HAS_MOON_ILLUM = True
    except Exception:
        _HAS_MOON_ILLUM = False
except Exception:
    _ASTROPY_OK = False


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────
@dataclass
class AstroNightSummary:
    night_id: str
    dark_hours: int
    avg_score_dark: int
    best_hour_score: int
    best_window_hours: int


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def parse_datetime_any(t: Any) -> Optional[datetime]:
    if t is None:
        return None
    if isinstance(t, datetime):
        return t

    s = str(t).strip()
    if not s:
        return None

    s = s.replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def to_local(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is not None:
        return dt

    if ZoneInfo is None:
        return dt

    try:
        return dt.replace(tzinfo=ZoneInfo(tz_name))
    except Exception:
        return dt


def night_id_from_datetime(dt_local: datetime) -> str:
    """
    NOCHE ASTRONÓMICA REAL:
    - Si la hora es antes de las 12:00 → pertenece a la noche anterior
    - Si es después → noche del mismo día
    """
    if dt_local.hour < 12:
        night = dt_local.date() - timedelta(days=1)
    else:
        night = dt_local.date()
    return night.strftime("%Y-%m-%d")


def dark_factor(sun_alt_deg: float) -> float:
    """
    Factor de oscuridad:
    - >= -12° → 0
    - <= -18° → 1
    - interpolación entre medias
    """
    if sun_alt_deg >= -12.0:
        return 0.0
    if sun_alt_deg <= -18.0:
        return 1.0
    return (-(sun_alt_deg + 12.0)) / 6.0


def moon_penalty(moon_alt_deg: float, moon_illum_pct: float) -> float:
    if moon_alt_deg <= 0.0:
        return 0.0

    illum = max(0.0, min(100.0, moon_illum_pct))
    alt = max(0.0, min(90.0, moon_alt_deg))

    return (illum * 0.35) + (alt * 0.20)


def seeing_penalty(humidity: float, wind_kmh: float) -> float:
    h = max(0.0, min(100.0, humidity))
    w = max(0.0, wind_kmh)

    p = 0.0
    if h > 85:
        p += (h - 85) * 0.6
    if w > 15:
        p += (w - 15) * 1.0
    if h > 85 and w > 20:
        p += 10.0

    return min(p, 35.0)


def meteo_fallback_score(clouds: float, humidity: float, wind: float) -> int:
    clouds = max(0.0, min(100.0, clouds))
    humidity = max(0.0, min(100.0, humidity))
    wind = max(0.0, wind)

    p = clouds * 0.65 + humidity * 0.20 + min(wind, 40.0)
    return int(round(max(0.0, min(100.0, 100.0 - p))))


# ─────────────────────────────────────────────
# CORE FUNCTION
# ─────────────────────────────────────────────
def compute_astro_scores(
    lat: float,
    lon: float,
    hourly_rows: List[Dict[str, Any]],
    tz_name: str = "Europe/Madrid",
) -> Tuple[List[Dict[str, Any]], Dict[str, AstroNightSummary]]:

    summaries: Dict[str, List[int]] = {}
    best_window: Dict[str, int] = {}
    current_window: Dict[str, int] = {}

    if not hourly_rows:
        return hourly_rows, {}

    # ───── FALLBACK SIN ASTROPY ─────
    if not _ASTROPY_OK:
        for r in hourly_rows:
            c = float(r.get("clouds", 0))
            h = float(r.get("humidity", 0))
            w = float(r.get("wind", 0))
            score = meteo_fallback_score(c, h, w)

            r["astro_score"] = score
            r["is_dark"] = True

            night = "unknown"
            summaries.setdefault(night, []).append(score)
            current_window[night] = current_window.get(night, 0) + 1
            best_window[night] = max(best_window.get(night, 0), current_window[night])

        return hourly_rows, build_summaries(summaries, best_window)

    # ───── ASTROPY REAL ─────
    location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg)

    for r in hourly_rows:
        dt = parse_datetime_any(r.get("time"))
        if dt is None:
            continue

        dt_local = to_local(dt, tz_name)
        night = night_id_from_datetime(dt_local)

        t = Time(dt_local)
        altaz = AltAz(obstime=t, location=location)

        sun_alt = float(get_sun(t).transform_to(altaz).alt.to(u.deg).value)
        moon = get_body("moon", t, location=location)
        moon_alt = float(moon.transform_to(altaz).alt.to(u.deg).value)

        if _HAS_MOON_ILLUM:
            try:
                illum = float(moon_illumination(t) * 100.0)
            except Exception:
                illum = 0.0
        else:
            illum = 0.0

        df = dark_factor(sun_alt)
        is_dark = df > 0.05

        clouds = float(r.get("clouds", 0))
        humidity = float(r.get("humidity", 0))
        wind = float(r.get("wind", 0))

        p = (
            clouds * 0.60 +
            min(wind, 40.0) * 1.0 +
            humidity * 0.15 +
            moon_penalty(moon_alt, illum) +
            seeing_penalty(humidity, wind)
        )

        base = max(0.0, min(100.0, 100.0 - p))
        score = int(round(base * df))

        r["astro_score"] = score
        r["is_dark"] = is_dark
        r["sun_alt_deg"] = sun_alt
        r["moon_alt_deg"] = moon_alt
        r["moon_illum_pct"] = illum

        if is_dark:
            summaries.setdefault(night, []).append(score)
            current_window[night] = current_window.get(night, 0) + 1
            best_window[night] = max(best_window.get(night, 0), current_window[night])
        else:
            current_window[night] = 0

    return hourly_rows, build_summaries(summaries, best_window)


def build_summaries(
    scores_by_night: Dict[str, List[int]],
    best_window: Dict[str, int]
) -> Dict[str, AstroNightSummary]:

    out: Dict[str, AstroNightSummary] = {}

    for night, scores in scores_by_night.items():
        if not scores:
            out[night] = AstroNightSummary(night, 0, 0, 0, 0)
            continue

        out[night] = AstroNightSummary(
            night_id=night,
            dark_hours=len(scores),
            avg_score_dark=int(round(sum(scores) / len(scores))),
            best_hour_score=max(scores),
            best_window_hours=best_window.get(night, 0),
        )

    return out
