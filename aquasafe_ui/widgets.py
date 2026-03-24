from PyQt6.QtWidgets import QFrame


class CardFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("cardFrame")
        self.setFrameShape(QFrame.Shape.NoFrame)