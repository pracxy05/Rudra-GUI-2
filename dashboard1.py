# dashboard1.py

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QTime, Signal
from PySide6.QtGui import QFont, QCursor
import os

from telemetry1 import TelemetryPanel
from mission_stagebar import MissionStageBar
from tabs.controltab import ControlTab
from tabs.visualtab import VisualTab
from tabs.systemdials import SystemDialsTab
from tabs.gpstab import GPSTab
from tabs.csvtab import CSVTab
from tabs.logtab import LogTab
from tabs.plottab import PlotTab
from cockpit_tab import CockpitWidget, CockpitFloatingWindow
from gallery import GalleryTab
from admin import AdminTab
from inputsourcedialog import InputSourceDialog

class DashboardWindow(QMainWindow):

    inputsourcechanged = Signal(str, object)

    def __init__(self):
        super().__init__()
        print("Initializing DashboardWindow")
        self.setWindowTitle("RUDRA GROUND STATION")
        self.setGeometry(100, 100, 1400, 850)
        self.themedark = False
        self.active_input_source = None
        self.active_input_details = None
        self.init_ui()
        print("DashboardWindow UI initialized")

    def init_ui(self):
        self.telemetrypanel = TelemetryPanel()
        self.pagestack = QStackedWidget()
        self.pagestack.addWidget(ControlTab())
        self.pagestack.addWidget(VisualTab())
        self.pagestack.addWidget(SystemDialsTab())
        self.pagestack.addWidget(GPSTab())
        self.pagestack.addWidget(CSVTab())
        self.pagestack.addWidget(LogTab())

        self.maintabs = QTabWidget()
        self.maintabs.setTabPosition(QTabWidget.TabPosition.North)
        self.maintabs.addTab(CockpitWidget(), "COCKPIT")
        self.maintabs.addTab(PlotTab(), "PLOT")
        self.maintabs.addTab(GalleryTab(), "GALLERY")
        self.admin_tab = AdminTab()
        self.maintabs.addTab(self.admin_tab, "ADMIN")
        self.maintabs.setTabVisible(self.maintabs.indexOf(self.admin_tab), False)

        self.homebtn = QPushButton("HOME")
        self.homebtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.homebtn.setStyleSheet("""
            QPushButton {
                background: #f2f3f5;
                border: 1.7px solid #b5b9be;
                border-radius: 9px;
                padding: 10px 22px;
                color: #222;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #d6dae0; }
        """)
        self.homebtn.clicked.connect(self.show_home_tabs)

        self.themebtn = QPushButton("THEME")
        self.themebtn.setCheckable(True)
        self.themebtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.themebtn.setStyleSheet("""
            QPushButton {
                background: #d2d3d6;
                border: 1.5px solid #b0b2b7;
                border-radius: 9px;
                padding: 10px 17px;
                color: #222;
                font-size: 14px;
            }
            QPushButton:checked {
                background: #232b34;
                color: #f9fafb;
                border: 1.5px solid #222;
            }
        """)
        self.themebtn.clicked.connect(self.toggle_theme)

        self.showcockpitbtn = QPushButton("SHOW COCKPIT")
        self.showcockpitbtn.setStyleSheet("""
            QPushButton {
                background: orange;
                font-weight: bold;
                padding: 7px 20px;
                border-radius: 8px;
            }
            QPushButton:hover { background: #e67e22; }
        """)
        self.showcockpitbtn.clicked.connect(self.toggle_cockpit_window)

        self.inputbtn = QPushButton("INPUT")
        self.inputbtn.setStyleSheet("""
            QPushButton {
                background: #43d5ff;
                color: #18202a;
                font-weight: bold;
                border-radius: 8px;
                padding: 7px 22px;
                font-size: 14px;
            }
            QPushButton:hover { background: #2b9ed9; }
        """)
        self.inputbtn.clicked.connect(self.open_input_source_dialog)

        topbar = QFrame()
        topbar.setFixedHeight(70)
        topbar.setStyleSheet("QFrame { background-color: rgba(20, 20, 40, 0.6); border-radius: 10px; margin: 5px; }")
        toplayout = QHBoxLayout(topbar)
        toplayout.setContentsMargins(15, 5, 15, 5)
        toplayout.setSpacing(30)

        self.rudralogo = QLabel("RUDRA")
        self.rudralogo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.rudralogo.setStyleSheet("color: rgba(255, 255, 255, 0.04);")
        self.rudralogo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.rudralogo.setFixedWidth(120)
        self.rudralogo.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        self.rudralogo.mousePressEvent = self.toggle_admin_tab_hidden

        title = QLabel("RUDRA GROUND STATION")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white; padding: 5px;")
        titlecontainer = QWidget()
        titlecontainer_layout = QHBoxLayout(titlecontainer)
        titlecontainer_layout.setContentsMargins(0, 0, 0, 0)
        titlecontainer_layout.setSpacing(0)
        titlecontainer_layout.addWidget(self.rudralogo)
        titlecontainer_layout.addWidget(title)
        toplayout.addWidget(titlecontainer)
        toplayout.addStretch()

        topright = QHBoxLayout()
        topright.setSpacing(14)
        for btn in [self.homebtn, self.themebtn, self.showcockpitbtn, self.inputbtn]:
            btn.setMinimumHeight(38)
            btn.setMaximumHeight(42)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            topright.addWidget(btn)
        topright.addStretch()
        toprightwidget = QWidget()
        toprightwidget.setLayout(topright)
        toprightwidget.setFixedHeight(48)
        toplayout.addWidget(toprightwidget)

        self.inputstatus = QLabel()
        self.inputstatus.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.inputstatus.setStyleSheet("color: #17a2b8; background-color: rgba(0,0,0,0.18); padding: 6px 10px; border-radius: 7px;")
        self.inputstatus.setText("Input Source: [not selected]")
        toplayout.addWidget(self.inputstatus)

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

        self.cockpitwindow = CockpitFloatingWindow(self)
        self.cockpitwindow.hide()

        self.timerlabel = QLabel("Mission Time 00:00")
        self.timerlabel.setFont(QFont("Segoe UI", 12))
        self.timerlabel.setStyleSheet("color: #3498db; background-color: rgba(0, 0, 0, 0.3); padding: 5px 15px; border-radius: 15px;")
        toplayout.addWidget(self.timerlabel)

        self.missiontimer = QTimer()
        self.missiontime = QTime(0, 0, 0)
        self.missiontimer.timeout.connect(self.update_mission_time)
        self.missiontimer.start(1000)

        self.maintabs.currentChanged.connect(self.on_main_tab_changed)
        self.telemetrypanel.tab_select.connect(self.show_stack_page)

    # --- Features/Slots ---

    def toggle_admin_tab_hidden(self, event):
        print("Admin tab toggle triggered")
        idx = self.maintabs.indexOf(self.admin_tab)
        if not self.maintabs.isTabVisible(idx):
            self.maintabs.setTabVisible(idx, True)
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

    def open_input_source_dialog(self):
        print("Opening input source dialog")
        dialog = InputSourceDialog()
        dialog.input_source_selected.connect(self.handle_input_source_selected)

        dialog.exec()

    def handle_input_source_selected(self, sourceid, extra):
        print(f"Input source selected: {sourceid}, details: {extra}")
        self.active_input_source = sourceid
        self.active_input_details = extra

        if sourceid == "csv":
            self.inputstatus.setText(f"Input Source: CSV File\n{extra}")
        elif sourceid == "xbee_serial":
            self.inputstatus.setText(f"Input Source: Serial (COM Port)\n{extra}")
        elif sourceid == "xbee_wired":
            self.inputstatus.setText(f"Input Source: XBee Direct Wired")
        else:
            self.inputstatus.setText("Input Source: [Unknown]")

        self.inputsourcechanged.emit(sourceid, extra)
