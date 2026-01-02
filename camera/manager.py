from __future__ import annotations
from typing import Optional

from camera.base import CameraBase
from camera.mock_camera import MockCamera


class CameraManager:
    def __init__(self):
        self.camera: CameraBase = MockCamera()

    def set_mock(self):
        self.camera = MockCamera()

    def get(self) -> CameraBase:
        return self.camera
