from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, QDateTime
import csv
import os
import sys

LOG_CSV_PATH = "mission_logs.csv"

LOG_COLORS = {
    "INFO": "#d6edf9",
    "WARNING": "#FFA726",
    "ERROR": "#E74C3C",
    "CRITICAL": "#B71C1C",
    "ML": "#8e44ad"
}
TEXT_COLORS = {
    "INFO": "#18303a",
    "WARNING": "#222",
    "ERROR": "#fff",
    "CRITICAL": "#fff",
    "ML": "#fff"
}


def ml_check(log_type, msg, details):
    keywords = ["anomaly", "unexpected", "fail", "overflow", "exception", "nan", "reset"]
    msg_lower = (msg or "").lower() + (details or "").lower()
    if log_type.upper() == "CRITICAL":
        return True, "Critical error"
    for kw in keywords:
        if kw in msg_lower:
            return True, f"Keyword '{kw}'"
    return False, ""


def ensure_logfile():
    if not os.path.isfile(LOG_CSV_PATH):
        with open(LOG_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Time", "Type", "Location", "Message", "Details", "ML_Flag", "ML_Details"])


def save_log_to_file(row):
    ensure_logfile()
    with open(LOG_CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def current_timestamp():
    return QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")


class LogMessage(QFrame):
    def __init__(self, log_data):
        super().__init__()
        self.expanded = False
        self.log_data = log_data
        self.short_text = log_data["Message"]
        self.full_text = log_data.get("Details") or self.short_text

        log_type = log_data["Type"].upper()
        color = LOG_COLORS.get(log_type, "#eeeeee")
        textcol = TEXT_COLORS.get(log_type, "#242424")
        if log_data.get("ML_Flag"):
            color, textcol = LOG_COLORS["ML"], TEXT_COLORS["ML"]

        self.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border-radius: 11px;
                border: 2px solid #bbb;
                margin: 8px 2px;
            }}
        """)

        column = QHBoxLayout(self)
        column.setContentsMargins(11, 8, 11, 8)
        column.setSpacing(18)

        # Time column
        time_label = QLabel(log_data["Time"])
        time_label.setStyleSheet(f"color: {textcol}; font-size:13px; font-weight:600; min-width:114px;")
        column.addWidget(time_label, 0)

        # Location column
        loc_label = QLabel(log_data['Location'])
        loc_label.setStyleSheet(f"color: {textcol}; font-size:14px; font-weight:600; min-width:107px;")
        column.addWidget(loc_label, 0)

        # Message/Details column
        message_col = QVBoxLayout()
        message_row = QHBoxLayout()

        # Type badge
        type_badge = QLabel(log_type)
        badge_bg = {
            "INFO": "#7ac3fa", "WARNING": "#fd9d00",
            "ERROR": "#c90a1a", "CRITICAL": "#880014", "ML": "#461f6b"
        }.get(log_type, "#ccc")
        type_badge.setStyleSheet(
            f"color:white; background:{badge_bg}; border-radius:6px; padding:2.5px 11px; margin-right:12px; font-size:13.8px; font-weight:bold;")
        message_row.addWidget(type_badge, 0)

        # Main message in visible white box
        self.msg_label = QLabel(self.short_text)
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet(
            "color:#000;"
            "font-size:14px; font-weight:600;"
            "background:rgba(255,255,255,0.85);"
            "border-radius:5px;"
            "padding:4px 6px;"
        )
        message_row.addWidget(self.msg_label, 1)

        # Toggle details button
        self.btn_toggle = QPushButton("⮞")
        self.btn_toggle.setFixedSize(22, 22)
        self.btn_toggle.setStyleSheet("background:transparent; border:none; color:#555; font-size:15px;")
        self.btn_toggle.clicked.connect(self.toggle_expand)
        message_row.addWidget(self.btn_toggle, 0)

        # Remove button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("background:transparent; border:none; color:#aaa; font-size:15px;")
        close_btn.clicked.connect(self.delete_self)
        message_row.addWidget(close_btn, 0)

        message_col.addLayout(message_row)

        # Details below if expanded
        self.details_area = QLabel()
        self.details_area.setStyleSheet(
            "color:#26235f; font-size:13px; background:rgba(255,255,255,0.7); border-radius:6px; padding:5px 9px; margin-top:6px;"
        )
        self.details_area.setWordWrap(True)
        self.details_area.setVisible(False)
        message_col.addWidget(self.details_area)

        # ML badge if present
        if log_data.get("ML_Flag"):
            ml_badge = QLabel("ML⚡")
            ml_badge.setStyleSheet(
                "font-weight: bold; color: #fff; background:#8769e8; padding:2px 10px; border-radius:7px; margin-left:8px; font-size:14px;"
            )
            message_row.addWidget(ml_badge, 0)

        column.addLayout(message_col, 2)
        self.setMaximumHeight(80)  # Increased default height for visibility

    def toggle_expand(self):
        if self.expanded:
            self.details_area.setVisible(False)
            self.btn_toggle.setText("⮞")
            self.setMaximumHeight(80)
        else:
            self.details_area.setText(self.full_text)
            self.details_area.setVisible(True)
            self.btn_toggle.setText("⮟")
            self.setMaximumHeight(180)
        self.expanded = not self.expanded

    def delete_self(self):
        self.setVisible(False)


class LogTab(QWidget):
    def __init__(self):
        super().__init__()
        ensure_logfile()
        layout = QVBoxLayout(self)
        topbar = QHBoxLayout()

        log_label = QLabel("MISSION LOGS")
        log_label.setStyleSheet("font-weight: bold; letter-spacing:1px; font-size:17px; color:#2c2233;")
        topbar.addWidget(log_label, 0)

        # Filter dropdown
        self.filter_box = QComboBox()
        self.filter_box.addItems(["ALL", "INFO", "WARNING", "ERROR", "CRITICAL", "ML"])
        self.filter_box.setFixedHeight(32)
        self.filter_box.setStyleSheet("""
            QComboBox{background:#fff;border:2px solid #c4c4d4; border-radius:7px; font-size:15px;min-width:112px; padding:4px 26px 4px 12px; color:#212;text-align:left;}
            QComboBox:drop-down{width:28px;border:transparent;}
            QComboBox QAbstractItemView{selection-background-color:#e1f2ff; font-size:15px; color:#1c1c1c;}
            QComboBox::item:selected{background:#f6b060;color:black;}
        """)
        self.filter_box.currentIndexChanged.connect(self.filter_changed)
        topbar.addWidget(self.filter_box, 0)
        topbar.addStretch(1)

        # Reload, Download, Trash buttons
        self.reload_btn = QPushButton("RELOAD")
        self.reload_btn.setFixedHeight(32)
        self.reload_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#006699; font-size:15px; padding:6px 14px;")
        self.reload_btn.clicked.connect(self.load_logs_from_file)
        topbar.addWidget(self.reload_btn, 0)

        self.download_btn = QPushButton("DOWNLOAD LOG")
        self.download_btn.setFixedHeight(32)
        self.download_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#2a2849; font-size:15px; padding:6px 14px;")
        self.download_btn.clicked.connect(self.download_log)
        topbar.addWidget(self.download_btn, 0)

        self.trash_btn = QPushButton("🗑")
        self.trash_btn.setFixedHeight(32)
        self.trash_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#d73a17; font-size:15px;")
        self.trash_btn.clicked.connect(self.clear_logs)
        topbar.addWidget(self.trash_btn, 0)

        layout.addLayout(topbar)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.msg_wrap = QWidget()
        self.msg_layout = QVBoxLayout(self.msg_wrap)
        self.msg_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.msg_wrap)
        layout.addWidget(self.scroll, 1)
        self.setLayout(layout)

        self.log_data = []
        sys.stderr = self

        # Load logs from file
        self.load_logs_from_file()

    def write(self, text):
        if text.strip():
            self.add_log("ERROR", "Terminal", text.strip(), details=text.strip())

    def flush(self):
        pass

    def add_log(self, log_type, location, message, details=None):
        details = details or message
        timestamp = current_timestamp()
        ml_flag, ml_details = ml_check(log_type, message, details)
        entry = {
            "Time": timestamp,
            "Type": log_type.upper(),
            "Location": location,
            "Message": message,
            "Details": details,
            "ML_Flag": ml_flag,
            "ML_Details": ml_details
        }
        save_log_to_file([entry["Time"], entry["Type"], entry["Location"], entry["Message"], entry["Details"], int(ml_flag), ml_details])
        self.log_data.append(entry)
        self.refresh_logs()

    def load_logs_from_file(self):
        ensure_logfile()
        self.log_data = []
        try:
            with open(LOG_CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entry = {
                        "Time": row["Time"],
                        "Type": row["Type"],
                        "Location": row["Location"],
                        "Message": row["Message"],
                        "Details": row["Details"],
                        "ML_Flag": row["ML_Flag"] in ("1", "True", "true"),
                        "ML_Details": row["ML_Details"]
                    }
                    self.log_data.append(entry)
            print("✅ Loaded logs:", self.log_data)
        except Exception as e:
            print("⚠️ Error loading logs:", e)
        self.refresh_logs()

    def clear_logs(self):
        while self.msg_layout.count():
            w = self.msg_layout.itemAt(0).widget()
            if w:
                w.deleteLater()
            self.msg_layout.takeAt(0)
        self.log_data = []
        ensure_logfile()
        with open(LOG_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Time", "Type", "Location", "Message", "Details", "ML_Flag", "ML_Details"])

    def download_log(self):
        dlg = QFileDialog()
        save_path, _ = dlg.getSaveFileName(self, "Save Logs", "mission_logs.csv", "CSV Files (*.csv)")
        if save_path:
            ensure_logfile()
            with open(LOG_CSV_PATH, "r", encoding="utf-8") as src, open(save_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())

    def filter_changed(self):
        self.refresh_logs()

    def refresh_logs(self):
        while self.msg_layout.count():
            w = self.msg_layout.itemAt(0).widget()
            if w:
                w.deleteLater()
            self.msg_layout.takeAt(0)
        filter_mode = self.filter_box.currentText()
        for log in self.log_data:
            t = log["Type"]
            is_ml = log.get("ML_Flag")
            if filter_mode == "ALL":
                self.msg_layout.addWidget(LogMessage(log))
            elif filter_mode == "ML" and is_ml:
                self.msg_layout.addWidget(LogMessage(log))
            elif filter_mode == t:
                self.msg_layout.addWidget(LogMessage(log))
        scrollbar = self.scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
