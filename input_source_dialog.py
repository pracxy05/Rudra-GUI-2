# inputsourcedialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QPushButton, QHBoxLayout,
    QMessageBox, QFileDialog, QListWidget
)
from PySide6.QtCore import Signal, Qt
import sys
import glob
import serial


class InputSourceDialog(QDialog):
    input_source_selected = Signal(str, object)  # (source_id, extra_details)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Input Source")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>Select telemetry input source:</b><br>"
            "Choose how telemetry data should be received.<br>"
            "Detect connected devices or browse CSV files."
        ))

        self.radio_csv = QRadioButton("CSV File (Load from Disk)")
        self.radio_xbee_wired = QRadioButton("XBee (Direct Wired)")
        self.radio_xbee_serial = QRadioButton("XBee (Serial/COM Port, auto-detect)")

        layout.addWidget(self.radio_csv)
        layout.addWidget(self.radio_xbee_wired)
        layout.addWidget(self.radio_xbee_serial)

        # COM port list for XBee Serial
        self.com_ports_list = QListWidget()
        self.com_ports_list.setVisible(False)
        layout.addWidget(self.com_ports_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        # Connections
        self.radio_xbee_serial.toggled.connect(self.update_com_ports)
        btn_ok.clicked.connect(self.accept_dialog)
        btn_cancel.clicked.connect(self.reject)

    # ---------------------
    #   Port Listing Logic
    # ---------------------
    def update_com_ports(self):
        """Show available COM ports when serial option selected."""
        self.com_ports_list.setVisible(self.radio_xbee_serial.isChecked())
        if self.radio_xbee_serial.isChecked():
            ports = self.list_serial_ports()
            self.com_ports_list.clear()
            if ports:
                self.com_ports_list.addItems(ports)
            else:
                self.com_ports_list.addItem("No COM ports detected")

    def list_serial_ports(self):
        """Cross-platform COM port listing."""
        if sys.platform.startswith('win'):
            ports = [f'COM{i+1}' for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            return []
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except Exception:
                pass
        return result

    # ---------------------
    #   Selection Logic
    # ---------------------
    def accept_dialog(self):
        """Handle user selection and emit appropriate signals."""
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
            QMessageBox.information(self, "XBee Wired", "Ensure your XBee wired module is connected.")
            self.accept()

        elif self.radio_xbee_serial.isChecked():
            if not self.com_ports_list.currentItem():
                QMessageBox.warning(self, "No Port", "Please select a COM port from the list.")
                return

            selected_port = self.com_ports_list.currentItem().text()
            if "No COM ports" in selected_port:
                QMessageBox.warning(self, "No Port", "No serial port detected. Please connect a device.")
                return

            self.input_source_selected.emit("xbee_serial", selected_port)
            self.accept()

        else:
            QMessageBox.warning(self, "No Selection", "Please select an input source.")
