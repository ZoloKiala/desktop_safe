MAIN_STYLESHEET = """
QMainWindow {
    background: #f3f5f7;
}

QWidget#centralRoot, QWidget#bodyRoot {
    background: #f3f5f7;
    color: #1b2745;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QLabel {
    background: transparent;
    color: #1b2745;
}

QFrame#topBar {
    background: #1c2856;
    border: none;
}

QLabel#logoLabel,
QLabel#appTitleLabel {
    background: transparent;
    color: white;
}

QLabel#appTitleLabel {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#heroTitle {
    font-size: 24px;
    font-weight: 700;
    color: #1b2745;
}

QLabel#heroSubtitle {
    font-size: 14px;
    color: #657089;
}

QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 700;
    color: #1b2745;
}

QLabel#sectionLabel {
    font-size: 13px;
    font-weight: 600;
    color: #5d6a82;
}

QLabel#fileInfoLabel,
QLabel#helpLabel {
    color: #5f6b82;
    font-size: 13px;
}

QLabel#statusLabel {
    background: #e8f7ec;
    color: #1f6b3b;
    border: 1px solid #b7e4c7;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: 600;
}

QLabel#updateLabel {
    background: #fff4d6;
    color: #8a6116;
    border: 1px solid #f0d58a;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: 600;
}

QFrame#cardFrame {
    background: #ffffff;
    border: 1px solid #d8e0ea;
    border-radius: 16px;
}

QGroupBox#formGroup {
    background: #f8fafc;
    border: 1px solid #dde4ee;
    border-radius: 14px;
    margin-top: 10px;
    font-weight: 700;
    color: #223154;
}

QGroupBox#formGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QPushButton {
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
    min-height: 20px;
}

QPushButton#primaryButton {
    background: #2a56d4;
    color: white;
    border: none;
}

QPushButton#primaryButton:hover {
    background: #204bc4;
}

QPushButton#softButton,
QPushButton#headerButton {
    background: #e6ecf5;
    color: #1d2b4d;
    border: 1px solid #d3dce8;
}

QPushButton#softButton:hover,
QPushButton#headerButton:hover {
    background: #dce5f0;
}

QPushButton:disabled {
    background: #cfd8e3;
    color: #7b8797;
}

QToolButton#iconToolButton {
    background: #e6ecf5;
    border: 1px solid #d3dce8;
    border-radius: 12px;
    padding: 8px;
}

QToolButton#iconToolButton:hover {
    background: #dce5f0;
}

QToolButton#iconToolButton:disabled {
    background: #cfd8e3;
    border: 1px solid #cfd8e3;
}

QLineEdit,
QComboBox,
QTextEdit {
    background: white;
    border: 1px solid #d7deea;
    border-radius: 10px;
    padding: 8px 10px;
    color: #1b2745;
}

QComboBox {
    min-height: 22px;
    padding-right: 26px;
}

QLineEdit:focus,
QComboBox:focus,
QTextEdit:focus {
    border: 1px solid #5b86ff;
}

QRadioButton {
    spacing: 8px;
    color: #1b2745;
    font-weight: 600;
}

QScrollArea {
    border: none;
    background: #f3f5f7;
}

QTableWidget {
    background: white;
    border: 1px solid #d7deea;
    border-radius: 12px;
    gridline-color: #e8edf4;
    selection-background-color: #dfe9ff;
    selection-color: #1b2745;
}

QHeaderView::section {
    background: #eef3f8;
    color: #1b2745;
    border: none;
    border-bottom: 1px solid #d7deea;
    padding: 8px;
    font-weight: 700;
}

QTextEdit#logOutput {
    background: #fbfcfe;
    border: 1px solid #d7deea;
    border-radius: 12px;
}
"""