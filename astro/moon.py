from datetime import date
from astral.moon import phase


def moon_phase_fraction(d: date) -> float:
    """
    Devuelve fase lunar normalizada:
    0.0 = luna nueva
    1.0 = luna llena
    """
    p = phase(d)  # 0..29.53
    return min(p / 14.765, 1.0)
