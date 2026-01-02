from datetime import datetime
from astral import LocationInfo
from astral.sun import sun


def _to_naive(dt: datetime) -> datetime:
    """
    Convierte cualquier datetime a naive (sin tzinfo).
    """
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def is_night_time(dt: datetime, lat: float, lon: float) -> bool:
    """
    True si es noche astronómica.
    Todo se normaliza a datetime naive para evitar errores tz-aware.
    """
    dt = _to_naive(dt)

    location = LocationInfo(latitude=lat, longitude=lon)

    s = sun(
        location.observer,
        date=dt.date()
        # ❌ NO pasamos tzinfo aquí
    )

    dawn = _to_naive(s["dawn"])
    dusk = _to_naive(s["dusk"])

    return dt < dawn or dt > dusk
