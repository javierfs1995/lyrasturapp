from PySide6.QtCore import QObject, QTimer
from camera.frame_bus import FrameBus


class LiveViewService(QObject):
    def __init__(self, cam_manager, fps: int = 12):
        super().__init__()
        self.cam = cam_manager
        self.fps = fps

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_frame)

    def start(self, fps: int | None = None):
        """
        Arranca el live view.
        fps opcional para cambiarlo dinámicamente.
        """
        if fps is not None:
            self.fps = int(fps)
            self.timer.setInterval(int(1000 / self.fps))

        if not self.timer.isActive():
            self.cam.start_live()
            self.timer.start(int(1000 / self.fps))

    def stop(self):
        if self.timer.isActive():
            self.timer.stop()
        self.cam.stop_live()

    def _grab_frame(self):
        frame = self.cam.get_frame()
        if frame is not None:
            FrameBus().frame_ready.emit(frame)
