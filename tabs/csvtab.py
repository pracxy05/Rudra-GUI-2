from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLabel, QTableWidget, QTableWidgetItem, QRadioButton
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
import os

class CSVTab(QWidget):
    # Signal emits every row (live or CSV) as a dictionary
    data_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        header = QHBoxLayout()
        self.label = QLabel("CSV Viewer")
        header.addWidget(self.label)

        self.live_radio = QRadioButton("Live")
        self.file_radio = QRadioButton("File")
        self.live_radio.setChecked(True)
        header.addWidget(self.live_radio)
        header.addWidget(self.file_radio)
        header.addStretch()
        layout.addLayout(header)

        btnlayout = QHBoxLayout()
        self.loadbtn = QPushButton("Load CSV File")
        self.loadbtn.clicked.connect(self.loadcsv)
        btnlayout.addWidget(self.loadbtn)

        self.refreshbtn = QPushButton("Refresh")
        self.refreshbtn.clicked.connect(self.refreshcsv)
        btnlayout.addWidget(self.refreshbtn)
        layout.addLayout(btnlayout)

        self.table = QTableWidget()
        layout.addWidget(self.table, stretch=1)

        self.csvpath = None
        self.csvdata = None
        self._live_data = []

        # Default mode
        self.mode = "live"

        self.live_radio.toggled.connect(self.mode_toggled)

        # --- Comments for future connections ---
        # Connect receivers to data_updated signal here.
        # Example: self.data_updated.connect(telemetry_panel.update_telemetry)
        # You can add connections for plot, cockpit, or other tabs here in future.

    def mode_toggled(self, checked):
        if self.live_radio.isChecked():
            self.mode = "live"
            self.loadbtn.setDisabled(True)
            self.refreshbtn.setDisabled(True)
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
        else:
            self.mode = "file"
            self.loadbtn.setDisabled(False)
            self.refreshbtn.setDisabled(False)

    def loadcsv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV file", "", "CSV Files (*.csv);;All Files (*)")
        if path:
            self.csvpath = path
            self.displaycsv(path)

    def displaycsv(self, path):
        try:
            df = pd.read_csv(path)
            self.csvdata = df
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels(df.columns.astype(str).tolist())

            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                self.appendRow(row_dict)
                self.data_updated.emit(row_dict)

            self.label.setText(f"CSV Loaded: {os.path.basename(path)}")
        except Exception as e:
            self.label.setText(f"Error loading CSV: {str(e)}")

    def appendRow(self, row):
        current_row = self.table.rowCount()
        if current_row == 0:
            # Setup headers if first row
            self.table.setColumnCount(len(row))
            self.table.setHorizontalHeaderLabels([str(k) for k in row.keys()])

        self.table.insertRow(current_row)
        for col_idx, (key, value) in enumerate(row.items()):
            item = QTableWidgetItem(str(value))
            self.table.setItem(current_row, col_idx, item)

        # Emit the row update signal so telemetry or other tabs can update
        self.data_updated.emit(row)

    def refreshcsv(self):
        if self.csvpath:
            self.displaycsv(self.csvpath)

    # Method for external live data appending (called from XBee preprocessor)
    def append_live_data(self, row):
        if self.mode == "live":
            self.appendRow(row)