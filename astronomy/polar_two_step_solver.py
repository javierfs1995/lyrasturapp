from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Tuple
import math


@dataclass
class SolverResult:
    ok: bool
    angle_deg: float
    center_xy: Tuple[float, float]
    offset_xy: Tuple[float, float]   # center_xy - image_center
    matches: int
    mean_error_px: float
    total_error_px: float
    message: str


def _local_maxima_points(img: np.ndarray, threshold: float, max_points: int = 250) -> np.ndarray:
    H, W = img.shape
    a = img[1:-1, 1:-1]

    n0 = img[0:-2, 0:-2]
    n1 = img[0:-2, 1:-1]
    n2 = img[0:-2, 2:  ]
    n3 = img[1:-1, 0:-2]
    n4 = img[1:-1, 2:  ]
    n5 = img[2:  , 0:-2]
    n6 = img[2:  , 1:-1]
    n7 = img[2:  , 2:  ]

    maxima = (a > threshold) & \
             (a >= n0) & (a >= n1) & (a >= n2) & (a >= n3) & \
             (a >= n4) & (a >= n5) & (a >= n6) & (a >= n7)

    ys, xs = np.where(maxima)
    if xs.size == 0:
        return np.zeros((0, 2), dtype=np.float32)

    xs = xs + 1
    ys = ys + 1

    vals = img[ys, xs]
    order = np.argsort(vals)[::-1]
    order = order[:max_points]
    pts = np.stack([xs[order], ys[order]], axis=1).astype(np.float32)
    return pts


def detect_stars(img: np.ndarray, max_points: int = 250) -> np.ndarray:
    if img.ndim != 2:
        raise ValueError("detect_stars expects grayscale 2D image")

    a = img.astype(np.float32)
    mean = float(np.mean(a))
    std = float(np.std(a))
    thr = mean + 3.0 * std
    return _local_maxima_points(a, threshold=thr, max_points=max_points)


def rotate_points(P: np.ndarray, center: Tuple[float, float], angle_deg: float) -> np.ndarray:
    cx, cy = center
    ang = np.deg2rad(angle_deg)
    c = np.cos(ang)
    s = np.sin(ang)

    X = P[:, 0] - cx
    Y = P[:, 1] - cy
    xr = c * X - s * Y + cx
    yr = s * X + c * Y + cy
    return np.stack([xr, yr], axis=1)


def match_points(P: np.ndarray, Q: np.ndarray, tol_px: float = 6.0) -> Tuple[np.ndarray, np.ndarray, float]:
    if P.shape[0] == 0 or Q.shape[0] == 0:
        return np.zeros((0, 2), dtype=np.float32), np.zeros((0, 2), dtype=np.float32), float("inf")

    Q_used = np.zeros((Q.shape[0],), dtype=bool)
    Pm, Qm, errs = [], [], []

    for i in range(P.shape[0]):
        px, py = P[i]
        dx = Q[:, 0] - px
        dy = Q[:, 1] - py
        d2 = dx * dx + dy * dy

        j = int(np.argmin(d2))
        if Q_used[j]:
            continue
        d = float(np.sqrt(d2[j]))
        if d <= tol_px:
            Q_used[j] = True
            Pm.append([px, py])
            Qm.append([Q[j, 0], Q[j, 1]])
            errs.append(d)

    if len(errs) == 0:
        return np.zeros((0, 2), dtype=np.float32), np.zeros((0, 2), dtype=np.float32), float("inf")

    return np.array(Pm, dtype=np.float32), np.array(Qm, dtype=np.float32), float(np.mean(errs))


def estimate_center_from_pairs(P: np.ndarray, Q: np.ndarray, angle_deg: float) -> Tuple[Tuple[float, float], bool]:
    ang = np.deg2rad(angle_deg)
    c = np.cos(ang)
    s = np.sin(ang)
    R = np.array([[c, -s],
                  [s,  c]], dtype=np.float32)
    I = np.eye(2, dtype=np.float32)
    A = (I - R)

    det = float(np.linalg.det(A))
    if abs(det) < 1e-6:
        return (0.0, 0.0), False

    Ainv = np.linalg.inv(A)

    C = []
    for i in range(P.shape[0]):
        p = P[i]
        q = Q[i]
        rhs = q - (R @ p)
        ci = Ainv @ rhs
        C.append(ci)

    C = np.stack(C, axis=0)
    cx = float(np.median(C[:, 0]))
    cy = float(np.median(C[:, 1]))
    return (cx, cy), True


def solve_polar_two_step(
    img1: np.ndarray,
    img2: np.ndarray,
    search_deg: Tuple[float, float] = (35.0, 145.0),
    step_deg: float = 1.0,
    tol_px: float = 7.0,
    max_points: int = 220
) -> SolverResult:

    if img1.ndim != 2 or img2.ndim != 2:
        return SolverResult(False, 0.0, (0.0, 0.0), (0.0, 0.0), 0, 0.0, 0.0, "Imágenes no válidas (2D).")

    H, W = img1.shape
    center_img = (W / 2.0, H / 2.0)

    P1 = detect_stars(img1, max_points=max_points)
    P2 = detect_stars(img2, max_points=max_points)

    if P1.shape[0] < 12 or P2.shape[0] < 12:
        return SolverResult(
            False, 0.0, center_img, (0.0, 0.0),
            0, 0.0, 0.0,
            f"Pocas estrellas (img1={P1.shape[0]}, img2={P2.shape[0]}). Sube expo/gain."
        )

    a0, a1 = search_deg
    angles = np.arange(a0, a1 + 1e-6, step_deg, dtype=np.float32)

    best_matches = -1
    best_err = float("inf")
    best_angle = 0.0

    for ang in angles:
        P1r = rotate_points(P1, center_img, float(ang))
        Pm, Qm, err = match_points(P1r, P2, tol_px=tol_px)
        m = Pm.shape[0]
        if m > best_matches or (m == best_matches and err < best_err):
            best_matches = m
            best_err = err
            best_angle = float(ang)

    if best_matches < 8:
        return SolverResult(False, best_angle, center_img, (0.0, 0.0), best_matches, best_err, 0.0,
                           "No hay matches suficientes. Gira RA 60–90° y sube expo/gain.")

    P1r = rotate_points(P1, center_img, best_angle)
    Pm_r, Qm, mean_err = match_points(P1r, P2, tol_px=tol_px)

    if Pm_r.shape[0] < 8:
        return SolverResult(False, best_angle, center_img, (0.0, 0.0), int(Pm_r.shape[0]), mean_err, 0.0,
                           "Matching insuficiente. Ajusta tol_px o mejora capturas.")

    center_est, ok = estimate_center_from_pairs(Pm_r, Qm, best_angle)
    if not ok:
        return SolverResult(False, best_angle, center_img, (0.0, 0.0), int(Pm_r.shape[0]), mean_err, 0.0,
                           "No se pudo estimar el centro (degenerado).")

    cx, cy = center_est
    dx = cx - center_img[0]
    dy = cy - center_img[1]
    total = float(math.hypot(dx, dy))

    return SolverResult(
        True,
        best_angle,
        (cx, cy),
        (dx, dy),
        int(Pm_r.shape[0]),
        float(mean_err),
        total,
        "OK. Centro de rotación estimado."
    )
