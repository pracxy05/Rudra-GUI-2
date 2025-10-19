from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtGui import QGuiApplication
import csv, os, sys, re, numpy as np
from collections import deque

LOG_CSV_PATH = "mission_logs.csv"

LOG_COLORS = {"INFO":"#d6edf9","WARNING":"#FFA726","ERROR":"#E74C3C","CRITICAL":"#B71C1C","ML":"#8e44ad"}
TEXT_COLORS = {"INFO":"#18303a","WARNING":"#222","ERROR":"#fff","CRITICAL":"#fff","ML":"#fff"}

SENSOR_THRESHOLDS = {
    "TEMP":{"min":-10,"max":85,"critical_max":100,"unit":"°C"},
    "HUM":{"min":0,"max":100,"critical_max":100,"unit":"%"},
    "GAS":{"min":0,"max":100,"critical_max":150,"unit":"KΩ"},
    "PRES":{"min":300,"max":1100,"critical_min":200,"critical_max":1200,"unit":"hPa"},
    "ALT":{"min":-500,"max":50000,"critical_max":100000,"unit":"m"},
    "VOLT":{"min":3.0,"max":42.0,"critical_min":2.5,"critical_max":50.0,"unit":"V"},
    "CURR":{"min":-1000,"max":10000,"critical_max":15000,"unit":"mA"},
    "ACC":{"max":50.0,"critical_max":100.0,"unit":"m/s²"},
    "GYRO":{"max":2000,"critical_max":3000,"unit":"°/s"},
    "MAG":{"min":-1000,"max":1000,"critical_max":2000,"unit":"uT"}
}

# Ignore noisy Chromium/GPU lines that aren't actionable
TERMINAL_IGNORE_PATTERNS = (
    "gpu_channel_manager.cc", "GLES3 context", "GLES2", "virtualization", "ContextResult::kFatalFailure"
)

def ml_check(log_type, msg, details):
    keywords = ["anomaly","unexpected","fail","overflow","exception","nan","reset","critical","traceback","syntaxerror"]
    msg_lower = (msg or "").lower() + (details or "").lower()
    if log_type.upper()=="CRITICAL": return True,"Critical error detected"
    for kw in keywords:
        if kw in msg_lower: return True, f"Keyword '{kw}' detected"
    return False,""

def ensure_logfile():
    if not os.path.isfile(LOG_CSV_PATH):
        with open(LOG_CSV_PATH,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow(["Time","Type","Location","Message","Details","ML_Flag","ML_Details"])

def save_log_to_file(row):
    ensure_logfile()
    with open(LOG_CSV_PATH,"a",newline="",encoding="utf-8") as f:
        csv.writer(f).writerow(row)

def current_timestamp():
    return QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")

def safe_float(value, default=0.0):
    if value is None or value=='' or str(value).lower() in ('nan','n/a'): return None
    try: return float(value)
    except (ValueError,TypeError): return default

class SmartThresholdManager:
    def __init__(self, window_size=20, sigma_factor=2.5):
        self.window_size=window_size; self.sigma_factor=sigma_factor
        self.buffers={k:deque(maxlen=window_size) for k in ("TEMP","VOLT","CURR","PRES")}
    def update_and_check(self, key, value):
        if key not in self.buffers or value is None: return None
        buf=self.buffers[key]; buf.append(value)
        if len(buf)<5: return None
        mean=float(np.mean(buf)); std=float(np.std(buf))
        if std==0: return None
        if value>mean+self.sigma_factor*std: return f"{key} anomaly: {value:.2f} above expected (~{mean:.2f} ± {std:.2f})"
        if value<mean-self.sigma_factor*std: return f"{key} anomaly: {value:.2f} below expected (~{mean:.2f} ± {std:.2f})"
        return None

def check_telemetry_thresholds(telemetry_dict):
    logs=[]
    # TEMP
    if 'TEMP' in telemetry_dict or 'temperature' in telemetry_dict:
        temp=safe_float(telemetry_dict.get('TEMP') or telemetry_dict.get('temperature'))
        if temp is not None:
            t=SENSOR_THRESHOLDS['TEMP']
            if temp>t.get('critical_max',100):
                logs.append(("CRITICAL","BME680",f"Temperature critical: {temp}{t['unit']}",f"Exceeded {t.get('critical_max')}{t['unit']}"))
            elif temp>t['max']:
                logs.append(("WARNING","BME680",f"Temperature high: {temp}{t['unit']}",f"Above {t['max']}{t['unit']}"))
            elif temp<t['min']:
                logs.append(("WARNING","BME680",f"Temperature low: {temp}{t['unit']}",f"Below {t['min']}{t['unit']}"))
    # HUM
    if 'HUM' in telemetry_dict or 'humidity' in telemetry_dict:
        hum=safe_float(telemetry_dict.get('HUM') or telemetry_dict.get('humidity'))
        if hum is not None:
            t=SENSOR_THRESHOLDS['HUM']
            if hum>t['max'] or hum<t['min']:
                logs.append(("ERROR","BME680",f"Humidity out of range: {hum}{t['unit']}",f"Valid {t['min']}-{t['max']}{t['unit']}"))
    # PRES
    if 'PRES' in telemetry_dict or 'pressure' in telemetry_dict:
        pres=safe_float(telemetry_dict.get('PRES') or telemetry_dict.get('pressure'))
        if pres is not None:
            t=SENSOR_THRESHOLDS['PRES']
            if pres>t.get('critical_max',1200) or pres<t.get('critical_min',200):
                logs.append(("CRITICAL","BME680/DPS310",f"Pressure critical: {pres}{t['unit']}",f"Outside {t.get('critical_min')}-{t.get('critical_max')}{t['unit']}"))
            elif pres>t['max'] or pres<t['min']:
                logs.append(("WARNING","BME680/DPS310",f"Pressure unusual: {pres}{t['unit']}",f"Expected {t['min']}-{t['max']}{t['unit']}"))
    # VOLT
    if 'VOLT' in telemetry_dict or 'voltage' in telemetry_dict:
        volt=safe_float(telemetry_dict.get('VOLT') or telemetry_dict.get('voltage'))
        if volt is not None:
            t=SENSOR_THRESHOLDS['VOLT']
            if volt<t.get('critical_min',2.5):
                logs.append(("CRITICAL","INA219",f"Battery critically low: {volt}{t['unit']}",f"Min {t.get('critical_min')}{t['unit']}"))
            elif volt>t.get('critical_max',50):
                logs.append(("CRITICAL","INA219",f"Voltage dangerously high: {volt}{t['unit']}",f"Max {t.get('critical_max')}{t['unit']}"))
            elif volt<t['min']:
                logs.append(("WARNING","INA219",f"Battery low: {volt}{t['unit']}",f"Below {t['min']}{t['unit']}"))
    # CURR
    if 'CURR' in telemetry_dict or 'current' in telemetry_dict:
        curr=safe_float(telemetry_dict.get('CURR') or telemetry_dict.get('current'))
        if curr is not None:
            t=SENSOR_THRESHOLDS['CURR']
            if curr>t.get('critical_max',15000):
                logs.append(("CRITICAL","INA219",f"Current overload: {curr}{t['unit']}",f"Exceeds {t.get('critical_max')}{t['unit']}"))
            elif curr>t['max']:
                logs.append(("WARNING","INA219",f"High current draw: {curr}{t['unit']}",f"Above {t['max']}{t['unit']}"))
    # ALT
    if 'ALT' in telemetry_dict or 'altitude' in telemetry_dict:
        alt=safe_float(telemetry_dict.get('ALT') or telemetry_dict.get('altitude'))
        if alt is not None:
            t=SENSOR_THRESHOLDS['ALT']
            if alt>t.get('critical_max',100000):
                logs.append(("ERROR","Altitude",f"Altitude extremely high: {alt}{t['unit']}",f"Exceeds {t.get('critical_max')}{t['unit']}"))
            elif alt<t['min']:
                logs.append(("WARNING","Altitude",f"Negative altitude: {alt}{t['unit']}", "Altitude calculation may be incorrect"))
    # ACC magnitude
    if 'ACC' in telemetry_dict or 'acceleration' in telemetry_dict:
        acc_str=telemetry_dict.get('ACC') or telemetry_dict.get('acceleration','0,0,0')
        if isinstance(acc_str,str):
            try:
                parts=[safe_float(x,0.0) for x in acc_str.split(',')]
                vals=[p for p in parts if p is not None]
                mag=(sum(x*x for x in vals)**0.5) if vals else 0.0
                t=SENSOR_THRESHOLDS['ACC']
                if mag>t.get('critical_max',100.0):
                    logs.append(("CRITICAL","BNO055",f"Extreme acceleration: {mag:.2f}{t['unit']}",f"Exceeds {t.get('critical_max')}{t['unit']}"))
                elif mag>t['max']:
                    logs.append(("WARNING","BNO055",f"High acceleration: {mag:.2f}{t['unit']}",f"Above {t['max']}{t['unit']}"))
            except Exception:
                pass
    # GPS
    if 'GPS_RAW' in telemetry_dict or 'gps' in telemetry_dict:
        gps=telemetry_dict.get('GPS_RAW') or telemetry_dict.get('gps','')
        if not gps.strip():
            logs.append(("INFO","GPS","GPS searching for fix","No GPS signal acquired yet"))
    # NaN scan
    for key,value in telemetry_dict.items():
        if isinstance(value,str) and value.lower()=="nan":
            logs.append(("WARNING",f"Sensor:{key}",f"Invalid reading: {key}=nan","Possible sensor fault"))
    return logs

class LogMessage(QFrame):
    def __init__(self, log_data):
        super().__init__()
        self.expanded=False
        self.log_data=log_data
        self.short_text=log_data["Message"]
        self.full_text=log_data.get("Details") or self.short_text
        log_type=log_data["Type"].upper()
        color=LOG_COLORS.get(log_type,"#eeeeee"); textcol=TEXT_COLORS.get(log_type,"#242424")
        if log_data.get("ML_Flag"): color, textcol = LOG_COLORS["ML"], TEXT_COLORS["ML"]
        self.setStyleSheet(f"QFrame {{ background:{color}; border-radius:11px; border:2px solid #bbb; margin:8px 2px; }}")
        col=QHBoxLayout(self); col.setContentsMargins(11,8,11,8); col.setSpacing(18)
        tlabel=QLabel(log_data["Time"]); tlabel.setStyleSheet(f"color:{textcol}; font-size:13px; font-weight:600; min-width:114px;")
        col.addWidget(tlabel,0)
        lloc=QLabel(log_data['Location']); lloc.setStyleSheet(f"color:{textcol}; font-size:14px; font-weight:600; min-width:107px;")
        col.addWidget(lloc,0)
        mcol=QVBoxLayout(); mrow=QHBoxLayout()
        badge=QLabel(log_type)
        badgebg={"INFO":"#7ac3fa","WARNING":"#fd9d00","ERROR":"#c90a1a","CRITICAL":"#880014","ML":"#461f6b"}.get(log_type,"#ccc")
        badge.setStyleSheet(f"color:white; background:{badgebg}; border-radius:6px; padding:2.5px 11px; margin-right:12px; font-size:13.8px; font-weight:bold;")
        mrow.addWidget(badge,0)
        self.msg_label=QLabel(self.short_text); self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet("color:#000; font-size:14px; font-weight:600; background:rgba(255,255,255,0.85); border-radius:5px; padding:4px 6px;")
        mrow.addWidget(self.msg_label,1)
        self.btn_toggle=QPushButton("⮞"); self.btn_toggle.setFixedSize(22,22)
        self.btn_toggle.setStyleSheet("background:transparent; border:none; color:#555; font-size:15px;")
        self.btn_toggle.clicked.connect(self.toggle_expand); mrow.addWidget(self.btn_toggle,0)
        close_btn=QPushButton("×"); close_btn.setFixedSize(22,22)
        close_btn.setStyleSheet("background:transparent; border:none; color:#aaa; font-size:15px;")
        close_btn.clicked.connect(self.delete_self); mrow.addWidget(close_btn,0)
        mcol.addLayout(mrow)
        self.details_area=QLabel()
        self.details_area.setStyleSheet("color:#26235f; font-size:13px; background:rgba(255,255,255,0.7); border-radius:6px; padding:5px 9px; margin-top:6px;")
        self.details_area.setWordWrap(True); self.details_area.setVisible(False); mcol.addWidget(self.details_area)
        if log_data.get("ML_Flag"):
            mlb=QLabel("ML⚡"); mlb.setStyleSheet("font-weight:bold; color:#fff; background:#8769e8; padding:2px 10px; border-radius:7px; margin-left:8px; font-size:14px;")
            mrow.addWidget(mlb,0)
        col.addLayout(mcol,2); self.setMaximumHeight(80)
    def toggle_expand(self):
        show=not self.details_area.isVisible()
        self.details_area.setVisible(show); self.btn_toggle.setText("⮟" if show else "⮞")
        self.details_area.setText(self.full_text if show else ""); self.setMaximumHeight(180 if show else 80)
    def delete_self(self): self.setVisible(False)

class LogTab(QWidget):
    telemetry_received = Signal(dict)
    health_changed = Signal(int, str)  # 0,1,2

    def __init__(self):
        super().__init__()
        ensure_logfile()

        layout=QVBoxLayout(self)
        topbar=QHBoxLayout()

        title=QLabel("MISSION LOGS")
        title.setStyleSheet("font-weight:bold; letter-spacing:1px; font-size:17px; color:#2c2233;")
        topbar.addWidget(title,0)

        self.filter_box=QComboBox()
        self.filter_box.addItems(["ALL","INFO","WARNING","ERROR","CRITICAL","ML"])
        self.filter_box.setFixedHeight(32)
        self.filter_box.setStyleSheet("""
            QComboBox{background:#fff;border:2px solid #c4c4d4; border-radius:7px; font-size:15px;min-width:112px; padding:4px 26px 4px 12px; color:#212;}
            QComboBox:drop-down{width:28px;border:transparent;}
            QComboBox QAbstractItemView{selection-background-color:#e1f2ff; font-size:15px; color:#1c1c1c;}
            QComboBox::item:selected{background:#f6b060;color:black;}
        """)
        self.filter_box.currentIndexChanged.connect(self.filter_changed)
        topbar.addWidget(self.filter_box,0)

        topbar.addStretch(1)

        self.download_btn=QPushButton("DOWNLOAD")
        self.download_btn.setFixedHeight(32)
        self.download_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#2a2849; font-size:15px; padding:6px 14px;")
        self.download_btn.clicked.connect(self.download_log)
        topbar.addWidget(self.download_btn,0)

        self.pause_btn=QPushButton("PAUSE")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setFixedHeight(32)
        self.pause_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#6b6b6b; font-size:15px; padding:6px 14px;")
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        topbar.addWidget(self.pause_btn,0)

        self.refresh_btn=QPushButton("REFRESH")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#2a2849; font-size:15px; padding:6px 14px;")
        self.refresh_btn.clicked.connect(self.refresh_logs)
        topbar.addWidget(self.refresh_btn,0)

        self.trash_btn=QPushButton("🗑")
        self.trash_btn.setFixedHeight(32)
        self.trash_btn.setStyleSheet("background:#f6f6f7; border-radius:8px; color:#d73a17; font-size:15px;")
        self.trash_btn.clicked.connect(self.clear_logs)
        topbar.addWidget(self.trash_btn,0)

        layout.addLayout(topbar)

        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.msg_wrap=QWidget()
        self.msg_layout=QVBoxLayout(self.msg_wrap)
        self.msg_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.msg_wrap)
        layout.addWidget(self.scroll,1)
        self.setLayout(layout)

        self.log_data=[]
        self.smart_manager=SmartThresholdManager()
        self.paused=False
        self.add_log("INFO","LogTab","Log system initialized","Ready to monitor telemetry data")

        # Terminal capture proxies (always on; no UI toggle)
        self._orig_stdout=sys.stdout; self._orig_stderr=sys.stderr
        self._stdout_buf=""; self._stderr_buf=""
        sys.stdout = self._StreamProxy(self._on_stdout_text, self._orig_stdout)
        sys.stderr = self._StreamProxy(self._on_stderr_text, self._orig_stderr)

    class _StreamProxy:
        def __init__(self, on_text, original): self.on_text=on_text; self.original=original
        def write(self, text):
            try: self.original.write(text)
            except Exception: pass
            self.on_text(text)
        def flush(self):
            try: self.original.flush()
            except Exception: pass

    def _on_pause_toggled(self, checked):
        self.paused = bool(checked)
        self.pause_btn.setText("PLAY" if self.paused else "PAUSE")

    # stdout lines
    def _on_stdout_text(self, text):
        self._stdout_buf += text
        while "\n" in self._stdout_buf:
            line, self._stdout_buf = self._stdout_buf.split("\n",1)
            s=line.strip()
            if not s or self._ignore_terminal(s): continue
            if not self.paused:
                level = self._level_from_terminal(s, default="INFO")
                self.add_log(level, "Terminal", s, s)

    # stderr lines
    def _on_stderr_text(self, text):
        self._stderr_buf += text
        while "\n" in self._stderr_buf:
            line, self._stderr_buf = self._stderr_buf.split("\n",1)
            s=line.strip()
            if not s or self._ignore_terminal(s): continue
            if not self.paused:
                level = self._level_from_terminal(s, default="ERROR")
                self.add_log(level, "Terminal", s, s)

    def _ignore_terminal(self, s: str) -> bool:
        low=s.lower()
        return any(pat.lower() in low for pat in TERMINAL_IGNORE_PATTERNS)

    def _level_from_terminal(self, s: str, default="INFO") -> str:
        low=s.lower()
        if "traceback" in low or "syntaxerror" in low or "unexpected character" in low:
            return "ERROR"
        if "fatal" in low or "critical" in low:
            return "CRITICAL"
        if "warn" in low:
            return "WARNING"
        return default

    # Telemetry path
    def process_telemetry(self, telemetry_dict: dict):
        if self.paused:
            return
        sev=0; reason="Nominal"
        for log_type, location, message, details in check_telemetry_thresholds(telemetry_dict):
            self.add_log(log_type, location, message, details)
            if log_type=="CRITICAL": sev,reason = 2,message
            elif sev<1 and log_type in ("WARNING","ERROR"): sev,reason = 1,message
        for key in ("TEMP","VOLT","CURR","PRES"):
            val = safe_float(telemetry_dict.get(key))
            msg = self.smart_manager.update_and_check(key, val)
            if msg:
                self.add_log("ML", key, msg, "Smart threshold anomaly detected")
                if sev<1: sev,reason = 1, f"{key} anomaly"
        self.health_changed.emit(sev, reason)

    # UI helpers
    def add_log(self, log_type, location, message, details=None):
        details = details or message
        ts = current_timestamp()
        ml_flag, ml_details = ml_check(log_type, message, details)
        entry = {"Time":ts,"Type":log_type.upper(),"Location":location,"Message":message,
                 "Details":details,"ML_Flag":ml_flag,"ML_Details":ml_details}
        save_log_to_file([entry["Time"],entry["Type"],entry["Location"],entry["Message"],entry["Details"],int(ml_flag),ml_details])
        self.log_data.append(entry)
        self.refresh_logs()

    def clear_logs(self):
        while self.msg_layout.count():
            w=self.msg_layout.itemAt(0).widget()
            if w: w.deleteLater()
            self.msg_layout.takeAt(0)
        self.log_data=[]
        ensure_logfile()
        with open(LOG_CSV_PATH,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow(["Time","Type","Location","Message","Details","ML_Flag","ML_Details"])
        self.add_log("INFO","LogTab","Logs cleared","All previous logs have been removed")

    def download_log(self):
        dlg = QFileDialog()
        save_path,_ = dlg.getSaveFileName(self,"Save Logs","mission_logs.csv","CSV Files (*.csv)")
        if save_path:
            ensure_logfile()
            with open(LOG_CSV_PATH,"r",encoding="utf-8") as src, open(save_path,"w",encoding="utf-8") as dst:
                dst.write(src.read())

    def filter_changed(self):
        self.refresh_logs()

    def refresh_logs(self):
        while self.msg_layout.count():
            w=self.msg_layout.itemAt(0).widget()
            if w: w.deleteLater()
            self.msg_layout.takeAt(0)
        mode=self.filter_box.currentText()
        for log in self.log_data:
            t=log["Type"]; is_ml=log.get("ML_Flag")
            if mode=="ALL" or (mode=="ML" and is_ml) or (mode==t):
                self.msg_layout.addWidget(LogMessage(log))
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
