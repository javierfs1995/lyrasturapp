import cv2
import numpy as np


def detect_polaris(gray: np.ndarray):
    """
    Devuelve (x, y) en píxeles del centro de Polaris.
    Retorna None si no encuentra candidato fiable.
    """
    if gray is None or gray.size == 0:
        return None

    # Normalizar y suavizar
    img = cv2.GaussianBlur(gray, (7, 7), 0)

    # Umbral adaptativo para estrellas brillantes
    _, th = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Limpiar ruido
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Encontrar blobs
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    h, w = gray.shape
    cx_img, cy_img = w / 2, h / 2

    # Elegimos el blob más brillante y cercano al centro
    best = None
    best_score = -1

    for c in cnts:
        area = cv2.contourArea(c)
        if area < 5:
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue

        x = M["m10"] / M["m00"]
        y = M["m01"] / M["m00"]

        # brillo medio del blob
        mask = np.zeros_like(gray, dtype=np.uint8)
        cv2.drawContours(mask, [c], -1, 255, -1)
        brightness = cv2.mean(gray, mask=mask)[0]

        # penalizar distancia al centro
        dist = np.hypot(x - cx_img, y - cy_img)
        score = brightness - 0.05 * dist

        if score > best_score:
            best_score = score
            best = (int(x), int(y))

    return best
