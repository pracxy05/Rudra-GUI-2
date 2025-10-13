from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, 
    QFrame, QFileDialog, QDialog, QGraphicsDropShadowEffect, QCheckBox, QSlider
)
from PySide6.QtGui import QPixmap, QFont, QColor
from PySide6.QtCore import Qt, QTimer
import os

class MissionEvent:
    def __init__(self, image_path, title, caption, timestamp):
        self.image_path = image_path
        self.title = title
        self.caption = caption
        self.timestamp = timestamp
        self.favorite = False

def safe_pixmap(path, w=640, h=360):
    if path.lower().endswith(".pdf"):
        return None
    if os.path.exists(path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            return pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None

class FullscreenDialog(QDialog):
    def __init__(self, parent, img_path, title="", caption="", timestamp="", is_pdf=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setStyleSheet("background: rgba(30,30,40,0.95);")
        self.setMinimumSize(900, 600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color:#38aaf7;")
        lay.addWidget(title_lbl, alignment=Qt.AlignHCenter)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        if is_pdf:
            img_label.setText("📄 PDF Preview Not Supported\n" + os.path.basename(img_path))
            img_label.setStyleSheet("color: #ccc; font-size:16px; background:#1a202a; padding:30px; border-radius:14px;")
            img_label.setMinimumSize(500, 280)
        else:
            pixmap = safe_pixmap(img_path, 1200, 800)
            if pixmap:
                img_label.setPixmap(pixmap)
            else:
                img_label.setText("[No Image]")
                img_label.setMinimumSize(500, 280)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor("#106088"))
        shadow.setYOffset(6)
        img_label.setGraphicsEffect(shadow)
        lay.addWidget(img_label, alignment=Qt.AlignHCenter)

        cap = QLabel(caption)
        cap.setStyleSheet("color: #e0e9f0; font-size: 15px;")
        cap.setWordWrap(True)
        cap.setMaximumWidth(1000)
        lay.addWidget(cap, alignment=Qt.AlignHCenter)

        ts = QLabel(timestamp)
        ts.setStyleSheet("color: #88bdff; font-size: 13px; margin-top: 6px;")
        lay.addWidget(ts, alignment=Qt.AlignRight)

        close_btn = QPushButton("⨉ Close")
        close_btn.setStyleSheet("""
            QPushButton { background:#3267a8; color:white; border-radius:12px; font-size:15px; font-weight:bold; padding:8px 24px; }
            QPushButton:hover { background:#43d5ff; color:#18202a; }
        """)
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignHCenter)

class MissionCarouselCard(QFrame):
    def __init__(self, event, show_full_fn, toggle_fav_fn):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(event.title)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #1889f0;")
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        self.img_label = QLabel()
        pixmap = safe_pixmap(event.image_path, 340, 200)
        if pixmap:
            self.img_label.setPixmap(pixmap)
        else:
            self.img_label.setText("[No Image]")
            self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setFixedSize(340, 200)
        self.img_label.setCursor(Qt.PointingHandCursor)
        self.img_label.mousePressEvent = lambda ev: show_full_fn(
            event.image_path, event.title, event.caption, event.timestamp, event.image_path.lower().endswith(".pdf")
        )
        layout.addWidget(self.img_label, alignment=Qt.AlignHCenter)

        caption = QLabel(event.caption)
        caption.setFont(QFont("Segoe UI", 10))
        caption.setStyleSheet("color:#333; background: #f9f9fb; border-radius:7px; padding:6px 12px;")
        caption.setWordWrap(True)
        layout.addWidget(caption, alignment=Qt.AlignHCenter)

        ts_fav = QHBoxLayout()
        ts = QLabel(event.timestamp)
        ts.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        ts.setStyleSheet("color: #666;")
        ts_fav.addWidget(ts, alignment=Qt.AlignLeft)

        fav_btn = QPushButton("⭐" if event.favorite else "☆")
        fav_btn.setFixedSize(40, 28)
        fav_btn.setStyleSheet("background:none; border:none; font-size:18px; color:#f1c40f;")
        fav_btn.clicked.connect(lambda: toggle_fav_fn(event, fav_btn))
        ts_fav.addWidget(fav_btn, alignment=Qt.AlignRight)

        layout.addLayout(ts_fav)

        self.setStyleSheet("QFrame { background: #eef3fa; border-radius: 14px; padding:10px; }")

class GalleryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = [
            MissionEvent("assets/launch.jpg", "Launch", "Vehicle lifts off, engines nominal.", "T+00:00"),
            MissionEvent("assets/ascend.jpg", "Ascent", "Stage 1 burn, passing 5km altitude.", "T+01:35"),
            MissionEvent("assets/stage_sep.jpg", "Stage Separation", "First stage detached, ignition.", "T+02:57"),
            MissionEvent("assets/orbit.jpg", "Orbit Achieved", "Payload in orbit.", "T+08:21"),
        ]
        self.carousel_index = 0
        self.slideshow_timer = QTimer(self)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 20, 25, 25)
        main_layout.setSpacing(12)

        # Action Bar
        action_bar = QHBoxLayout()
        folder_btn = QPushButton("📂 Open File")
        folder_btn.setFixedHeight(34)
        folder_btn.setCursor(Qt.PointingHandCursor)
        folder_btn.clicked.connect(self.open_gallery_file)
        action_bar.addWidget(folder_btn, alignment=Qt.AlignLeft)

        self.auto_slide_chk = QCheckBox("Auto-Slideshow")
        self.auto_slide_chk.stateChanged.connect(self.toggle_slideshow)
        action_bar.addWidget(self.auto_slide_chk, alignment=Qt.AlignRight)

        main_layout.addLayout(action_bar)

        # Carousel
        self.carousel = QStackedWidget()
        self.card_widgets = []
        for event in self.events:
            card = MissionCarouselCard(event, self.show_fullscreen, self.toggle_favorite)
            self.carousel.addWidget(card)
            self.card_widgets.append(card)
        main_layout.addWidget(self.carousel, 8)

        # Navigation
        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("⟨ Prev")
        prev_btn.clicked.connect(self.prev_slide)
        nav_layout.addWidget(prev_btn)

        self.counter_label = QLabel(self._counter_text())
        nav_layout.addWidget(self.counter_label, alignment=Qt.AlignCenter)

        next_btn = QPushButton("Next ⟩")
        next_btn.clicked.connect(self.next_slide)
        nav_layout.addWidget(next_btn)

        main_layout.addLayout(nav_layout)

        self.prev_btn = prev_btn
        self.next_btn = next_btn
        self._update_nav_buttons()

    def show_fullscreen(self, img_path, title, caption, ts, is_pdf):
        dlg = FullscreenDialog(self, img_path, title, caption, ts, is_pdf)
        dlg.exec()

    def open_gallery_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image or PDF", "",
            "Images/PDF (*.png *.jpg *.jpeg *.pdf);;All Files (*)"
        )
        if not path:
            return
        is_pdf = path.lower().endswith(".pdf")
        self.show_fullscreen(path, os.path.basename(path), "", "", is_pdf)

    def prev_slide(self):
        if self.carousel_index > 0:
            self.carousel_index -= 1
            self.carousel.setCurrentIndex(self.carousel_index)
            self.counter_label.setText(self._counter_text())
            self._update_nav_buttons()

    def next_slide(self):
        if self.carousel_index < len(self.events) - 1:
            self.carousel_index += 1
            self.carousel.setCurrentIndex(self.carousel_index)
            self.counter_label.setText(self._counter_text())
            self._update_nav_buttons()

    def _counter_text(self):
        return f"{self.carousel_index+1} / {len(self.events)}"

    def _update_nav_buttons(self):
        self.prev_btn.setEnabled(self.carousel_index != 0)
        self.next_btn.setEnabled(self.carousel_index != len(self.events) - 1)

    def toggle_slideshow(self, state):
        if state == Qt.Checked:
            self.slideshow_timer.timeout.connect(self.next_slide)
            self.slideshow_timer.start(3000)  # 3 sec
        else:
            self.slideshow_timer.stop()

    def toggle_favorite(self, event, btn):
        event.favorite = not event.favorite
        btn.setText("⭐" if event.favorite else "☆")
