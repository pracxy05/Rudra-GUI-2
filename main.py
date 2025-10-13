# main.py
import sys
import os

# Force software OpenGL as fallback
os.environ['QT_OPENGL'] = 'software'
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["VISPY_GL_BACKEND"] = "pyqt6"
os.environ["VISPY_USE_APP"] = "PyQt6"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet
from control import LoginWindow

# Use desktop OpenGL if available
from PySide6.QtOpenGLWidgets import QOpenGLWidget
QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)

if __name__ == "__main__":
    print("Starting QApplication")
    app = QApplication(sys.argv)
    
    print("Applying stylesheet")
    apply_stylesheet(app, theme='light_blue.xml')

    print("Creating LoginWindow")
    try:
        window = LoginWindow()
        print("Showing LoginWindow")
        window.show()
    except Exception as e:
        import traceback
        print("Error creating LoginWindow:", e)
        print(traceback.format_exc())

    print("Entering event loop")
    sys.exit(app.exec())
