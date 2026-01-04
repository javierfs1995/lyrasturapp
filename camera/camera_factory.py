from camera.camera_source import CameraSource
from camera.simulated_camera import SimulatedCameraManager
from camera.zwo_camera import ZWOCameraManager


def create_camera_manager(source: CameraSource):
    if source == CameraSource.ZWO:
        cam = ZWOCameraManager()
        if cam.camera_connected:
            return cam

        # fallback automático
        print("[CameraFactory] ZWO no disponible → Simulador")
        return SimulatedCameraManager()

    if source == CameraSource.FILE:
        raise NotImplementedError("File camera aún no implementada")

    return SimulatedCameraManager()
