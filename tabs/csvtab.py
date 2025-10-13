from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QTableWidget, QTableWidgetItem
import pandas as pd
import os


class CSVTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        self.label = QLabel("📂 CSV Viewer")
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load CSV File")
        self.load_btn.clicked.connect(self.load_csv)
        btn_layout.addWidget(self.load_btn)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_csv)
        btn_layout.addWidget(self.refresh_btn)
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        layout.addWidget(self.table, stretch=1)

        self.setLayout(layout)
        self.csv_path = None

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if path:
            self.csv_path = path
            self.display_csv(path)

    def refresh_csv(self):
        if self.csv_path and os.path.exists(self.csv_path):
            self.display_csv(self.csv_path)

    def display_csv(self, path):
        try:
            df = pd.read_csv(path)
            self.table.setRowCount(len(df))
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels(list(df.columns))
            for i, row in df.iterrows():
                for j, val in enumerate(row):
                    self.table.setItem(i, j, QTableWidgetItem(str(val)))
        except Exception as e:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.label.setText(f"Error: {e}")
