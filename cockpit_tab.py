import os
import sys
import math
import csv
import time
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PySide6.QtCore import Qt, QTimer, QUrl, QSize
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QScrollArea, QSizePolicy, QPushButton, QDialog, QApplication, QFileDialog

# Optional WebEngine/Multimedia imports
HAS_WEBENGINE = True
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    HAS_WEBENGINE = False

USE_MULTIMEDIA = True
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception:
    USE_MULTIMEDIA = False

try:
    import cv2
    HAS_CV2 = True
except Exception:
    HAS_CV2 = False

def silent(func):
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception in {func.__name__}:", e)
            return None
    return wrapped

def make_plotly_gauge_html(title, minv, maxv, initv, barcolor="#2B84D6", textcolor="#111111"):
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html,body{{margin:0;height:100%;background:transparent}}
body{{font-family:Segoe UI,sans-serif}}
.plotly .modebar{{display:none!important}}
</style>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
<div id="g"></div>
<script>
var data = [{{
    type: "indicator",
    mode: "gauge+number",
    value: {initv},
    title: {{text: "{title}", font: {{size:22, color:"{textcolor}"}}}},
    number: {{font: {{size: 24, color: "{textcolor}"}}}},
    gauge: {{
        axis: {{range:[{minv},{maxv}], tickcolor:"#333", nticks:6, tickfont:{{size:13, color:"{textcolor}"}}}},
        bar: {{color:"{barcolor}"}},
        bgcolor:"rgba(0,0,0,0)", borderwidth:0,
        steps:[
            {{range:[{minv},{maxv}], color:"rgba(0,128,255,0.08)"}}
        ],
        threshold: {{value: {0.92*maxv}, line: {{color: "red", width: 3}}, thickness:0.75}}
    }}
}}];
var layout = {{margin:{{l:8,r:8,t:12,b:8}}, paper_bgcolor:"rgba(0,0,0,0)", font:{{family:"Segoe UI", color:"{textcolor}"}}, height:180}};
Plotly.newPlot('g', data, layout, {{displayModeBar:false, responsive:true}});
window.updateGauge = function(val) {{
    try{{
        Plotly.restyle('g', 'value', [Number(val) || 0], 0);
    }}catch(e){{}}
}};
</script>
</body>
</html>"""
    return html

class AltitudeCylinder(QWidget):
    def __init__(self, maxalt=1500, rocketpath=None, parent=None):
        super().__init__(parent)
        self.maxalt = float(maxalt)
        self.alt = 0.0
        self.rocketpath = rocketpath
        self.rocket = QPixmap(self.rocketpath) if self.rocketpath and os.path.exists(self.rocketpath) else None
        self.setMinimumSize(120, 420)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.titlefont = QFont("Segoe UI", 11, QFont.Bold)
        self.valuefont = QFont("Consolas", 14, QFont.Bold)

    @silent
    def setAltitude(self, value):
        try:
            v = float(value)
        except Exception:
            v = 0.0
        self.alt = max(0.0, min(self.maxalt, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        pad = 10
        inner = r.adjusted(pad, pad, -pad, -pad)
        p.fillRect(r, QColor("#f2f2f2"))
        p.setPen(QPen(QColor("#d0d0d0"), 1.2))
        p.setBrush(QBrush(QColor("#e8e8e8")))
        p.drawRoundedRect(inner, 12, 12)
        left = inner.left()
        right = inner.right() - 12
        top = inner.top() + 24
        bottom = inner.bottom() - 38
        width = right - left
        height = bottom - top

        p.setBrush(QBrush(QColor("#ededed")))
        p.setPen(QPen(QColor("#cccccc"), 1.0))
        p.drawRoundedRect(left, top, width, height, 8, 8)

        ratio = self.alt/self.maxalt if self.maxalt else 0
        fillh = max(6, height*ratio)
        filly = bottom - fillh
        grad = QLinearGradient(left, filly, left, bottom)
        grad.setColorAt(0.0, QColor("#4fd2ff"))
        grad.setColorAt(1.0, QColor("#006b96"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        drawh = fillh - 6 if fillh > 12 else fillh
        p.drawRoundedRect(left+6, filly+6, width-12, drawh, 6, 6)

        p.setPen(QPen(QColor("#111111")))
        p.setFont(QFont("Consolas", 9))
        ticks = 6
        for i in range(ticks):
            frac = i / (ticks-1)
            y = bottom - frac*height
            p.drawLine(right+6, int(y), right+20, int(y))
            val = int(round(frac * self.maxalt))
            p.drawText(right+24, int(y)-8, 40, 16, Qt.AlignLeft | Qt.AlignVCenter, str(val))
        if self.rocket:
            rpw = min(36, int(width*0.5))
            rph = rpw
            rockety = int(bottom - fillh - rph/2)
            rocketx = int(left + width/2 - rpw/2)
            rockety = max(top+4, min(rockety, bottom - rph - 4))
            p.drawPixmap(rocketx, rockety, rpw, rph, self.rocket)
        p.setPen(QPen(QColor("#111111")))
        p.setFont(self.titlefont)
        p.drawText(left, inner.top()+6, width, 20, Qt.AlignCenter, "Altitude")
        p.setFont(self.valuefont)
        p.drawText(left, inner.bottom()-34, width, 28, Qt.AlignCenter, f"{int(self.alt)} m")
        p.end()

class CameraBox(QFrame):
    def __init__(self, title="Camera", parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {background:#f2f2f2; border:1px solid #cfcfcf; border-radius:10px;}
            QLabel[objectName=title] {color:#111111; font:10pt "Segoe UI";padding-left:6px;}
            QLabel[objectName=view] {background:#000;border-radius:8px;}
            QPushButton {background:transparent; color:#333; border:1px solid #bdbdbd; border-radius:6px; padding:2px;}
            QPushButton:hover {background:#e0e0e0;}
        """)
        self.setMinimumSize(320,220)
        self.currentfile = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(6)
        titlelbl = QLabel(title)
        titlelbl.setObjectName("title")
        titlelbl.setFixedHeight(22)
        layout.addWidget(titlelbl)

        self.view = QLabel()
        self.view.setObjectName("view")
        self.view.setMinimumSize(300, 160)
        self.view.setAlignment(Qt.AlignCenter)
        blank = QPixmap(self.view.size())
        blank.fill(QColor("#000000"))
        self.view.setPixmap(blank)
        layout.addWidget(self.view)

        ctrlrow = QHBoxLayout()
        ctrlrow.setSpacing(6)

        self.uploadbtn = QPushButton("⏏")
        self.uploadbtn.setToolTip("Upload")
        self.uploadbtn.setFixedSize(36,28)
        self.uploadbtn.clicked.connect(self.onupload)
        ctrlrow.addWidget(self.uploadbtn)

        self.playbtn = QPushButton("▶")
        self.playbtn.setToolTip("Play")
        self.playbtn.setFixedSize(36,28)
        self.playbtn.clicked.connect(self.onplay)
        ctrlrow.addWidget(self.playbtn)

        self.pausebtn = QPushButton("⏸")
        self.pausebtn.setToolTip("Pause")
        self.pausebtn.setFixedSize(36,28)
        self.pausebtn.clicked.connect(self.onpause)
        ctrlrow.addWidget(self.pausebtn)

        self.restartbtn = QPushButton("⟲")
        self.restartbtn.setToolTip("Restart")
        self.restartbtn.setFixedSize(36,28)
        self.restartbtn.clicked.connect(self.onrestart)
        ctrlrow.addWidget(self.restartbtn)

        ctrlrow.addStretch()
        self.expandbtn = QPushButton("⛶")
        self.expandbtn.setToolTip("Expand")
        self.expandbtn.setFixedSize(36,28)
        self.expandbtn.clicked.connect(self.openexpanded)
        ctrlrow.addWidget(self.expandbtn)
        layout.addLayout(ctrlrow)

        self.player = None
        self.audiooutput = None
        self.videowidget = None
        if USE_MULTIMEDIA:
            try:
                self.player = QMediaPlayer(self)
                self.audiooutput = QAudioOutput(self)
                self.player.setAudioOutput(self.audiooutput)
                self.videowidget = QVideoWidget(self)
                self.videowidget.setMinimumSize(300, 160)
                self.videowidget.setStyleSheet("background:#000;")
                self.player.setVideoOutput(self.videowidget)
            except Exception:
                self.player = None
                self.audiooutput = None
                self.videowidget = None

    @silent
    def onupload(self):
        file, _ = QFileDialog.getOpenFileName(self, "Choose video file", "", "Video Files (*.mp4 *.avi *.mkv *.mov);;All Files (*)")
        if not file:
            return
        self.currentfile = file
        if self.player and self.videowidget:
            parentlayout = self.layout()
            idx = parentlayout.indexOf(self.view)
            if idx != -1:
                parentlayout.insertWidget(idx, self.videowidget)
                parentlayout.removeWidget(self.view)
            self.view.hide()
            self.videowidget.show()
            self.player.setVideoOutput(self.videowidget)
            self.player.setSource(QUrl.fromLocalFile(file))
            self.player.setPlaybackRate(1.0)
            self.player.play()
        else:
            pix = QPixmap(self.view.size())
            pix.fill(QColor("#e0e0e0"))
            painter = QPainter(pix)
            painter.setPen(QColor("#111111"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(pix.rect(), Qt.AlignCenter, os.path.basename(file))
            painter.end()
            self.view.setPixmap(pix)

    @silent
    def onplay(self):
        if self.player and self.currentfile:
            self.player.play()

    @silent
    def onpause(self):
        if self.player and self.currentfile:
            self.player.pause()

    @silent
    def onrestart(self):
        if self.player and self.currentfile:
            self.player.stop()
            QTimer.singleShot(100, lambda: self.player.play())

    @silent
    def updateframe(self, framebgr):
        if not HAS_CV2 or framebgr is None:
            blank = QPixmap(self.view.size())
            blank.fill(QColor("#000"))
            self.view.setPixmap(blank)
            return
        h, w = framebgr.shape[:2]
        rgb = cv2.cvtColor(framebgr, cv2.COLOR_BGR2RGB)
        bytesperline = 3 * w
        qimg = QImage(rgb.data, w, h, bytesperline, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.view.setPixmap(pix)

    @silent
    def openexpanded(self):
        dlg = QDialog(self.window())
        dlg.setWindowTitle("Camera - Expanded")
        dlg.setModal(True)
        v = QVBoxLayout(dlg)
        # If playing video, reparent the QVideoWidget temporarily
        is_video = self.player and self.videowidget and self.currentfile
        if is_video:
            old_parent = self.videowidget.parentWidget()
            self.videowidget.setParent(dlg)
            v.addWidget(self.videowidget)
            self.videowidget.show()
            dlg.resize(900, 700)
            dlg.exec()
            self.videowidget.setParent(old_parent)
            old_parent.layout().insertWidget(1, self.videowidget)
            self.videowidget.setMinimumSize(300, 160)
        else:
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            if self.view.pixmap():
                label.setPixmap(self.view.pixmap().scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                empty = QPixmap(800, 600)
                empty.fill(QColor("#000"))
                label.setPixmap(empty)
            v.addWidget(label)
            dlg.resize(900, 700)
            dlg.exec()

class CockpitWidget(QWidget):
    def __init__(self, parent=None, rocketpath=None, telemetrycsv=None):
        super().__init__(parent)
        self.setStyleSheet("background:#f2f2f2; color:#111111; font-family:Segoe UI;")
        self.rocketpath = rocketpath
        self.telemetrycsv = telemetrycsv
        self.initui()
        self.csvrows = []
        self.csvindex = 0
        if self.telemetrycsv and os.path.exists(self.telemetrycsv):
            try:
                with open(self.telemetrycsv, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    self.csvrows = list(reader)
            except Exception as e:
                print("Failed to read telemetry CSV:", e)
        self.demotimer = QTimer(self)
        self.demotimer.timeout.connect(self.demotick)
        self.demotimer.start(300)

    def initui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content = QWidget()
        content.setMinimumWidth(1400)
        scroll.setWidget(content)
        grid = QGridLayout(content)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        # Plotly/Simple Gauges left
        self.createplotlygauges()
        leftv = QVBoxLayout()
        leftv.setSpacing(12)
        leftv.addWidget(self.wrappanel(self.gtempview, "Temperature"))
        leftv.addWidget(self.wrappanel(self.gpresview, "Pressure"))
        leftv.addWidget(self.wrappanel(self.gaccelview, "Acceleration"))
        leftwidget = QWidget()
        leftwidget.setLayout(leftv)
        # Camera boxes right
        self.cameraboxes = [
            CameraBox("Front Camera"),
            CameraBox("Rear Camera"),
        ]
        rightv = QVBoxLayout()
        rightv.setSpacing(12)
        for cam in self.cameraboxes:
            rightv.addWidget(cam)
        rightwidget = QWidget()
        rightwidget.setLayout(rightv)
        self.alt = AltitudeCylinder(maxalt=1500, rocketpath=self.rocketpath)
        grid.addWidget(leftwidget, 0, 0)
        grid.addWidget(self.alt, 0, 1)
        grid.addWidget(rightwidget, 0, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 3)
        outer = QVBoxLayout(self)
        outer.addWidget(scroll)
        self.setLayout(outer)

    def wrappanel(self, widget, labeltext):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("QFrame{background:#f2f2f2; border-radius:10px; border:1px solid #cfcfcf;}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8,8,8,8)
        layout.addWidget(widget, 4)
        lbl = QLabel(labeltext)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedWidth(72)
        layout.addWidget(lbl, 1)
        frame.label = lbl
        return frame

    def createplotlygauges(self):
        t0, p0, a0 = 20.0, 1013.25, 0.0
        textcolor = "#111111"
        self.gtemphtml = make_plotly_gauge_html("Temperature (C)", -50, 150, t0, barcolor="#FF7043", textcolor=textcolor)
        self.gpreshtml = make_plotly_gauge_html("Pressure (Pa)", 800, 1200, p0, barcolor="#42A5F5", textcolor=textcolor)
        self.gaccelhtml = make_plotly_gauge_html("Acceleration (m/s²)", 0, 20, a0, barcolor="#66BB6A", textcolor=textcolor)
        if HAS_WEBENGINE:
            self.gtempview = QWebEngineView()
            self.gtempview.setHtml(self.gtemphtml, QUrl("about:blank"))
            self.gtempview.setMinimumSize(320,180)
            self.gpresview = QWebEngineView()
            self.gpresview.setHtml(self.gpreshtml, QUrl("about:blank"))
            self.gpresview.setMinimumSize(320,180)
            self.gaccelview = QWebEngineView()
            self.gaccelview.setHtml(self.gaccelhtml, QUrl("about:blank"))
            self.gaccelview.setMinimumSize(320,180)
        else:
            def simplelabel(txt):
                l = QLabel(txt)
                l.setFixedHeight(180)
                l.setAlignment(Qt.AlignCenter)
                l.setStyleSheet("background:#e8e8e8; border-radius:8px; color:#111111;")
                return l
            self.gtempview = simplelabel("Temperature\nPlotly missing")
            self.gpresview = simplelabel("Pressure\nPlotly missing")
            self.gaccelview = simplelabel("Acceleration\nPlotly missing")

    @silent
    def updateplotlyview(self, webview, value):
        if not HAS_WEBENGINE or webview is None:
            return
        js = f"window.updateGauge({float(value)})"
        webview.page().runJavaScript(js)

    @silent
    def demotick(self):
        # If CSV available, play rows; otherwise, step demo mode
        if self.csvrows:
            row = self.csvrows[self.csvindex % len(self.csvrows)]
            self.updateFromRow(row)
            self.csvindex = (self.csvindex + 1) % len(self.csvrows)
        else:
            if not hasattr(self, "demostate"):
                self.demostate = {"t":15.0, "p":1013.25, "a":0.0, "alt":100.0}
            s = self.demostate
            s["t"] = max(-20, min(120, s["t"] + 0.3))
            s["p"] = 900 + 50*math.sin(s["t"]/9.0)
            s["a"] = abs(math.sin(s["t"]/8.0))*8.0
            s["alt"] = min(1500, s["alt"] + 2.2)
            row = {
                "TempC": s["t"],
                "PressurePa": s["p"],
                "Accelms2": s["a"],
                "Altitudem": s["alt"],
            }
            self.updateFromRow(row)

    @silent
    def updateFromRow(self, row):
        try:
            if "TempC" in row and row["TempC"] not in (None, ""):
                self.updateplotlyview(self.gtempview, float(row["TempC"]))
            if "PressurePa" in row and row["PressurePa"] not in (None, ""):
                self.updateplotlyview(self.gpresview, float(row["PressurePa"]))
            if "Accelms2" in row and row["Accelms2"] not in (None, ""):
                self.updateplotlyview(self.gaccelview, float(row["Accelms2"]))
            if "Altitudem" in row and row["Altitudem"] not in (None, ""):
                self.alt.setAltitude(float(row["Altitudem"]))
        except Exception as e:
            print("updateFromRow error", e)

class CockpitFloatingWindow(QDialog):
    def __init__(self, parent=None, rocketpath=None, telemetrycsv=None):
        super().__init__(parent)
        self.setWindowTitle("Cockpit Gauges")
        self.setModal(False)
        self.resize(1100, 720)
        self.setStyleSheet("background:#f2f2f2;")
        layout = QVBoxLayout(self)
        self.cockpit = CockpitWidget(self, rocketpath=rocketpath, telemetrycsv=telemetrycsv)
        layout.addWidget(self.cockpit)
        btnrow = QHBoxLayout()
        btnrow.addStretch()
        closebtn = QPushButton("Close")
        closebtn.setFixedHeight(30)
        closebtn.clicked.connect(self.close)
        btnrow.addWidget(closebtn)
        layout.addLayout(btnrow)

    def updateFromRow(self, row):
        self.cockpit.updateFromRow(row)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    rocket_default = "rCTT.png" if os.path.exists("rCTT.png") else None
    csvfile = "telemetry.csv" if os.path.exists("telemetry.csv") else None
    w = CockpitFloatingWindow(rocketpath=rocket_default, telemetrycsv=csvfile)
    w.show()
    def filldemoframes():
        for cb in w.cockpit.cameraboxes:
            px = QPixmap(cb.view.size())
            px.fill(QColor("#000000"))
            cb.view.setPixmap(px)
    filldemoframes()
    sys.exit(app.exec())
