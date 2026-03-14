import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)


class SimpleApp(QWidget):
    def __init__(self):
        super().__init__()

        # Set up the window
        self.setWindowTitle("Simple PyQt App")
        self.resize(400, 200)

        # Layout
        layout = QVBoxLayout()

        # Widgets
        self.label = QLabel("Type something and click the button:")
        self.input = QLineEdit()
        self.button = QPushButton("Show Message")

        # Add widgets to layout
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.button)

        # Connect button click
        self.button.clicked.connect(self.show_message)

        # Apply layout
        self.setLayout(layout)

    def show_message(self):
        text = self.input.text().strip()
        if not text:
            QMessageBox.information(self, "Info", "Please type something first 🙂")
        else:
            QMessageBox.information(self, "You typed:", text)


def main():
    app = QApplication(sys.argv)
    window = SimpleApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
