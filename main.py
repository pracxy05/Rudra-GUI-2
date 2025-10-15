# main.py
import sys, os
os.environ["QTOPENGL"] = "software"
os.environ["QT_QUICK_BACKEND"] = "software"

from PySide6.QtWidgets import QApplication
from qt_material import apply_stylesheet
from control import LoginWindow

class MainApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        apply_stylesheet(self.app, theme='light_blue.xml')

    def run(self):
        self.show_login()

    def show_login(self):
        try:
            self.window = LoginWindow()
            self.window.show()
            self.window.login_successful.connect(self.show_dashboard)
        except Exception as e:
            import traceback
            print("Error creating LoginWindow:", e)
            print(traceback.format_exc())
            sys.exit(1)
        sys.exit(self.app.exec())

    def show_dashboard(self):
        try:
            from dashboard1 import MainDashboardWindow
            self.dash = MainDashboardWindow()
            self.dash.show()
        except Exception as e:
            import traceback
            print("Error creating MainDashboardWindow:", e)
            print(traceback.format_exc())

if __name__ == "__main__":
    MainApp().run()
