from __future__ import annotations
from PySide6.QtCore import QObject, Signal
import numpy as np


class _FrameBus(QObject):
    """
    Bus global para compartir frames entre páginas.
    """
    frame_ready = Signal(object)  # np.ndarray


_FRAME_BUS = None


def FrameBus() -> _FrameBus:
    global _FRAME_BUS
    if _FRAME_BUS is None:
        _FRAME_BUS = _FrameBus()
    return _FRAME_BUS
