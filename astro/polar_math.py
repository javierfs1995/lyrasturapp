import math


def pixel_scale_arcsec(pixel_size_um: float, focal_mm: float) -> float:
    """
    Escala en arcsec/pixel
    """
    return 206.265 * (pixel_size_um / focal_mm)


def polar_error_from_pixels(
    dx_px: float,
    dy_px: float,
    pixel_size_um: float,
    focal_mm: float,
):
    """
    Devuelve error total y componentes ALT/AZ en arcmin
    """
    scale_arcsec = pixel_scale_arcsec(pixel_size_um, focal_mm)

    dx_arcmin = (dx_px * scale_arcsec) / 60.0
    dy_arcmin = (dy_px * scale_arcsec) / 60.0

    error = math.hypot(dx_arcmin, dy_arcmin)

    # Convención:
    #  X → AZ
    #  Y → ALT
    return {
        "error_arcmin": error,
        "alt_arcmin": -dy_arcmin,
        "az_arcmin": dx_arcmin,
    }
