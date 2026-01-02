from PySide6.QtCore import QObject, Signal


class BaseWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def run(self):
        """
        Sobrescribir en cada worker
        """
        raise NotImplementedError
