from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.icons import get_app_icon


class AppTray(QSystemTrayIcon):
    def __init__(self, settings_window: QWidget, on_quit: Callable[[], None]) -> None:
        icon = get_app_icon()
        super().__init__(icon)
        self._settings_window = settings_window
        self._on_quit = on_quit
        self.setToolTip("Noise Monitor MVP")

        menu = QMenu()
        open_action = QAction("Настройки", self)
        open_action.triggered.connect(self.show_settings)
        menu.addAction(open_action)

        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self._on_quit)
        menu.addAction(exit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._handle_activation)

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_settings()

    def show_settings(self) -> None:
        self._settings_window.setWindowState(
            self._settings_window.windowState() & ~Qt.WindowState.WindowMinimized
        )
        self._settings_window.showNormal()
        self._settings_window.raise_()
        self._settings_window.activateWindow()
