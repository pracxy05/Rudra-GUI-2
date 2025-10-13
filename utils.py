from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import os


def safe_pixmap(path: str, width: int = None, height: int = None):
    """Load a pixmap safely, return None if invalid. Optionally scale it."""
    if not os.path.exists(path):
        return None
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    if width and height:
        return pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return pixmap
