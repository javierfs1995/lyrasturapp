import cv2
import numpy as np
from typing import List, Tuple


def detect_stars(
    frame: np.ndarray,
    min_area: int = 5,
    max_area: int = 500
) -> List[Tuple[float, float]]:
    """
    Detecta estrellas y devuelve centroides (x, y).
    """
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()

    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        11,
        -2
    )

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    stars = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                x = M["m10"] / M["m00"]
                y = M["m01"] / M["m00"]
                stars.append((x, y))

    return stars
