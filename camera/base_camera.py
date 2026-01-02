class BaseCameraManager:
    def start_live(self):
        raise NotImplementedError

    def stop_live(self):
        raise NotImplementedError

    def get_frame(self):
        raise NotImplementedError

    def set_gain(self, value: int):
        raise NotImplementedError

    def set_exposure(self, ms: float):
        raise NotImplementedError

    def set_roi(self, x, y, w, h):
        raise NotImplementedError
