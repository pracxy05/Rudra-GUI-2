# inputsourcedialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QPushButton, QHBoxLayout,
    QMessageBox, QFileDialog, QInputDialog, QListWidget
)
from PySide6.QtCore import Signal, Qt

import sys
import glob

class InputSourceDialog(QDialog):
    input_source_selected = Signal(str, object)  # signal with source id and extra data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Input Source")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>Choose telemetry input source:</b><br>"
            "Select an input method for incoming data.<br>"
            "Detect connected devices and configure as required."
        ))

        self.radio_csv = QRadioButton("CSV File (Load from Disk)")
        self.radio_xbee_wired = QRadioButton("XBee (Direct Wired)")
        self.radio_xbee_serial = QRadioButton("XBee (Serial/COM Port, auto-detect)")

        layout.addWidget(self.radio_csv)
        layout.addWidget(self.radio_xbee_wired)
        layout.addWidget(self.radio_xbee_serial)

        # Info for port listing
        self.com_ports_list = QListWidget()
        self.com_ports_list.setVisible(False)
        layout.addWidget(self.com_ports_list)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.radio_xbee_serial.toggled.connect(self.update_com_ports)

        btn_ok.clicked.connect(self.accept_dialog)
        btn_cancel.clicked.connect(self.reject)

    def update_com_ports(self):
        if self.radio_xbee_serial.isChecked():
            self.com_ports_list.setVisible(True)
            ports = self.list_serial_ports()
            self.com_ports_list.clear()
            if ports:
                self.com_ports_list.addItems(ports)
            else:
                self.com_ports_list.addItem("No COM ports detected")
        else:
            self.com_ports_list.setVisible(False)

    def list_serial_ports(self):
        # Cross-platform serial port discovery
        if sys.platform.startswith('win'):
            ports = [f'COM{i+1}' for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            return []
        result = []
        import serial
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except Exception:
                pass
        return result

    def accept_dialog(self):
        if self.radio_csv.isChecked():
            path, _ = QFileDialog.getOpenFileName(
                self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
            )
            if not path:
                QMessageBox.warning(self, "No File Selected", "Please select a CSV file or cancel.")
                return
            self.input_source_selected.emit("csv", path)
            self.accept()
        elif self.radio_xbee_wired.isChecked():
            self.input_source_selected.emit("xbee_wired", None)
            QMessageBox.information(self, "XBee Wired", "Ensure your XBee wired interface is connected and powered.")
            self.accept()
        elif self.radio_xbee_serial.isChecked():
            selected_port = None
            if self.com_ports_list.currentItem():
                selected_port = self.com_ports_list.currentItem().text()
                if "No COM ports" in selected_port:
                    QMessageBox.warning(self, "No Port", "No serial port detected. Please connect a device.")
                    return
            else:
                QMessageBox.warning(self, "No Port", "Please select a COM port from the list.")
                return
            self.input_source_selected.emit("xbee_serial", selected_port)
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select an input source.")


