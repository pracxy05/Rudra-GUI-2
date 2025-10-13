from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QPushButton, QHBoxLayout, QMessageBox, QFileDialog, QInputDialog
)
from PySide6.QtCore import Signal, Qt

class InputSourceDialog(QDialog):
    
    input_source_selected = Signal(str, object)  # signal with source id and extra data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Input Source")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Choose telemetry input source:"))

        self.radio_csv = QRadioButton("CSV File")
        self.radio_xbee_wired = QRadioButton("XBee (Direct Wired)")
        self.radio_xbee_serial = QRadioButton("XBee (Serial/COM Port)")

        layout.addWidget(self.radio_csv)
        layout.addWidget(self.radio_xbee_wired)
        layout.addWidget(self.radio_xbee_serial)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        btn_ok.clicked.connect(self.accept_dialog)
        btn_cancel.clicked.connect(self.reject)

    def accept_dialog(self):
        if self.radio_csv.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)")
            if not path:
                QMessageBox.warning(self, "No File Selected", "Please select a CSV file or cancel.")
                return
            self.input_source_selected.emit("csv", path)
            self.accept()
        elif self.radio_xbee_wired.isChecked():
            self.input_source_selected.emit("xbee_wired", None)
            self.accept()
        elif self.radio_xbee_serial.isChecked():
            port, ok = QInputDialog.getText(self, "Serial Port", "Enter COM port (e.g. COM3):")
            if not ok or not port.strip():
                QMessageBox.warning(self, "Invalid Port", "Please enter a valid COM port or cancel.")
                return
            self.input_source_selected.emit("xbee_serial", port.strip())
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select an input source.")
