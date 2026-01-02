import os
import cv2
import numpy as np


def load_frame(path: str) -> np.ndarray:
    """
    Carga una imagen astronómica:
    - FITS (.fits/.fit/.fts)
    - PNG / JPG / TIF / BMP

    Devuelve imagen en escala de grises uint8.
    """
    ext = os.path.splitext(path)[1].lower()

    # FITS
    if ext in [".fits", ".fit", ".fts"]:
        from astropy.io import fits
        with fits.open(path) as hdul:
            data = hdul[0].data.astype(float)

        data -= np.nanmin(data)
        maxv = np.nanmax(data)
        if maxv > 0:
            data /= maxv
        data = np.clip(data * 255, 0, 255).astype(np.uint8)
        return data

    # Imagen normal
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"No se pudo cargar: {path}")

    img = img.astype(np.float32)
    img -= img.min()
    maxv = img.max()
    if maxv > 0:
        img /= maxv
    return (img * 255).astype(np.uint8)
