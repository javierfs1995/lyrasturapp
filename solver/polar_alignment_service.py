from typing import Tuple

from solver.frame_loader import load_frame
from solver.star_detection import detect_stars
from solver.rotation_solver import compute_rotation_center
from solver.polar_error import compute_polar_error_arcmin


class PolarAlignmentService:
    def __init__(
        self,
        focal_mm: float,
        pixel_size_um: float
    ):
        self.focal_mm = focal_mm
        self.pixel_size_um = pixel_size_um

    def solve_from_files(
        self,
        frame_a_path: str,
        frame_b_path: str
    ) -> Tuple[
        Tuple[float, float],  # sensor center
        Tuple[float, float],  # polar center
        float,                # error AZ arcmin
        float                 # error ALT arcmin
    ]:
        # Cargar imágenes
        frame_a = load_frame(frame_a_path)
        frame_b = load_frame(frame_b_path)

        # Detectar estrellas
        stars_a = detect_stars(frame_a)
        stars_b = detect_stars(frame_b)

        if len(stars_a) < 10 or len(stars_b) < 10:
            raise RuntimeError("No hay suficientes estrellas detectadas")

        # Centro de rotación
        polar_center = compute_rotation_center(stars_a, stars_b)

        # Centro del sensor
        h, w = frame_a.shape
        sensor_center = (w / 2, h / 2)

        # Error polar
        error_az, error_alt = compute_polar_error_arcmin(
            polar_center,
            sensor_center,
            self.focal_mm,
            self.pixel_size_um
        )

        return sensor_center, polar_center, error_az, error_alt
