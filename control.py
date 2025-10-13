# control.py
from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox, QFrame,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QColor
from dashboard1 import DashboardWindow
import os

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        print("Initializing LoginWindow UI")
        self.setWindowTitle("RUDRA Login")
        self.setGeometry(400, 300, 420, 540)
        self.setStyleSheet("""
            QWidget { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f2f2f2, stop:1 #e6e6e6); }
            QLabel { color: #2c3e50; font-size: 15px; margin-bottom: 8px; letter-spacing: 0.7px; }
            QLineEdit { padding: 12px; border: 2px solid #bdc3c7; border-radius: 8px; background-color: #ffffff; color: #2c3e50; font-size: 14px; }
            QLineEdit:focus { border: 2px solid #2980b9; background-color: #f8fbff; }
            QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5dade2, stop:1 #3498db); color: white; padding: 11px; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; letter-spacing: 0.5px; }
            QPushButton:hover { background-color: #2e86de; }
            QPushButton:pressed { background-color: #1f669e; }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(25)

        # Logo
        logolabel = QLabel()
        logolabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logopath = os.path.join(os.path.dirname(__file__), "assets", "rudralogo.png")
        if os.path.exists(logopath):
            pixmap = QPixmap(logopath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logolabel.setPixmap(scaled)
            else:
                logolabel.setText("RUDRA")
        else:
            logolabel.setText("RUDRA")

        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(60)
        glow.setColor(QColor(52, 152, 219, 180))
        glow.setOffset(0, 0)
        logolabel.setGraphicsEffect(glow)
        layout.addWidget(logolabel)

        titlelabel = QLabel("RUDRA Mission Control")
        titlelabel.setFont(QFont("Orbitron", 18, QFont.Weight.Bold))
        titlelabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titlelabel)

        # Form frame
        formframe = QFrame()
        formframe.setStyleSheet("""
            QFrame { background-color: rgba(255,255,255,0.9); border-radius: 14px; padding: 28px 24px 20px 24px; border: 1px solid #dcdcdc; }
        """)
        frame_shadow = QGraphicsDropShadowEffect()
        frame_shadow.setBlurRadius(35)
        frame_shadow.setColor(QColor(52, 152, 219, 50))
        frame_shadow.setOffset(0, 12)
        formframe.setGraphicsEffect(frame_shadow)

        formlayout = QVBoxLayout()
        inputlabel = QLabel("Enter Launch Access Code")
        inputlabel.setFont(QFont("Arial", 13))
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter Security Code")
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.returnPressed.connect(self.check_login)
        self.loginbtn = QPushButton("🚀 LAUNCH")
        self.loginbtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.loginbtn.clicked.connect(self.check_login)
        formlayout.addWidget(inputlabel)
        formlayout.addWidget(self.input)
        formlayout.addWidget(self.loginbtn)
        formframe.setLayout(formlayout)
        layout.addWidget(formframe)
        layout.addStretch()
        self.setLayout(layout)

    def check_login(self):
        print("Check login triggered")
        self.loginbtn.setEnabled(False)
        self.input.setEnabled(False)
        allowed_passwords = ["rudra", "RUDRA", "Rudra"]
        try:
            if any(self.input.text().lower() == p.lower() for p in allowed_passwords):
                print("Login successful, opening DashboardWindow")
                self.dashboard = DashboardWindow()
                self.dashboard.show()
                self.close()
            else:
                print("Login failed: Incorrect Launch Code")
                QMessageBox.warning(self, "Access Denied", "Incorrect Launch Code")
                self.loginbtn.setEnabled(True)
                self.input.setEnabled(True)
                self.input.clear()
                self.input.setFocus()
        except Exception as e:
            import traceback
            error_message = f"Failed to open dashboard:\n{str(e)}"
            print("Exception in check_login:", e)
            print(traceback.format_exc())
            QMessageBox.critical(self, "Error", error_message)
            self.loginbtn.setEnabled(True)
            self.input.setEnabled(True)
