from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class MissionStageBar(QWidget):
    def __init__(self):
        super().__init__()
        self.stages = [
            "START_TEST", "LAUNCH", "ASCEND", "SEPARATE_PAYLOAD",
            "BEGIN_DESCENT", "DEPLOY_AEROBRAKE", "LAND"
        ]
        self.current_stage = 0

        layout = QHBoxLayout()
        layout.setSpacing(20)

        self.stage_labels = []
        for stage in self.stages:
            label = QLabel(stage)
            label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(40)
            label.setFixedWidth(150)
            label.setFrameShape(QFrame.Shape.Box)
            label.setStyleSheet("background-color: gray; color: white; border-radius: 8px;")
            layout.addWidget(label)
            self.stage_labels.append(label)

        self.setLayout(layout)

        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_stage)
        self.timer.start(3000)  # Every 3 seconds

    def animate_stage(self):
        if self.current_stage < len(self.stage_labels):
            # Reset previous stages to green (completed)
            for i in range(self.current_stage):
                self.stage_labels[i].setStyleSheet("background-color: green; color: white; border-radius: 8px;")

            # Highlight current stage (yellow)
            self.stage_labels[self.current_stage].setStyleSheet("background-color: orange; color: black; border-radius: 8px;")
            self.current_stage += 1
        else:
            # Once completed, loop back
            self.current_stage = 0
            for label in self.stage_labels:
                label.setStyleSheet("background-color: gray; color: white; border-radius: 8px;")
