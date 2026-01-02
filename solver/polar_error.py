from typing import Tuple


def compute_polar_error_arcmin(
    center_px: Tuple[float, float],
    sensor_center_px: Tuple[float, float],
    focal_mm: float,
    pixel_size_um: float
) -> Tuple[float, float]:
    """
    Devuelve error polar en arcmin:
    (error_az_arcmin, error_alt_arcmin)
    """

    dx_px = center_px[0] - sensor_center_px[0]
    dy_px = center_px[1] - sensor_center_px[1]

    # Escala de imagen
    arcsec_per_pixel = 206.265 * pixel_size_um / focal_mm

    dx_arcsec = dx_px * arcsec_per_pixel
    dy_arcsec = dy_px * arcsec_per_pixel

    dx_arcmin = dx_arcsec / 60.0
    dy_arcmin = dy_arcsec / 60.0

    # X → AZ, Y → ALT
    error_az = dx_arcmin
    error_alt = dy_arcmin

    return error_az, error_alt
