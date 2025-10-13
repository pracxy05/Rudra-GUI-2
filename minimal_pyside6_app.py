# minimal_pyside6_app.py
import sys
from PySide6.QtWidgets import QApplication, QLabel

if __name__ == "__main__":
    app = QApplication(sys.argv)
    label = QLabel("Hello, PySide6!")
    label.show()
    sys.exit(app.exec())
