from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PolarInstructions(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.alt_label = QLabel("ALT: —")
        self.az_label = QLabel("AZ : —")
        self.quality_label = QLabel("Calidad: —")

        for lbl in (self.alt_label, self.az_label):
            lbl.setStyleSheet("font-size:14pt;font-weight:700")

        self.quality_label.setStyleSheet("color:#9aa4ab")

        layout.addWidget(QLabel("Polar Alignment"))
        layout.addWidget(self.alt_label)
        layout.addWidget(self.az_label)
        layout.addSpacing(10)
        layout.addWidget(self.quality_label)

    def update_values(self, error_az, error_alt):
        def fmt(v, axis):
            sign = "↑" if v > 0 and axis == "ALT" else \
                   "↓" if v < 0 and axis == "ALT" else \
                   "→" if v > 0 else "←"
            return f"{axis}: {sign} {abs(v):.2f}′"

        self.alt_label.setText(fmt(error_alt, "ALT"))
        self.az_label.setText(fmt(error_az, "AZ"))

        quality = max(0, 100 - (abs(error_alt) + abs(error_az)) * 5)
        self.quality_label.setText(f"Calidad: {int(quality)} %")
