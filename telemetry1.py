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
        for widget in [self.lbl_conn, self.lbl_time, self.lbl_pack]: right_vals.addWidget(widget)
        conn_layout.addLayout(left_labels)
        conn_layout.addLayout(right_vals)
        conn_block.setLayout(conn_layout)
        main_layout.addWidget(conn_block)

        # FLIGHT PANEL - MAPS DIRECTLY TO COLUMN NAMES
        flight_block = QFrame()
        flight_block.setStyleSheet(block_style)
        flight_layout, l1, l2 = QHBoxLayout(), QVBoxLayout(), QVBoxLayout()
        flight_keys = [
            ("Altitude", "Altitude_m"),
            ("Acceleration", "Accel_m_s2"),
            ("Temperature", "Temp_C"),
            ("Pressure", "Pressure_Pa"),
            ("Battery", "Battery_pct"),
            ("Comm", "Comm_pct")
        ]
        for txt, _ in flight_keys: l1.addWidget(self._keybox(f"{txt.upper()}:"))
        self.vals_flight = [self._valbox("-") for _ in flight_keys]
        for widget in self.vals_flight: l2.addWidget(widget)
        flight_layout.addLayout(l1)
        flight_layout.addLayout(l2)
        flight_block.setLayout(flight_layout)
        main_layout.addWidget(flight_block)
        self.flight_keys = flight_keys  # (label, csv key) for live update

        # GPS PANEL - ALSO MAPS COLUMN NAMES
        gps_block = QFrame()
        gps_block.setStyleSheet(block_style)
        gps_layout, l3, l4 = QHBoxLayout(), QVBoxLayout(), QVBoxLayout()
        gps_keys = [
            ("GPS Alt", "GPS_Alt_m"),
            ("Latitude", "Latitude_deg"),
            ("Longitude", "Longitude_deg"),
            ("Velocity", "Velocity_m_s"),
            ("Comm Redundant", "Comm_R_pct")
        ]
        for txt, _ in gps_keys: l3.addWidget(self._keybox(f"{txt.upper()}:"))
        self.vals_gps = [self._valbox("-") for _ in gps_keys]
        for widget in self.vals_gps: l4.addWidget(widget)
        gps_layout.addLayout(l3)
        gps_layout.addLayout(l4)
        gps_block.setLayout(gps_layout)
        main_layout.addWidget(gps_block)
        self.gps_keys = gps_keys  # for update

        main_layout.addStretch()
        nav_outer = QFrame()
        nav_outer.setStyleSheet(
            """
            QFrame { border: 2px solid #bbb; border-radius: 14px; background-color: #d4d7db; margin-top: 12px; }
            """
        )
        nav_grid = QGridLayout(); nav_grid.setSpacing(6)
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
        if color: style += f"color:{color}; font-weight:bold;"
        lbl.setStyleSheet(style)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    # Runtime update method, call this with a dataframe row
    def update_telemetry(self, row):
        for i, (_, col) in enumerate(self.flight_keys):
            self.vals_flight[i].setText(str(row.get(col, "-")))
        for i, (_, col) in enumerate(self.gps_keys):
            self.vals_gps[i].setText(str(row.get(col, "-")))
