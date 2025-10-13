from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QGridLayout, QProgressBar
from PySide6.QtGui import QFont
from PySide6.QtCore import QTimer
import random


class SystemDialsTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.signal_box, self.signal_bar = self.make_dial("📶 Signal Strength", "%")
        layout.addWidget(self.signal_box)

        self.battery_box, self.battery_bar = self.make_dial("🔋 Battery", "%")
        layout.addWidget(self.battery_box)

        self.cpu_box, self.cpu_bar = self.make_dial("🖥 CPU Usage", "%")
        layout.addWidget(self.cpu_box)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_dummy_data)
        self.timer.start(1000)

    def make_dial(self, title, unit):
        group = QGroupBox(title)
        glayout = QGridLayout()

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(50)
        bar.setFormat(f"%p{unit}")
        bar.setFont(QFont("Segoe UI", 10))

        glayout.addWidget(bar, 0, 0)
        group.setLayout(glayout)
        return group, bar

    def update_dummy_data(self):
        self.signal_bar.setValue(random.randint(50, 100))
        self.battery_bar.setValue(random.randint(30, 100))
        self.cpu_bar.setValue(random.randint(10, 90))
