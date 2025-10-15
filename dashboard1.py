from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QTime, Signal
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

        # Data flow and telemetry state
        self.active_input_source = None
        self.active_input_details = None
        self.preproc = None

        self.init_ui()

    # ---------------------------
    #   MAIN UI SETUP
    # ---------------------------
    def init_ui(self):
        self.telemetrypanel = TelemetryPanel()

        self.pagestack = QStackedWidget()
        self.pagestack.addWidget(ControlTab())
        self.pagestack.addWidget(VisualTab())
        self.pagestack.addWidget(SystemDialsTab())

        # Defer and guard GPSTab import + construct
        try:
            from tabs.gpstab import GPSTab
            gps_tab = GPSTab()
        except Exception as e:
            print("❌ GPSTab init error:", e)
            gps_tab = QWidget()
        self.pagestack.addWidget(gps_tab)

        self.csvtab = CSVTab()
        self.pagestack.addWidget(self.csvtab)
        self.pagestack.addWidget(LogTab())

        # Defer and guard PlotTab import + construct
        try:
            from tabs.plottab import PlotTab
            self.plottab = PlotTab()
        except Exception as e:
            print("❌ PlotTab init error:", e)
            self.plottab = QWidget()  # placeholder

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
        self.admin_tab = AdminTab()
        self.maintabs.addTab(self.admin_tab, "ADMIN")
        self.maintabs.setTabVisible(self.maintabs.indexOf(self.admin_tab), False)

        # ------------------ Top Bar ------------------
        topbar = QFrame()
        topbar.setFixedHeight(70)
        topbar.setStyleSheet("QFrame { background: #f2f3f5; border-radius: 16px; margin: 5px; }")
        toplayout = QHBoxLayout(topbar)
        toplayout.setContentsMargins(12, 5, 16, 5)
        toplayout.setSpacing(20)

        # Button group
        btnbox = QFrame()
        btnbox.setStyleSheet("QFrame {background: #f2f3f5; border-radius: 12px; border: 1.7px solid #e2e2e6;}")
        btnrow = QHBoxLayout(btnbox)
        btnrow.setContentsMargins(10, 5, 10, 5)
        btnrow.setSpacing(10)

        btnstyle = """
            QPushButton {
                background: #e9e9ef;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                color: #232a35;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background: #d9dae3; color: #19305a; }
        """

        self.homebtn = QPushButton("HOME")
        self.homebtn.setStyleSheet(btnstyle)
        self.homebtn.clicked.connect(self.show_home_tabs)

        self.themebtn = QPushButton("THEME")
        self.themebtn.setCheckable(True)
        self.themebtn.setStyleSheet(btnstyle)
        self.themebtn.clicked.connect(self.toggle_theme)

        self.corebtn = QPushButton("CORE")
        self.corebtn.setStyleSheet(btnstyle)
        self.corebtn.clicked.connect(self.toggle_cockpit_window)

        self.inputbtn = QPushButton("INPUT")
        self.inputbtn.setStyleSheet(btnstyle)
        self.inputbtn.clicked.connect(self.open_input_source_dialog)

        for btn in [self.homebtn, self.themebtn, self.corebtn, self.inputbtn]:
            btn.setMinimumHeight(38)
            btn.setMaximumHeight(44)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btnrow.addWidget(btn)

        toplayout.addWidget(btnbox, stretch=0)

        # Logo + Admin trigger
        self.logolabel = QLabel()
        logopath = "C:/MERN_TT/assets/Home.png"
        namelabel = QLabel("RUDRA GROUNDSTATION")
        namelabel.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        namelabel.setStyleSheet(
            "color: #232a35; background: #f2f3f5; border-radius: 14px; padding: 10px 22px;"
            "letter-spacing: 2.2px; margin-left: 5px; font-weight: bold; border: 1.7px solid #e2e2e6;"
        )
        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(8, 0, 6, 0)
        logo_row.setSpacing(8)
        if os.path.exists(logopath):
            logopix = QPixmap(logopath).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logolabel.setPixmap(logopix)
        self.logolabel.setCursor(QCursor(Qt.PointingHandCursor))
        self.logolabel.setFixedSize(44, 44)
        logo_row.addWidget(self.logolabel)
        logo_row.addWidget(namelabel)
        logo_row_widget = QWidget()
        logo_row_widget.setLayout(logo_row)
        toplayout.addWidget(logo_row_widget)
        self.logolabel.mousePressEvent = self.toggle_admin_tab_hidden

        toplayout.addStretch(1)

        # Status and mission time
        self.inputstatus = QLabel("Input Source: [not selected]")
        self.inputstatus.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.inputstatus.setStyleSheet(
            "color: #17a2b8; background-color: rgba(0,0,0,0.18); padding: 6px 10px; border-radius: 11px;"
        )
        toplayout.addWidget(self.inputstatus)

        self.timerlabel = QLabel("Mission Time 00:00")
        self.timerlabel.setFont(QFont("Segoe UI", 12))
        self.timerlabel.setStyleSheet(
            "color: #3498db; background-color: rgba(0, 0, 0, 0.13); padding: 7px 17px; border-radius: 13px;"
        )
        toplayout.addWidget(self.timerlabel)
        # ------------------ End Top Bar ------------------

        # Central layout
        contentarea = QWidget()
        contentlayout = QVBoxLayout(contentarea)
        contentlayout.setContentsMargins(0, 0, 0, 0)
        contentlayout.setSpacing(0)
        contentlayout.addWidget(topbar, 0)
        contentlayout.addWidget(self.maintabs, 1)
        contentlayout.addWidget(self.pagestack, 1)
        contentlayout.addWidget(MissionStageBar(), 0)

        self.pagestack.hide()
        self.maintabs.show()

        containerlayout = QHBoxLayout()
        containerlayout.addWidget(self.telemetrypanel, 0)
        containerlayout.addWidget(contentarea, 1)
        containerwidget = QWidget()
        containerwidget.setLayout(containerlayout)
        self.setCentralWidget(containerwidget)

        # Cockpit floating window
        self.cockpitwindow = CockpitFloatingWindow(self)
        self.cockpitwindow.hide()

        # Mission timer
        self.missiontimer = QTimer()
        self.missiontime = QTime(0, 0, 0)
        self.missiontimer.timeout.connect(self.update_mission_time)
        self.missiontimer.start(1000)

        # Connections
        self.maintabs.currentChanged.connect(self.on_main_tab_changed)
        self.telemetrypanel.tab_select.connect(self.show_stack_page)

        # --- Data Flow Connections ---
        self.csvtab.data_updated.connect(self.telemetrypanel.update_telemetry)
        self.csvtab.data_updated.connect(self._forward_to_plot_and_cockpit)
        self.inputsourcechanged.connect(self.change_input_source)

    # ---------------------------
    #   DATA FLOW HANDLERS
    # ---------------------------
    def _forward_to_plot_and_cockpit(self, row):
        """Send telemetry rows to all visual components."""
        try:
            if hasattr(self.plottab, "update_plot_data"):
                self.plottab.update_plot_data(row)
            if hasattr(self.cockpit_widget, "update_telemetry"):
                self.cockpit_widget.update_telemetry(row)
            if hasattr(self.cockpitwindow, "update_telemetry"):
                self.cockpitwindow.update_telemetry(row)
        except Exception:
            pass

    def change_input_source(self, name, details):
        """Switch between CSV / XBee live / Simulation sources."""
        self._stop_preproc_if_running()
        self.active_input_source = name
        self.active_input_details = details

        if name in ("xbee_serial", "xbee_wired"):
            # Start live telemetry
            port = details if isinstance(details, str) else None
            baud = 9600
            if port:
                try:
                    self.preproc = XBeeTelemetryWorker(port, baud)

                    # telemetry panel connection & connection status updates
                    self.preproc.connected.connect(lambda p: self.telemetrypanel.set_connection_state(True, f"XBee:{p}"))
                    self.preproc.connection_lost.connect(lambda msg: self.telemetrypanel.set_connection_state(False, msg))

                    # live data distribution
                    self.preproc.rowReady.connect(self.telemetrypanel.update_telemetry)

                    # CSVTab live append
                    if hasattr(self.csvtab, "append_live_data"):
                        self.preproc.rowReady.connect(self.csvtab.append_live_data)
                    else:
                        self.preproc.rowReady.connect(self.csvtab.appendRow)

                    # PlotTab and Cockpit forwarding (guard methods)
                    if hasattr(self.plottab, "update_plot_data"):
                        self.preproc.rowReady.connect(self.plottab.update_plot_data)
                    if hasattr(self.cockpit_widget, "update_telemetry"):
                        self.preproc.rowReady.connect(self.cockpit_widget.update_telemetry)
                    if hasattr(self.cockpitwindow, "update_telemetry"):
                        self.preproc.rowReady.connect(self.cockpitwindow.update_telemetry)

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
    #   UI INTERACTIONS
    # ---------------------------
    def open_input_source_dialog(self):
        """Triggered by top bar INPUT button."""
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

        # Emit standardized signal for live data management
        self.inputsourcechanged.emit(sourceid, extra)

    # ---------------------------
    #   THEME / WINDOW TOGGLES
    # ---------------------------
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
