from PySide6.QtWidgets import QFrame, QVBoxLayout

class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(12, 12, 12, 12)
