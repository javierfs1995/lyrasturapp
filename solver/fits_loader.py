from astropy.io import fits
import numpy as np


def load_fits(path: str) -> np.ndarray:
    """
    Carga un FITS astronómico y devuelve una imagen normalizada.
    """
    with fits.open(path) as hdul:
        data = hdul[0].data.astype(float)

    # Normalizar
    data -= data.min()
    data /= data.max()
    data *= 255.0

    return data.astype("uint8")
