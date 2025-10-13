# cockpit_tab.py
# Robust Cockpit tab — Plotly gauges (live JS updates), altitude cylinder with rocket,
# compact camera boxes with upload/play/pause/restart/expand icons, and defensive error handling.
#
# Exposes: CockpitWidget, CockpitFloatingWindow
# Default rocket path: r"C:\MERN_TT\assets\rocket.png"

import os
import sys
import math
import time
import tempfile
from pathlib import Path

# In some environments QtWebEngine's GPU causes repeated errors; disabling GPU can help.
# If you prefer GPU, remove the next line.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QRectF
from PySide6.QtGui import (
    QPixmap, QImage, QColor, QPainter, QFont, QPen, QBrush, QLinearGradient
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QScrollArea, QSizePolicy, QPushButton, QDialog, QApplication, QFileDialog
)

# WebEngine (Plotly) — optional fallback handled below
_HAS_WEBENGINE = True
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception as e:
    print("Warning: QWebEngineView import failed:", e)
    _HAS_WEBENGINE = False

# Multimedia (optional)
_USE_MULTIMEDIA = True
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception as e:
    print("Multimedia not available:", e)
    _USE_MULTIMEDIA = False

# OpenCV optional support for camera frames
_HAS_CV2 = True
try:
    import cv2
except Exception:
    _HAS_CV2 = False

# ---------------- Helper / safe decorator ----------------
def safe(func):
    """Wrap UI critical methods to prevent uncaught exceptions from crashing paintEvent loops."""
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception in {func.__name__}: {e}")
            return None
    return wrapped

# ---------------- Plotly HTML generator ----------------
def make_plotly_gauge_html(title, min_v, max_v, init_v, bar_color="#2B84D6", text_color="#e6eef8"):
    """
    Returns full HTML string embedding a Plotly indicator and an `updateGauge(value)` JS function.
    We'll load this HTML via QWebEngineView.setHtml and update via runJavaScript.
    """
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    html,body{{margin:0;height:100%;background:transparent}}
    #g{{width:100%;height:100%;}}
    .plotly .modebar{{display:none !important;}}
  </style>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
  <div id="g"></div>
  <script>
    var data = [{{
      type: "indicator",
      mode: "gauge+number",
      value: {float(init_v)},
      title: {{ text: "{title}", font: {{size:16, color: "{text_color}"}} }},
      number: {{ font: {{ size:18, color: "{text_color}" }} }},
      gauge: {{
        axis: {{ range: [{min_v}, {max_v}], tickcolor: "#aab3bf", nticks: 6 }},
        bar: {{ color: "{bar_color}" }},
        bgcolor: "rgba(0,0,0,0)",
        borderwidth: 0,
        steps: [
          {{range: [{min_v}, {(min_v + max_v) / 2}], color: "rgba(0,128,255,0.08)"}},
          {{range: [{(min_v + max_v) / 2}, {(min_v + max_v) * 0.85}], color: "rgba(0,128,255,0.05)"}},
          {{range: [{(min_v + max_v) * 0.85}, {max_v}], color: "rgba(255,80,80,0.06)"}}
        ],
        threshold: {{ value: {max_v * 0.92}, line: {{color: "red", width: 3}}, thickness: 0.75 }}
      }}
    }}];
    var layout = {{
      margin: {{ l:8, r:8, t:14, b:8 }},
      paper_bgcolor: "rgba(0,0,0,0)",
      font: {{ family: "Segoe UI", color: "{text_color}" }},
      height: 180
    }};
    Plotly.newPlot('g', data, layout, {{displayModeBar:false, responsive:true}});

    window.updateGauge = function(v) {{
      try {{
        var val = Number(v) || 0;
        Plotly.restyle('g', {{ 'value': [[val]] }}, [0]);
      }} catch(e) {{
        console.error("updateGauge:", e);
      }}
    }};
  </script>
</body>
</html>
"""
    return html

# ---------------- Altitude cylinder (QPainter) ----------------
class AltitudeCylinder(QWidget):
    def __init__(self, max_alt=1500, rocket_path=None, parent=None):
        super().__init__(parent)
        print("AltitudeCylinder: init (rocket_path=%r)" % rocket_path)
        self.max_alt = float(max_alt)
        self.alt = 0.0
        self.rocket_path = rocket_path
        self._rocket = None
        if self.rocket_path and os.path.exists(self.rocket_path):
            try:
                self._rocket = QPixmap(self.rocket_path)
            except Exception as e:
                print("AltitudeCylinder: failed to load rocket image:", e)
                self._rocket = None
        else:
            self._rocket = None

        self.setMinimumSize(120, 420)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.title_font = QFont("Segoe UI", 11, QFont.Bold)
        self.value_font = QFont("Consolas", 14, QFont.Bold)

    def setAltitude(self, value):
        try:
            v = float(value)
        except Exception:
            v = 0.0
        self.alt = max(0.0, min(self.max_alt, v))
        self.update()

    @safe
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        # background panel
        p.fillRect(r, QColor("#131619"))

        pad = 10
        inner = r.adjusted(pad, pad, -pad, -pad)
        p.setPen(QPen(QColor("#2b3136"), 1.2))
        p.setBrush(QBrush(QColor("#0f1113")))
        p.drawRoundedRect(inner, 12, 12)

        left = inner.left() + 12
        right = inner.right() - 12
        top = inner.top() + 24
        bottom = inner.bottom() - 38
        width = right - left
        height = bottom - top

        # track
        p.setBrush(QBrush(QColor("#0a0c0e")))
        p.setPen(QPen(QColor("#23282c"), 1.0))
        p.drawRoundedRect(left, top, width, height, 8, 8)

        # fill gradient
        ratio = (self.alt / self.max_alt) if self.max_alt > 0 else 0.0
        fill_h = max(6, height * ratio)
        fill_y = bottom - fill_h
        grad = QLinearGradient(left, fill_y, left, bottom)
        grad.setColorAt(0.0, QColor("#4fd2ff"))
        grad.setColorAt(1.0, QColor("#006b96"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        draw_h = fill_h - 6 if fill_h > 12 else fill_h
        p.drawRoundedRect(left + 6, fill_y + 6, width - 12, draw_h, 6, 6)

        # ticks + numbers
        p.setPen(QPen(QColor("#9aa0a6"), 1.0))
        p.setFont(QFont("Consolas", 9))
        ticks = 6
        for i in range(ticks):
            frac = i / (ticks - 1)
            y = bottom - frac * height
            p.drawLine(right + 6, int(y), right + 20, int(y))
            val = int(round(frac * self.max_alt))
            p.drawText(right + 24, int(y - 8), 40, 16, Qt.AlignLeft | Qt.AlignVCenter, str(val))

        # rocket icon (if available)
        if self._rocket:
            rp_w = min(36, int(width * 0.5))
            rp_h = rp_w
            rocket_y = int(bottom - fill_h - rp_h / 2)
            rocket_x = int(left + width / 2 - rp_w / 2)
            rocket_y = max(top + 4, min(rocket_y, bottom - rp_h - 4))
            p.drawPixmap(rocket_x, rocket_y, rp_w, rp_h, self._rocket)

        # title & numeric
        p.setPen(QPen(QColor("#e6eef8")))
        p.setFont(self.title_font)
        p.drawText(left, inner.top() + 6, width, 20, Qt.AlignCenter, "Altitude")
        p.setFont(self.value_font)
        p.drawText(left, inner.bottom() - 34, width, 28, Qt.AlignCenter, f"{int(self.alt)} m")
        p.end()

# ---------------- CameraBox (small icon controls) ----------------
class CameraBox(QFrame):
    def __init__(self, title="Camera", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame { background: #0f1113; border:1px solid #2a2f34; border-radius:10px; }
            QLabel#title { color: #dfe9f2; font: 10pt 'Segoe UI'; padding-left:6px; }
            QLabel#view { background: #000000; border-radius:8px; }
            QPushButton { background: transparent; color: #a6c8ff; border: 1px solid #2a3b56; border-radius:6px; padding:2px; }
            QPushButton:hover { background: #1b2630; }
        """)
        self.setMinimumSize(320, 220)
        self.current_file = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("title")
        title_lbl.setFixedHeight(22)
        layout.addWidget(title_lbl)

        self.view = QLabel()
        self.view.setObjectName("view")
        self.view.setMinimumSize(300, 160)
        self.view.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.view)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        # small icon buttons
        self.upload_btn = QPushButton("⬆")
        self.upload_btn.setToolTip("Upload")
        self.upload_btn.setFixedSize(36, 28)
        self.upload_btn.clicked.connect(self._on_upload)
        ctrl_row.addWidget(self.upload_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setToolTip("Play")
        self.play_btn.setFixedSize(36, 28)
        self.play_btn.clicked.connect(self._on_play)
        ctrl_row.addWidget(self.play_btn)

        self.pause_btn = QPushButton("⏸")
        self.pause_btn.setToolTip("Pause")
        self.pause_btn.setFixedSize(36, 28)
        self.pause_btn.clicked.connect(self._on_pause)
        ctrl_row.addWidget(self.pause_btn)

        self.restart_btn = QPushButton("🔁")
        self.restart_btn.setToolTip("Restart")
        self.restart_btn.setFixedSize(36, 28)
        self.restart_btn.clicked.connect(self._on_restart)
        ctrl_row.addWidget(self.restart_btn)

        ctrl_row.addStretch()

        self.expand_btn = QPushButton("⛶")
        self.expand_btn.setToolTip("Expand")
        self.expand_btn.setFixedSize(36, 28)
        self.expand_btn.clicked.connect(self._open_expanded)
        ctrl_row.addWidget(self.expand_btn)

        layout.addLayout(ctrl_row)

        # Optional multimedia playback
        self.player = None
        self.video_widget = None
        if _USE_MULTIMEDIA:
            try:
                self.player = QMediaPlayer(self)
                self.audio_output = QAudioOutput(self)
                self.player.setAudioOutput(self.audio_output)
                self.video_widget = QVideoWidget(self)
                self.video_widget.setMinimumSize(300, 160)
            except Exception as e:
                print("CameraBox multimedia init failed:", e)
                self.player = None
                self.video_widget = None

    def _on_upload(self):
        file, _ = QFileDialog.getOpenFileName(self, "Choose video file", "", "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if not file:
            return
        self.current_file = file
        print("CameraBox: selected", file)
        if self.player and self.video_widget:
            parent_layout = self.layout()
            parent_layout.replaceWidget(self.view, self.video_widget)
            self.view.hide()
            self.video_widget.show()
            self.player.setSource(QUrl.fromLocalFile(file))
        else:
            pix = QPixmap(self.view.size())
            pix.fill(QColor("#070809"))
            painter = QPainter(pix)
            painter.setPen(QColor("#bfe1ff"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(pix.rect(), Qt.AlignCenter, os.path.basename(file))
            painter.end()
            self.view.setPixmap(pix)

    def _on_play(self):
        if self.player and self.current_file:
            self.player.play()
        else:
            print("CameraBox: play - no player/file")

    def _on_pause(self):
        if self.player and self.current_file:
            self.player.pause()
        else:
            print("CameraBox: pause - no player/file")

    def _on_restart(self):
        if self.player and self.current_file:
            self.player.stop()
            QTimer.singleShot(120, lambda: self.player.play())
        else:
            print("CameraBox: restart - no player/file")

    def update_frame(self, frame_bgr):
        """Accepts OpenCV BGR frame if cv2 available."""
        if not _HAS_CV2 or frame_bgr is None:
            blank = QPixmap(self.view.size())
            blank.fill(QColor("#000000"))
            self.view.setPixmap(blank)
            return
        try:
            h, w = frame_bgr.shape[:2]
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            bytes_per_line = 3 * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.view.setPixmap(pix)
        except Exception as e:
            print("CameraBox.update_frame error:", e)

    def _open_expanded(self):
        dlg = QDialog(self.window())
        dlg.setWindowTitle("Camera - Expanded")
        dlg.setModal(True)
        v = QVBoxLayout(dlg)
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        if self.view.pixmap():
            label.setPixmap(self.view.pixmap().scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            empty = QPixmap(800, 600)
            empty.fill(QColor("#000000"))
            label.setPixmap(empty)
        v.addWidget(label)
        dlg.resize(900, 700)
        dlg.exec()

# ---------------- CockpitWidget (assembled) ----------------
class CockpitWidget(QWidget):
    def __init__(self, parent=None, rocket_path=r"C:\MERN_TT\assets\rocket.png"):
        super().__init__(parent)
        print("CockpitWidget: initializing")
        self.rocket_path = rocket_path
        self.setStyleSheet("background: #131619; color: #e6eef8; font-family: 'Segoe UI';")
        self._init_ui()

        # Demo telemetry timer (replace with real wiring)
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(300)

        self._demo_state = {"t": 15.0, "p": 1013.25, "a": 0.0, "alt": 100.0}
        self._primary_sensor_ok = True

        print("CockpitWidget: initialized")

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)

        grid = QGridLayout(content)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        # Left column: Plotly gauges
        self._create_plotly_gauges()
        left_v = QVBoxLayout()
        left_v.setSpacing(12)
        left_v.addWidget(self._wrap_panel(self.g_temp_view, "Temperature"))
        left_v.addWidget(self._wrap_panel(self.g_pres_view, "Pressure"))
        left_v.addWidget(self._wrap_panel(self.g_accel_view, "Acceleration"))
        left_widget = QWidget(); left_widget.setLayout(left_v)

        # Middle: altitude cylinder
        self.alt = AltitudeCylinder(max_alt=1500, rocket_path=self.rocket_path)

        # Right: camera boxes
        self.camera_boxes = [CameraBox("Front Camera"), CameraBox("Rear Camera")]
        right_v = QVBoxLayout()
        right_v.setSpacing(12)
        for cam in self.camera_boxes:
            right_v.addWidget(cam)
        right_widget = QWidget(); right_widget.setLayout(right_v)

        # grid placement
        grid.addWidget(left_widget, 0, 0)
        grid.addWidget(self.alt, 0, 1)
        grid.addWidget(right_widget, 0, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 3)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def _wrap_panel(self, widget, label_text):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("QFrame { background: #0e1113; border-radius:10px; border:1px solid #1d2830; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(widget, 4)

        led = QLabel("●")
        led.setStyleSheet("color: limegreen; font-size: 20px;")
        led.setFixedWidth(26)
        layout.addWidget(led, 1)

        lbl = QLabel(label_text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedWidth(72)
        layout.addWidget(lbl, 1)

        frame._led = led
        return frame

    def _create_plotly_gauges(self):
        # initial values
        t0, p0, a0 = 20.0, 1013.25, 0.0
        # prepare HTML for gauges (bright text color)
        text_color = "#e6eef8"
        self._g_temp_html = make_plotly_gauge_html("Temperature (°C)", -50, 150, t0, bar_color="#FF7043", text_color=text_color)
        self._g_pres_html = make_plotly_gauge_html("Pressure (Pa)", 800, 1200, p0, bar_color="#42A5F5", text_color=text_color)
        self._g_accel_html = make_plotly_gauge_html("Acceleration (m/s²)", 0, 20, a0, bar_color="#66BB6A", text_color=text_color)

        # Create views (or fallback)
        if _HAS_WEBENGINE:
            self.g_temp_view = QWebEngineView()
            self.g_temp_view.setHtml(self._g_temp_html, QUrl("about:blank"))
            self.g_temp_view.setMinimumSize(320, 180)

            self.g_pres_view = QWebEngineView()
            self.g_pres_view.setHtml(self._g_pres_html, QUrl("about:blank"))
            self.g_pres_view.setMinimumSize(320, 180)

            self.g_accel_view = QWebEngineView()
            self.g_accel_view.setHtml(self._g_accel_html, QUrl("about:blank"))
            self.g_accel_view.setMinimumSize(320, 180)
        else:
            def simple_label(txt):
                l = QLabel(txt)
                l.setFixedHeight(180)
                l.setAlignment(Qt.AlignCenter)
                l.setStyleSheet("background:#0b0c0d; border-radius:8px; color:#cfe8ff")
                return l
            self.g_temp_view = simple_label("Temperature\n(Plotly missing)")
            self.g_pres_view = simple_label("Pressure\n(Plotly missing)")
            self.g_accel_view = simple_label("Acceleration\n(Plotly missing)")

    # Demo telemetry generator
    def _demo_tick(self):
        s = self._demo_state
        s["t"] += 0.4
        if s["t"] > 120:
            s["t"] = -20
        s["p"] += (math.sin(s["t"] / 9.0) * 0.6)
        s["a"] = abs(math.sin(s["t"] / 8.0) * 8.0)
        s["alt"] = min(1500, s["alt"] + 2.8)
        row = {"Temp_C": s["t"], "Pressure_Pa": s["p"], "Accel_m_s2": s["a"], "Altitude_m": s["alt"]}
        # demo redundant toggle occasionally
        primary_ok = (int(time.time()) % 40) < 35
        self.set_redundant_mode(not primary_ok)
        self.updateFromRow(row)

    @safe
    def updateFromRow(self, row):
        """
        row: dict with keys 'Temp_C', 'Pressure_Pa', 'Accel_m_s2', 'Altitude_m'
        Call this from your telemetry reader.
        """
        try:
            if 'Temp_C' in row:
                self._update_plotly_view(self.g_temp_view, row['Temp_C'])
            if 'Pressure_Pa' in row:
                self._update_plotly_view(self.g_pres_view, row['Pressure_Pa'])
            if 'Accel_m_s2' in row:
                self._update_plotly_view(self.g_accel_view, row['Accel_m_s2'])
            if 'Altitude_m' in row:
                self.alt.setAltitude(row['Altitude_m'])
        except Exception as e:
            print("updateFromRow error:", e)

    def _update_plotly_view(self, webview, value):
        if not _HAS_WEBENGINE or webview is None:
            return
        try:
            js = f"window.updateGauge({float(value)});"
            webview.page().runJavaScript(js)
        except Exception as e:
            print("Error updating plotly gauge:", e)

    def set_redundant_mode(self, active):
        """Switch LED color to indicate primary sensor failure (active=True means redundant active)."""
        print("CockpitWidget: set_redundant_mode:", active)
        for frame in self.findChildren(QFrame):
            led = getattr(frame, "_led", None)
            if led:
                if active:
                    led.setStyleSheet("color: orange; font-size: 20px;")
                else:
                    led.setStyleSheet("color: limegreen; font-size: 20px;")

    def update_camera_frame(self, index, frame_bgr):
        if 0 <= index < len(self.camera_boxes):
            self.camera_boxes[index].update_frame(frame_bgr)
        else:
            print("update_camera_frame: index out of range", index)

# ---------------- Floating window wrapper ----------------
class CockpitFloatingWindow(QDialog):
    def __init__(self, parent=None, rocket_path=r"C:\MERN_TT\assets\rocket.png"):
        super().__init__(parent)
        print("CockpitFloatingWindow: opening")
        self.setWindowTitle("Cockpit Gauges")
        self.setModal(False)
        self.resize(1100, 720)
        self.setStyleSheet("background:#111316;")
        layout = QVBoxLayout(self)
        self.cockpit = CockpitWidget(self, rocket_path=rocket_path)
        layout.addWidget(self.cockpit)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(30)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def updateFromRow(self, row):
        self.cockpit.updateFromRow(row)

# Expose public classes
__all__ = ["CockpitWidget", "CockpitFloatingWindow"]

# ---------------- standalone demo ----------------
if __name__ == "__main__":
    print("cockpit_tab.py standalone demo")
    app = QApplication(sys.argv)

    rocket_default = r"C:\MERN_TT\assets\rocket.png"
    if not os.path.exists(rocket_default):
        rocket_default = None

    w = CockpitFloatingWindow(rocket_path=rocket_default)
    w.show()

    # Fill demo camera frames (black)
    def fill_demo_frames():
        for cb in w.cockpit.camera_boxes:
            px = QPixmap(cb.view.size())
            px.fill(QColor("#000000"))
            cb.view.setPixmap(px)
    fill_demo_frames()

    sys.exit(app.exec())
