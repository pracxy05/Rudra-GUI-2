from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QTime, Signal, QPoint
from PySide6.QtGui import QFont, QCursor, QPixmap
import os

# --- Internal Imports (safe ones only) ---
from telemetry1 import TelemetryPanel
from mission_stagebar import MissionStageBar
from tabs.controltab import ControlTab
from tabs.visualtab import VisualTab
from tabs.systemdials import SystemDialsTab
from tabs.csvtab import CSVTab
from tabs.logtab import LogTab
from cockpit_tab import CockpitWidget, CockpitFloatingWindow
from gallery import GalleryTab
from admin import AdminTab
from inputsourcedialog import InputSourceDialog
from serial_preprocessor import XBeeTelemetryWorker  # live parser


class MainDashboardWindow(QMainWindow):
    inputsourcechanged = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RUDRA GROUND STATION")
        self.setGeometry(100, 100, 1400, 850)
        self.themedark = False
        self.active_input_source = None
        self.active_input_details = None
        self.preproc = None

        # references used for alignment
        self.topbar = None
        self.timerlabel = None
        self.health_strip = None
        self.health_icon = None
        self.logtab = None

        self.init_ui()

    # ---------------------------
    # MAIN UI SETUP (minimal edits only)
    # ---------------------------
    def init_ui(self):
        self.telemetrypanel = TelemetryPanel()

        self.pagestack = QStackedWidget()
        self.pagestack.addWidget(ControlTab())
        self.pagestack.addWidget(VisualTab())
        self.pagestack.addWidget(SystemDialsTab())
        try:
            from tabs.gpstab import GPSTab
            gps_tab = GPSTab()
        except Exception as e:
            print("❌ GPSTab init error:", e)
            gps_tab = QWidget()
        self.pagestack.addWidget(gps_tab)
        self.csvtab = CSVTab()
        self.pagestack.addWidget(self.csvtab)

        # Create and capture LogTab reference (no position or order change)
        self.pagestack.addWidget(LogTab())
        for i in range(self.pagestack.count()):
            w = self.pagestack.widget(i)
            if isinstance(w, LogTab):
                self.logtab = w
                break

        try:
            from tabs.plottab import PlotTab
            self.plottab = PlotTab()
        except Exception as e:
            print("❌ PlotTab init error:", e)
            self.plottab = QWidget()

        self.maintabs = QTabWidget()
        self.maintabs.setTabPosition(QTabWidget.TabPosition.North)

        self.cockpit_widget = CockpitWidget()
        self.maintabs.addTab(self.cockpit_widget, "COCKPIT")
        self.maintabs.addTab(self.plottab, "PLOT")
        self.maintabs.addTab(GalleryTab(), "GALLERY")

        self.summarytab = QTextEdit()
        self.summarytab.setReadOnly(True)
        self.summarytab.setText("Summary and analysis area (to be implemented).")
        self.maintabs.addTab(self.summarytab, "SUMMARY")

        # ------------------ Top Bar (alignment polish only) ------------------
        self.topbar = QFrame()
        self.topbar.setFixedHeight(70)
        self.topbar.setStyleSheet("QFrame { background: #f2f3f5; border-radius: 16px; margin: 5px; }")
        toplayout = QHBoxLayout(self.topbar)
        toplayout.setContentsMargins(12, 5, 16, 5)
        toplayout.setSpacing(16)

        # Button group; remove container background so pills float cleanly
        btnbox = QFrame()
        btnbox.setStyleSheet("QFrame { background: transparent; border: none; }")
        btnrow = QHBoxLayout(btnbox)
        btnrow.setContentsMargins(0, 0, 0, 0)
        btnrow.setSpacing(10)

        pill = """
            QPushButton {
                background: #e9e9ef;
                border: none;
                border-radius: 12px;
                padding: 8px 20px;
                color: #232a35;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background: #d9dae3; color: #19305a; }
        """
        self.homebtn  = QPushButton("HOME");  self.homebtn.setStyleSheet(pill);  self.homebtn.clicked.connect(self.show_home_tabs)
        self.themebtn = QPushButton("THEME"); self.themebtn.setCheckable(True);  self.themebtn.setStyleSheet(pill); self.themebtn.clicked.connect(self.toggle_theme)
        self.corebtn  = QPushButton("CORE");  self.corebtn.setStyleSheet(pill);  self.corebtn.clicked.connect(self.toggle_cockpit_window)
        self.inputbtn = QPushButton("INPUT"); self.inputbtn.setStyleSheet(pill); self.inputbtn.clicked.connect(self.open_input_source_dialog)
        for b in (self.homebtn, self.themebtn, self.corebtn, self.inputbtn):
            b.setMinimumHeight(36); b.setMaximumHeight(40); b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btnrow.addWidget(b)
        toplayout.addWidget(btnbox, 0, Qt.AlignVCenter)

        # Logo + Title in one compact block
        self.logolabel = QLabel()
        logopath = "C:/MERN_TT/assets/Home.png"
        if os.path.exists(logopath):
            self.logolabel.setPixmap(QPixmap(logopath).scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logolabel.setCursor(QCursor(Qt.PointingHandCursor))
        self.logolabel.setFixedSize(40, 40)

        namelabel = QLabel("RUDRA GROUNDSTATION")
        namelabel.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        # remove heavy border; keep subtle pad to stop clipping
        namelabel.setStyleSheet("color:#232a35; background:#f2f3f5; padding:6px 14px; border-radius:10px;")

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
        logo_row.setSpacing(8)
        logo_row.addWidget(self.logolabel, 0, Qt.AlignVCenter)
        logo_row.addWidget(namelabel, 0, Qt.AlignVCenter)
        logo_box = QFrame()
        logo_box.setStyleSheet("QFrame { background: transparent; border: none; }")
        logo_box.setLayout(logo_row)
        toplayout.addWidget(logo_box, 0, Qt.AlignVCenter)
        self.logolabel.mousePressEvent = self.toggle_admin_tab_hidden

        toplayout.addStretch(1)

        self.inputstatus = QLabel("Input Source: [not selected]")
        self.inputstatus.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.inputstatus.setStyleSheet("color:#17a2b8; background-color:rgba(0,0,0,0.18); padding:6px 10px; border-radius:11px;")
        toplayout.addWidget(self.inputstatus, 0, Qt.AlignVCenter)

        self.timerlabel = QLabel("Mission Time 00:00")
        self.timerlabel.setFont(QFont("Segoe UI", 12))
        self.timerlabel.setStyleSheet("color:#3498db; background-color:rgba(0,0,0,0.13); padding:7px 17px; border-radius:13px;")
        toplayout.addWidget(self.timerlabel, 0, Qt.AlignVCenter)

        # ------------------ Central Layout ------------------
        contentarea = QWidget()
        contentlayout = QVBoxLayout(contentarea)
        contentlayout.setContentsMargins(0, 0, 0, 0)
        contentlayout.setSpacing(0)

        contentlayout.addWidget(self.topbar, 0)

        # NEW: ultra-thin transparent strip just below topbar; holds only the lightning glyph
        self.health_strip = QFrame()
        self.health_strip.setFixedHeight(18)
        self.health_strip.setStyleSheet("QFrame { background: transparent; }")
        # icon inside strip; no background; mouse-transparent; always visible
        self.health_icon = QLabel("⚡", parent=self.health_strip)
        self.health_icon.setStyleSheet("color:#2ecc71; background:transparent; font-size:16px;")
        self.health_icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.health_icon.move(12, 1)
        contentlayout.addWidget(self.health_strip, 0)

        contentlayout.addWidget(self.maintabs, 1)
        contentlayout.addWidget(self.pagestack, 1)

        # Mission stage bar at the bottom of the content column
        self.mission_stage_bar = MissionStageBar()
        contentlayout.addWidget(self.mission_stage_bar, 0)

        self.pagestack.hide()
        self.maintabs.show()

        # Outer shell: left telemetry rail + content column
        outer = QHBoxLayout()
        outer.setContentsMargins(6, 6, 6, 6)
        self.telemetrypanel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        outer.addWidget(self.telemetrypanel, 0)
        outer.addWidget(contentarea, 1)
        container = QWidget()
        container.setLayout(outer)
        self.setCentralWidget(container)

        self.cockpitwindow = CockpitFloatingWindow(self)
        self.cockpitwindow.hide()

        self.missiontimer = QTimer()
        self.missiontime = QTime(0, 0, 0)
        self.missiontimer.timeout.connect(self.update_mission_time)
        self.missiontimer.start(1000)

        self.maintabs.currentChanged.connect(self.on_main_tab_changed)
        self.telemetrypanel.tab_select.connect(self.show_stack_page)

        # Data flow wiring
        self.csvtab.data_updated.connect(self.telemetrypanel.update_telemetry)
        self.csvtab.data_updated.connect(self._forward_to_plot_and_cockpit)
        self.inputsourcechanged.connect(self.change_input_source)

        if self.logtab is not None:
            self.logtab.health_changed.connect(self._on_health_changed)

    # Keep icon locked under timer across resizes
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_health_icon()

    def _reposition_health_icon(self):
        try:
            if not (self.health_strip and self.timerlabel and self.topbar):
                return
            # map timer center to global; then into the strip’s coords
            gcenter = self.timerlabel.mapToGlobal(self.timerlabel.rect().center())
            lcenter = self.health_strip.mapFromGlobal(gcenter)
            x = max(8, int(lcenter.x() - self.health_icon.width() // 2))
            y = max(1, int(self.health_strip.height() // 2 - self.health_icon.height() // 2))
            self.health_icon.move(x, y)
        except Exception:
            pass

    # ---------------------------
    # DATA FLOW HANDLERS
    # ---------------------------
    def _forward_to_plot_and_cockpit(self, row):
        try:
            if hasattr(self.plottab, "update_plot_data"):
                self.plottab.update_plot_data(row)
            if hasattr(self.cockpit_widget, "update_telemetry"):
                self.cockpit_widget.update_telemetry(row)
            if hasattr(self.cockpitwindow, "update_telemetry"):
                self.cockpitwindow.update_telemetry(row)
            if hasattr(self, 'mission_stage_bar'):
                self.mission_stage_bar.set_telemetry_data(row)
            if self.logtab is not None:
                self.logtab.process_telemetry(row)
        except Exception:
            pass

    def change_input_source(self, name, details):
        self._stop_preproc_if_running()
        self.active_input_source = name
        self.active_input_details = details

        if name in ("xbee_serial", "xbee_wired"):
            port = details if isinstance(details, str) else None
            baud = 9600
            if port:
                try:
                    self.preproc = XBeeTelemetryWorker(port, baud)
                    self.preproc.connected.connect(lambda p: self.telemetrypanel.set_connection_state(True, f"XBee:{p}"))
                    self.preproc.connection_lost.connect(lambda msg: self.telemetrypanel.set_connection_state(False, msg))
                    self.preproc.rowReady.connect(self.telemetrypanel.update_telemetry)
                    if hasattr(self.csvtab, "append_live_data"):
                        self.preproc.rowReady.connect(self.csvtab.append_live_data)
                    else:
                        self.preproc.rowReady.connect(self.csvtab.appendRow)
                    if hasattr(self.plottab, "update_plot_data"):
                        self.preproc.rowReady.connect(self.plottab.update_plot_data)
                    if hasattr(self.cockpit_widget, "update_telemetry"):
                        self.preproc.rowReady.connect(self.cockpit_widget.update_telemetry)
                    if hasattr(self.cockpitwindow, "update_telemetry"):
                        self.preproc.rowReady.connect(self.cockpitwindow.update_telemetry)
                    if hasattr(self, 'mission_stage_bar'):
                        self.preproc.rowReady.connect(self.mission_stage_bar.set_telemetry_data)
                    if self.logtab is not None:
                        self.preproc.rowReady.connect(self.logtab.process_telemetry)
                    self.telemetrypanel.set_connection_state(True, f"XBee:{port}")
                    self.preproc.start()
                except Exception as e:
                    self.telemetrypanel.set_connection_state(False, "XBee FAIL")
                    print("⚠️ Preprocessor start error:", e)
            else:
                self.telemetrypanel.set_connection_state(False, "XBee:NO PORT")
        elif name == "csv":
            self.telemetrypanel.set_connection_state(False, "CSV MODE")
        else:
            self.telemetrypanel.set_connection_state(False, "NO INPUT")

    def _stop_preproc_if_running(self):
        if getattr(self, "preproc", None):
            try:
                self.preproc.stop()
            except Exception:
                pass
            self.preproc = None
        self.telemetrypanel.set_connection_state(False, "DISCONNECTED")

    # ---------------------------
    # UI INTERACTIONS
    # ---------------------------
    def open_input_source_dialog(self):
        print("Opening input source dialog")
        dialog = InputSourceDialog(self)
        dialog.input_source_selected.connect(self.handle_input_source_selected)
        dialog.exec()

    def handle_input_source_selected(self, sourceid, extra):
        print(f"Input source selected: {sourceid}, details: {extra}")
        self.active_input_source = sourceid
        self.active_input_details = extra
        if sourceid == "csv":
            self.inputstatus.setText(f"Input Source: CSV File\n{extra}")
        elif sourceid in ("xbee_serial", "xbee_wired"):
            self.inputstatus.setText(f"Input Source: XBee ({extra})")
        else:
            self.inputstatus.setText("Input Source: [Unknown]")
        self.inputsourcechanged.emit(sourceid, extra)

    def toggle_admin_tab_hidden(self, event):
        idx = self.maintabs.indexOf(self.admin_tab)
        was_visible = self.maintabs.isTabVisible(idx)
        self.maintabs.setTabVisible(idx, not was_visible)
        if not was_visible:
            self.maintabs.setCurrentIndex(idx)

    def toggle_cockpit_window(self):
        if self.cockpitwindow.isVisible():
            self.cockpitwindow.hide()
        else:
            self.cockpitwindow.show()

    def update_mission_time(self):
        self.missiontime = self.missiontime.addSecs(1)
        self.timerlabel.setText(f"Mission Time {self.missiontime.toString('mm:ss')}")
        self._reposition_health_icon()  # keep aligned on tick too

    def show_stack_page(self, index):
        self.maintabs.hide()
        self.pagestack.show()
        self.pagestack.setCurrentIndex(index)

    def on_main_tab_changed(self, idx):
        self.pagestack.hide()
        self.maintabs.show()

    def show_home_tabs(self):
        self.pagestack.hide()
        self.maintabs.show()
        self.maintabs.setCurrentIndex(0)

    def toggle_theme(self):
        if self.themebtn.isChecked():
            self.setStyleSheet("""
                QMainWindow, QWidget { background: #232b2b; color: #e7eaf3; }
                QTabWidget::pane { background: #292e38; }
                QTabBar::tab { background: #444; color: #fafbfc; }
                QTabBar::tab:selected { background: #298af8; }
                QFrame { background: #22282b; }
                QPushButton, QLineEdit, QLabel { background: #333942; border: 1px solid #444; color: #e3eaf3; }
            """)
        else:
            self.setStyleSheet("")

    # ---------------------------
    # HEALTH ICON COLOR
    # ---------------------------
    def _on_health_changed(self, level: int, reason: str):
        color = "#2ecc71" if level == 0 else ("#f1c40f" if level == 1 else "#e74c3c")
        self.health_icon.setStyleSheet(f"color:{color}; background:transparent; font-size:16px;")
        self.health_icon.setToolTip(reason or "")
