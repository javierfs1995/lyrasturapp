from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QVBoxLayout, QMessageBox

from ui.polar_view import PolarView
from ui.polar_instructions import PolarInstructions

from solver.polar_alignment_service import PolarAlignmentService


class PolarAlignmentPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setSpacing(16)

        # Vista + instrucciones
        self.view = PolarView()
        self.instructions = PolarInstructions()

        # Panel derecho con botón
        right = QVBoxLayout()
        right.addWidget(self.instructions)

        self.solve_button = QPushButton("🔄 Recalcular alineación")
        self.solve_button.clicked.connect(self.solve_alignment)
        right.addWidget(self.solve_button)
        right.addStretch(1)

        layout.addWidget(self.view, 3)
        layout.addLayout(right, 1)

        # Servicio de solver (configurable)
        self.solver = PolarAlignmentService(
            focal_mm=700.0,
            pixel_size_um=2.0
        )

        # Rutas temporales (luego vendrán de cámara)
        self.frame_a_path = "solver/data/polaris/frame_a.png"
        self.frame_b_path = "solver/data/polaris/frame_b.png"

        # Primer cálculo automático
        self.solve_alignment()

    def solve_alignment(self):
        try:
            sensor_center, polar_center, error_az, error_alt = (
                self.solver.solve_from_files(
                    self.frame_a_path,
                    self.frame_b_path
                )
            )

            self.view.set_centers(sensor_center, polar_center)
            self.instructions.update_values(error_az, error_alt)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error en Polar Alignment",
                str(e)
            )
