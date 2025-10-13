# admin.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QCheckBox, QHBoxLayout,
    QLineEdit, QTextEdit, QGroupBox, QFormLayout, QComboBox
)
from PySide6.QtCore import Qt


class AdminTab(QWidget):
    def __init__(self):
        super().__init__()
        print("Initializing AdminTab")
        self.setWindowTitle("Admin Control Panel")
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Admin Control Panel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #c0392b;")
        layout.addWidget(title)

        # System Control Group
        sysgrp = QGroupBox("System Control")
        sys_layout = QFormLayout()
        self.power_checkbox = QCheckBox("System Power")
        self.power_checkbox.setChecked(True)
        self.sensor_checkbox = QCheckBox("Sensor Power")
        self.sensor_checkbox.setChecked(True)
        sys_layout.addRow("Main Power:", self.power_checkbox)
        sys_layout.addRow("Sensor Power:", self.sensor_checkbox)
        sysgrp.setLayout(sys_layout)
        layout.addWidget(sysgrp)

        # Access control
        self.access_code_edit = QLineEdit()
        self.access_code_edit.setPlaceholderText("Set Admin Access Code")
        self.access_code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.access_code_edit)

        # Command Input and Log Display
        cmdgrp = QGroupBox("Console Command")
        cmd_layout = QVBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter admin command")
        self.cmd_send_btn = QPushButton("Send Command")
        self.cmd_send_btn.clicked.connect(self.send_command)
        self.cmd_response = QTextEdit()
        self.cmd_response.setReadOnly(True)
        cmd_layout.addWidget(self.cmd_input)
        cmd_layout.addWidget(self.cmd_send_btn)
        cmd_layout.addWidget(self.cmd_response)
        cmdgrp.setLayout(cmd_layout)
        layout.addWidget(cmdgrp)

        # Data Encryption Mode Selector
        enc_group = QGroupBox("Encryption Settings")
        enc_layout = QHBoxLayout()
        self.enc_sel = QComboBox()
        self.enc_sel.addItems(["AES-128", "AES-256", "RSA-2048"])
        enc_layout.addWidget(QLabel("Encryption Algorithm:"))
        enc_layout.addWidget(self.enc_sel)
        enc_group.setLayout(enc_layout)
        layout.addWidget(enc_group)

        layout.addStretch()

    def send_command(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        # Example: Simulate command execution and response
        response = f"Executed command: {cmd}"
        self.cmd_response.append(response)
        self.cmd_input.clear()
