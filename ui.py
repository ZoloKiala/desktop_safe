import sys
from PyQt6.QtWidgets import QApplication
from aquasafe_ui.window import GeospatialProcessingWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeospatialProcessingWindow()
    window.show()
    sys.exit(app.exec())