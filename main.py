import sys

from PyQt6.QtWidgets import QApplication

from ui import GeospatialProcessingWindow


def main():
    app = QApplication(sys.argv)
    window = GeospatialProcessingWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()