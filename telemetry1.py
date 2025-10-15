# telemetry1.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QGridLayout
)
from PySide6.QtCore import Qt, Signal

class TelemetryPanel(QWidget):
    tab_select = Signal(int)  # Signal emits tab index (0..5)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(310)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(11)
        main_layout.setContentsMargins(7, 7, 7, 7)
        block_style = (
            "QFrame {background-color: #f2f2f2; border: 1.8px solid #bdbdbd; border-radius: 13px; padding: 8px 10px;}"
        )

        # Top: CONNECTION PANEL
        conn_block = QFrame()
        conn_block.setStyleSheet(block_style)
        conn_layout = QHBoxLayout()
        left_labels, right_vals = QVBoxLayout(), QVBoxLayout()
        for txt in ["CONNECTION:", "MISSION TIME:", "PACKET COUNT:"]:
            left_labels.addWidget(self._keybox(txt))
        self.lbl_conn = self._valbox("DISCONNECTED", "#d63031")
        self.lbl_time = self._valbox("00:00")
        self.lbl_pack = self._valbox("0")
        for widget in [self.lbl_conn, self.lbl_time, self.lbl_pack]:
            right_vals.addWidget(widget)
        conn_layout.addLayout(left_labels)
        conn_layout.addLayout(right_vals)
        conn_block.setLayout(conn_layout)
        main_layout.addWidget(conn_block)

        # FLIGHT PANEL - MAPS DIRECTLY TO COLUMN NAMES
        flight_block = QFrame()
        flight_block.setStyleSheet(block_style)
        flight_layout, l1, l2 = QHBoxLayout(), QVBoxLayout(), QVBoxLayout()
        self.flight_keys = [
            ("Altitude", "bmp_alt"),
            ("Acceleration", "accel"),
            ("Temperature", "bme_temp"),
            ("Pressure", "bme_p"),
            ("Battery", "batt_v"),
            ("Comm", "comm_q"),
        ]
        for txt, _ in self.flight_keys:
            l1.addWidget(self._keybox(f"{txt.upper()}:"))
        self.vals_flight = [self._valbox("-") for _ in self.flight_keys]
        for widget in self.vals_flight:
            l2.addWidget(widget)
        flight_layout.addLayout(l1)
        flight_layout.addLayout(l2)
        flight_block.setLayout(flight_layout)
        main_layout.addWidget(flight_block)

        # GPS PANEL - ALSO MAPS COLUMN NAMES
        gps_block = QFrame()
        gps_block.setStyleSheet(block_style)
        gps_layout, l3, l4 = QHBoxLayout(), QVBoxLayout(), QVBoxLayout()
        self.gps_keys = [
            ("GPS Alt", "gps_alt"),
            ("Latitude", "gps_lat"),
            ("Longitude", "gps_lon"),
            ("Velocity", "gps_vel"),
            ("Comm Redundant", "comm_q_R"),
        ]
        for txt, _ in self.gps_keys:
            l3.addWidget(self._keybox(f"{txt.upper()}:"))
        self.vals_gps = [self._valbox("-") for _ in self.gps_keys]
        for widget in self.vals_gps:
            l4.addWidget(widget)
        gps_layout.addLayout(l3)
        gps_layout.addLayout(l4)
        gps_block.setLayout(gps_layout)
        main_layout.addWidget(gps_block)

        # --- Navigation Buttons (unchanged) ---
        main_layout.addStretch()
        nav_outer = QFrame()
        nav_outer.setStyleSheet(
            """
            QFrame { border: 2px solid #bbb; border-radius: 14px; background-color: #d4d7db; margin-top: 12px; }
            """
        )
        nav_grid = QGridLayout()
        nav_grid.setSpacing(6)
        self.tab_btns = []
        names = ["CONTROL", "LIVE-3D", "SYS_INFO", "GPS", "CSV", "MISSION LOGS"]
        for idx, name in enumerate(names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, ix=idx: self._tab_clicked(ix))
            self.tab_btns.append(btn)
            row, col = divmod(idx, 2)
            nav_grid.addWidget(btn, row, col)
        nav_outer.setLayout(nav_grid)
        main_layout.addWidget(nav_outer, alignment=Qt.AlignmentFlag.AlignBottom)

        self.setLayout(main_layout)

        # Internal counters / state
        self._packets = 0

    def _tab_clicked(self, ix):
        for i, btn in enumerate(self.tab_btns):
            btn.setChecked(i == ix)
        self.tab_select.emit(ix)

    def _keybox(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "background:#fafbfa; border:1.1px solid #cbcbcb; border-radius:8px; font-family:Consolas; font-size:15px; padding:6px 8px;"
        )
        return lbl

    def _valbox(self, text, color=None):
        lbl = QLabel(text)
        style = "background:#fafbfa; border:1.2px solid #cbcbcb; border-radius:8px; font-family:Consolas; font-size:15px; padding:6px 8px;"
        if color:
            style += f"color:{color}; font-weight:bold;"
        lbl.setStyleSheet(style)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    # Helper: set connection label and color
    def set_connection_state(self, connected: bool, text: str = None):
        if connected:
            self.lbl_conn.setText(text or "CONNECTED")
            self.lbl_conn.setStyleSheet(self.lbl_conn.styleSheet() + " color: #006400; font-weight:bold;")
        else:
            self.lbl_conn.setText(text or "DISCONNECTED")
            self.lbl_conn.setStyleSheet(self.lbl_conn.styleSheet() + " color: #d63031; font-weight:bold;")

    # Slot to receive telemetry data rows and update display.
    # Row must be a dict with keys matching the configured column names.
    # If primary field missing or invalid, tries fallback field with _R suffix.
    def update_telemetry(self, row):
        # Increment packet count
        try:
            self._packets += 1
            self.lbl_pack.setText(str(self._packets))
        except Exception:
            pass

        for i, (_, col) in enumerate(self.flight_keys):
            value = row.get(col)
            if (value is None or value in ("", "-", "nan")) and row.get(f"{col}_R") is not None:
                value = row.get(f"{col}_R")
            self.vals_flight[i].setText(str(value if value is not None else "-"))

        for i, (_, col) in enumerate(self.gps_keys):
            value = row.get(col)
            if (value is None or value in ("", "-", "nan")) and row.get(f"{col}_R") is not None:
                value = row.get(f"{col}_R")
            self.vals_gps[i].setText(str(value if value is not None else "-"))
