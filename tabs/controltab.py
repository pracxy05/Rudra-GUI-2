from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QLabel, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class PowerButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumWidth(100)
        self.setMinimumHeight(40)
        self.is_on = False
        self.update_style()

    def update_style(self):
        if self.is_on:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2ecc71;
                    border: 2px solid #27ae60;
                    border-radius: 5px;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #27ae60;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    border: 2px solid #c0392b;
                    border-radius: 5px;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)


class ControlTab(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()

        cmd_section = QFrame()
        cmd_section.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.1);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        cmd_layout = QVBoxLayout()
        cmd_section.setLayout(cmd_layout)

        self.label = QLabel("🚀 Command Panel")
        self.label.setStyleSheet("""
            QLabel {
                color: #2980b9;
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        cmd_layout.addWidget(self.label)

        power_layout = QHBoxLayout()

        self.system_power = PowerButton("System Power")
        self.system_power.clicked.connect(self.toggle_system_power)

        self.sensor_power = PowerButton("Sensor Power")
        self.sensor_power.clicked.connect(self.toggle_sensor_power)

        power_layout.addWidget(self.system_power)
        power_layout.addWidget(self.sensor_power)
        cmd_layout.addLayout(power_layout)

        self.cmd_input = QTextEdit()
        self.cmd_input.setPlaceholderText("Type command here...")
        self.cmd_input.setMaximumHeight(100)
        cmd_layout.addWidget(self.cmd_input)

        self.send_btn = QPushButton("Send Command")
        self.send_btn.clicked.connect(self.send_command)
        cmd_layout.addWidget(self.send_btn)

        self.response = QLabel("Response: None")
        cmd_layout.addWidget(self.response)

        main_layout.addWidget(cmd_section)

        sensor_section = QFrame()
        sensor_section.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        sensor_layout = QVBoxLayout()
        sensor_section.setLayout(sensor_layout)

        sensor_title = QLabel("📊 Sensor Readings")
        sensor_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sensor_layout.addWidget(sensor_title)

        self.altitude_label = QLabel("Altitude: -- m")
        self.temp_label = QLabel("Temperature: -- °C")
        self.pressure_label = QLabel("Pressure: -- hPa")
        self.humidity_label = QLabel("Humidity: -- %")
        self.gas_label = QLabel("Gas Level: -- ppm")

        sensor_layout.addWidget(self.altitude_label)
        sensor_layout.addWidget(self.temp_label)
        sensor_layout.addWidget(self.pressure_label)
        sensor_layout.addWidget(self.humidity_label)
        sensor_layout.addWidget(self.gas_label)

        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh Sensors")
        self.refresh_btn.clicked.connect(self.refresh_sensors)

        self.calibrate_btn = QPushButton("⚙️ Calibrate")
        self.calibrate_btn.clicked.connect(self.calibrate_sensors)

        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.calibrate_btn)

        sensor_layout.addLayout(button_layout)
        main_layout.addWidget(sensor_section)

        self.setLayout(main_layout)

    def toggle_system_power(self):
        self.system_power.is_on = not self.system_power.is_on
        self.system_power.setText("System ON" if self.system_power.is_on else "System OFF")
        self.system_power.update_style()
        status = "activated" if self.system_power.is_on else "deactivated"
        self.response.setText(f"Response: System power {status}")

    def toggle_sensor_power(self):
        self.sensor_power.is_on = not self.sensor_power.is_on
        self.sensor_power.setText("Sensors ON" if self.sensor_power.is_on else "Sensors OFF")
        self.sensor_power.update_style()
        status = "activated" if self.sensor_power.is_on else "deactivated"
        self.response.setText(f"Response: Sensor power {status}")

        self.refresh_btn.setEnabled(self.sensor_power.is_on)
        self.calibrate_btn.setEnabled(self.sensor_power.is_on)

    def send_command(self):
        cmd = self.cmd_input.toPlainText()
        if cmd:
            if self.system_power.is_on:
                self.response.setText(f"Response: Command '{cmd}' sent.")
            else:
                self.response.setText("Response: System power is OFF. Please turn ON the system first.")
            self.cmd_input.clear()

    def refresh_sensors(self):
        if not self.sensor_power.is_on:
            self.response.setText("Response: Sensors are powered OFF")
            return

        self.altitude_label.setText("Altitude: 123.45 m")
        self.temp_label.setText("Temperature: 25.6 °C")
        self.pressure_label.setText("Pressure: 1013.25 hPa")
        self.humidity_label.setText("Humidity: 45.7 %")
        self.gas_label.setText("Gas Level: 125 ppm")
        self.response.setText("Response: Sensor readings updated")

    def calibrate_sensors(self):
        if not self.sensor_power.is_on:
            self.response.setText("Response: Sensors are powered OFF")
            return
        self.response.setText("Response: Calibrating sensors...")
