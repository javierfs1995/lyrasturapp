from PySide6.QtCore import QObject, Signal


class BaseCameraManager(QObject):
    """
    Clase base para cualquier cámara (ZWO real o simulada)

    Responsabilidades:
    - Emitir frames como QImage
    - Exponer API común (start/stop live, controles)
    """

    # 🔴 Frame listo para UI (CameraPage / PolarAlignment)
    frame_ready = Signal(object)   # QImage

    # ⚠️ Errores de cámara
    camera_error = Signal(str)

    def __init__(self):
        super().__init__()

    # ─────────────────────────────
    # Métodos que deben implementar las cámaras reales
    # ─────────────────────────────
    def start_live(self):
        raise NotImplementedError

    def stop_live(self):
        raise NotImplementedError

    def set_gain(self, value: int):
        pass

    def set_exposure(self, ms: float):
        pass

    def set_roi(self, x: int, y: int, w: int, h: int):
        pass
