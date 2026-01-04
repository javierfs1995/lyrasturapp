import numpy as np
from camera.base_camera import BaseCameraManager


class SimulatedCameraManager(BaseCameraManager):
    def __init__(self):
        super().__init__()
        self.camera_connected = True
        self.sdk_available = True

        self._live = False
        self._w = 1280
        self._h = 960
        self._frame_id = 0

        # Escala simulada (arcmin por pixel) — debe alinearse con PolarAlignmentPage.arcmin_per_px
        self.arcmin_per_px = 0.15

        # Error polar (arcmin) ajustable
        self._err_az_arcmin = 25.0   # derecha/izquierda (simulado)
        self._err_alt_arcmin = -15.0 # arriba/abajo (simulado)

        # Campo estelar base
        self._rng = np.random.default_rng(42)
        self._stars_bg = self._generate_background_stars()

    # ─────────────────────────
    def _generate_background_stars(self):
        stars = []
        for _ in range(140):
            x = self._rng.uniform(0, self._w)
            y = self._rng.uniform(0, self._h)
            flux = self._rng.uniform(70, 170)
            stars.append((x, y, flux))
        return stars

    # ─────────────────────────
    # API extra para Polar Alignment (demo)
    # ─────────────────────────
    def set_polar_error_arcmin(self, az_arcmin: float, alt_arcmin: float):
        self._err_az_arcmin = float(az_arcmin)
        self._err_alt_arcmin = float(alt_arcmin)

    def get_polar_error_arcmin(self):
        return self._err_az_arcmin, self._err_alt_arcmin

    # ─────────────────────────
    def start_live(self):
        self._live = True
        self._frame_id = 0

    def stop_live(self):
        self._live = False

    # ─────────────────────────
    def get_frame(self):
        if not self._live:
            return None

        self._frame_id += 1

        # Fondo oscuro + ruido
        frame = np.random.normal(18, 2, (self._h, self._w))

        # Convertir error arcmin → px (para colocar Polaris respecto al centro)
        err_px = np.array([
            self._err_az_arcmin / self.arcmin_per_px,
            self._err_alt_arcmin / self.arcmin_per_px
        ])

        # Deriva coherente: más error → deriva más (px/frame)
        # (esto simula lo que “ves” al ir tocando ALT/AZ)
        drift_rate = np.clip(err_px / 2500.0, -0.05, 0.05)  # límite seguridad
        drift = drift_rate * self._frame_id

        # Seeing (jitter)
        seeing = np.random.normal(0, 0.35, 2)

        # Dibujar estrellas de fondo (no derivan)
        for (x0, y0, flux) in self._stars_bg:
            x = x0 + seeing[0]
            y = y0 + seeing[1]
            ix = int(round(x))
            iy = int(round(y))
            if 1 <= ix < self._w - 1 and 1 <= iy < self._h - 1:
                frame[iy-1:iy+2, ix-1:ix+2] += flux

        # Polaris (estrella dominante) cerca del centro + error + deriva
        pol_x = (self._w / 2) + err_px[0] - drift[0] + seeing[0]
        pol_y = (self._h / 2) + err_px[1] - drift[1] + seeing[1]

        ix = int(round(pol_x))
        iy = int(round(pol_y))
        if 2 <= ix < self._w - 2 and 2 <= iy < self._h - 2:
            frame[iy-1:iy+2, ix-1:ix+2] += 420  # Polaris

        frame = np.clip(frame, 0, 255).astype(np.uint8)
        return frame
