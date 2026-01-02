DARK_THEME = """
QWidget {
    background-color: #0f1418;
    color: #dfe6eb;
    font-family: Segoe UI;
    font-size: 10pt;
}

QLabel {
    color: #dfe6eb;
}

QPushButton {
    background-color: #1b2328;
    border: 1px solid #2a353c;
    border-radius: 6px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #243038;
}

QPushButton:pressed {
    background-color: #2c3a44;
}

QComboBox {
    background-color: #1b2328;
    border: 1px solid #2a353c;
    border-radius: 6px;
    padding: 4px 8px;
}

QComboBox QAbstractItemView {
    background-color: #1b2328;
    selection-background-color: #2c3a44;
    border: 1px solid #2a353c;
}

QTableWidget {
    background-color: #0f1418;
    gridline-color: #1f2a30;
}

QHeaderView::section {
    background-color: #1b2328;
    color: #e6eef2;
    font-weight: bold;
    padding: 6px;
    border: none;
}

QScrollBar:vertical {
    background: #0f1418;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #2a353c;
    border-radius: 4px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
