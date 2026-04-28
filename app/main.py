from __future__ import annotations

from collections import deque
import logging
from logging.handlers import RotatingFileHandler
import sys
import time

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.audio_monitor import AudioMonitor
from app.config import ConfigStore, default_log_path
from app.icons import get_app_icon
from app.models import AppSettings
from app.overlay import NoiseLevelOverlay, OverlayState, ScreenOverlay
from app.single_instance import SingleInstanceGuard
from app.settings_window import SettingsWindow
from app.tray import AppTray
from app.version import __version__


def configure_logging() -> None:
    log_path = default_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=512 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


class AppController(QObject):
    _min_warning_thickness = 2

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.config_store = ConfigStore()
        self.settings = self.config_store.load()
        self.monitor = AudioMonitor(self)
        self.overlay = ScreenOverlay(self.settings.overlay_thickness)
        self.level_overlay = NoiseLevelOverlay()
        self.window = SettingsWindow()
        self.tray = AppTray(self.window, self.shutdown)
        self._hold_until = 0.0
        self._current_state = OverlayState.OFF
        self._is_shutting_down = False
        self._level_history: deque[tuple[float, float]] = deque()
        self._history_retention_seconds = 300.0
        self._history_chart_timer = QTimer(self)
        self._history_chart_timer.setInterval(250)

        self._wire_signals()
        self._bootstrap_ui()

    def _wire_signals(self) -> None:
        self.monitor.level_changed.connect(self._handle_level)
        self.monitor.status_changed.connect(self.window.set_status)
        self.window.settings_applied.connect(self.apply_settings)
        self.window.refresh_requested.connect(self.refresh_devices)
        self.window.preview_requested.connect(self._preview_overlay)
        self.window.close_requested.connect(self.shutdown)
        self._history_chart_timer.timeout.connect(self._refresh_history_chart)

    def _bootstrap_ui(self) -> None:
        screen = self.app.primaryScreen()
        self.overlay.attach_to_screen(screen)
        self.level_overlay.attach_to_screen(screen)
        self.app.setWindowIcon(self.tray.icon())
        self.window.setWindowIcon(self.tray.icon())

        self.refresh_devices()
        self.window.set_settings(self.settings)
        self.tray.show()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.warning(
                self.window,
                "Нет системного трея",
                "Системный трей недоступен. Окно останется открытым постоянно.",
            )
        self.window.show()
        self._history_chart_timer.start()

        self.apply_settings(self.settings, persist=False)

    def refresh_devices(self) -> None:
        devices = self.monitor.list_input_devices()
        selected_name = (
            self.window.current_settings().input_device_name or self.settings.input_device_name
        )
        self.window.set_devices(devices, selected_name)
        if devices:
            self.window.set_status(f"Найдено микрофонов: {len(devices)}")
        else:
            self.window.set_status("Входные устройства не найдены")

    def apply_settings(self, settings: AppSettings, persist: bool = True) -> None:
        self.settings = settings.normalized()
        self.overlay.set_thickness(self.settings.overlay_thickness)
        self.level_overlay.configure(
            self.settings.show_level_meter,
            self.settings.level_meter_position,
        )
        active_device_name = self.monitor.start(self.settings)
        if active_device_name:
            self.settings = AppSettings(
                input_device_name=active_device_name,
                warning_threshold=self.settings.warning_threshold,
                critical_threshold=self.settings.critical_threshold,
                overlay_thickness=self.settings.overlay_thickness,
                show_level_meter=self.settings.show_level_meter,
                level_meter_position=self.settings.level_meter_position,
                hold_ms=self.settings.hold_ms,
                smoothing_factor=self.settings.smoothing_factor,
                update_interval_ms=self.settings.update_interval_ms,
            ).normalized()
        self.window.set_settings(self.settings)
        if persist:
            self.config_store.save(self.settings)
            self.window.set_status("Настройки сохранены")

    def _handle_level(self, level: float) -> None:
        self.window.set_level(level)
        self.level_overlay.set_level(level)
        now_seconds = time.monotonic()
        now_ms = now_seconds * 1_000
        self._append_level_history(now_seconds, level)

        if level >= self.settings.critical_threshold:
            self._hold_until = now_ms + self.settings.hold_ms
            self.overlay.set_thickness(self.settings.overlay_thickness)
            self._set_overlay_state(OverlayState.CRITICAL)
            return

        if level >= self.settings.warning_threshold:
            self._hold_until = now_ms + self.settings.hold_ms
            self.overlay.set_thickness(self._warning_thickness_for_level(level))
            self._set_overlay_state(OverlayState.WARNING)
            return

        if now_ms < self._hold_until:
            return

        self.overlay.set_thickness(self.settings.overlay_thickness)
        self._set_overlay_state(OverlayState.OFF)

    def _preview_overlay(self, state: OverlayState) -> None:
        if state == OverlayState.OFF:
            self._hold_until = 0.0
            self.overlay.set_thickness(self.settings.overlay_thickness)
            self._set_overlay_state(OverlayState.OFF)
            return

        self._hold_until = time.monotonic() * 1_000 + 1_500
        if state == OverlayState.WARNING:
            self.overlay.set_thickness(self._warning_thickness_for_level(self.settings.warning_threshold))
        else:
            self.overlay.set_thickness(self.settings.overlay_thickness)
        self._set_overlay_state(state)

    def _set_overlay_state(self, state: OverlayState) -> None:
        if self._current_state == state:
            return
        self._current_state = state
        self.overlay.set_state(state)

    def _warning_thickness_for_level(self, level: float) -> int:
        min_thickness = min(self._min_warning_thickness, self.settings.overlay_thickness)
        warning = float(self.settings.warning_threshold)
        critical = float(self.settings.critical_threshold)

        if level <= warning:
            return min_thickness
        if level >= critical:
            return self.settings.overlay_thickness

        progress = (level - warning) / max(1.0, critical - warning)
        dynamic_thickness = min_thickness + (
            (self.settings.overlay_thickness - min_thickness) * progress
        )
        return max(min_thickness, int(round(dynamic_thickness)))

    def _append_level_history(self, timestamp: float, level: float) -> None:
        self._level_history.append((timestamp, level))
        self._prune_level_history(timestamp)

    def _prune_level_history(self, now_seconds: float) -> None:
        min_timestamp = now_seconds - self._history_retention_seconds
        while self._level_history and self._level_history[0][0] < min_timestamp:
            self._level_history.popleft()

    def _refresh_history_chart(self) -> None:
        now_seconds = time.monotonic()
        self._prune_level_history(now_seconds)
        period_seconds = self.window.selected_history_period_seconds()
        min_timestamp = now_seconds - period_seconds
        points = [
            (timestamp - min_timestamp, level)
            for timestamp, level in self._level_history
            if timestamp >= min_timestamp
        ]
        self.window.set_history_points(points, period_seconds)

    def show_window(self) -> None:
        self.tray.show_settings()

    def shutdown(self) -> None:
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        self._history_chart_timer.stop()
        self.monitor.stop()
        self.tray.hide()
        self.overlay.hide()
        self.level_overlay.hide()
        self.app.quit()


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(f"Noise Monitor MVP v{__version__}")
    app.setWindowIcon(get_app_icon())
    app.setQuitOnLastWindowClosed(False)

    if SingleInstanceGuard.notify_existing_instance():
        return 0

    instance_guard = SingleInstanceGuard()
    if not instance_guard.start():
        return 1

    controller = AppController(app)
    instance_guard.activation_requested.connect(controller.show_window)
    app.aboutToQuit.connect(instance_guard.close)
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
