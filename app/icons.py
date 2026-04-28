from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle


ICON_PATH = Path(__file__).resolve().parent / "assets" / "noise_monitor.ico"


def get_app_icon() -> QIcon:
    if ICON_PATH.exists():
        return QIcon(str(ICON_PATH))

    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume)
