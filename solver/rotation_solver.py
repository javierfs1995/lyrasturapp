import numpy as np
from typing import List, Tuple


def compute_rotation_center(
    stars_a: List[Tuple[float, float]],
    stars_b: List[Tuple[float, float]]
) -> Tuple[float, float]:
    """
    Calcula el centro de rotación (px) entre dos capturas.
    """
    if len(stars_a) < 5 or len(stars_b) < 5:
        raise ValueError("No hay suficientes estrellas")

    A = np.array(stars_a)
    B = np.array(stars_b)

    n = min(len(A), len(B))
    A = A[:n]
    B = B[:n]

    mid = (A + B) / 2
    d = B - A
    perp = np.column_stack([-d[:, 1], d[:, 0]])

    M = perp
    b = mid[:, 0] * perp[:, 0] + mid[:, 1] * perp[:, 1]

    center, *_ = np.linalg.lstsq(M, b, rcond=None)
    return float(center[0]), float(center[1])
