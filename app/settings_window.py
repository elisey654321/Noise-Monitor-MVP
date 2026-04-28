from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.models import AppSettings, AudioDeviceInfo
from app.overlay import OverlayState
from app.version import __version__


class SettingsWindow(QWidget):
    settings_applied = Signal(AppSettings)
    refresh_requested = Signal()
    preview_requested = Signal(object)
    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Noise Monitor MVP v{__version__}")
        self.setMinimumWidth(420)
        defaults = AppSettings()
        self._smoothing_factor = defaults.smoothing_factor
        self._update_interval_ms = defaults.update_interval_ms

        self.device_combo = QComboBox()
        self.refresh_button = QPushButton("Обновить список")
        self.warning_spin = QSpinBox()
        self.critical_spin = QSpinBox()
        self.hold_spin = QSpinBox()
        self.thickness_spin = QSpinBox()
        self.show_level_meter_checkbox = QCheckBox("Показывать шкалу шума поверх окон")
        self.level_meter_position_combo = QComboBox()
        self.level_bar = QProgressBar()
        self.level_label = QLabel("0 / 100")
        self.status_label = QLabel("Готово к настройке")
        self.version_label = QLabel(f"Версия: {__version__}")
        self.save_button = QPushButton("Сохранить")
        self.preview_warning_button = QPushButton("Проверить желтый")
        self.preview_critical_button = QPushButton("Проверить красный")
        self.preview_off_button = QPushButton("Скрыть рамку")
        self.history_toggle = QToolButton()
        self.history_period_combo = QComboBox()
        self.history_series = QLineSeries()
        self.history_axis_x = QValueAxis()
        self.history_axis_y = QValueAxis()
        self.history_chart_view = self._build_history_chart()
        self.history_container = QWidget()

        self._configure_inputs()
        self._build_layout()
        self._wire_signals()

    def _configure_inputs(self) -> None:
        self.warning_spin.setRange(0, 99)
        self.critical_spin.setRange(1, 100)
        self.hold_spin.setRange(0, 5_000)
        self.hold_spin.setSingleStep(50)
        self.hold_spin.setSuffix(" мс")
        self.thickness_spin.setRange(2, 256)
        self.thickness_spin.setSuffix(" px")

        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.status_label.setWordWrap(True)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.level_meter_position_combo.addItem("Слева сверху", "top_left")
        self.level_meter_position_combo.addItem("Справа сверху", "top_right")
        self.level_meter_position_combo.addItem("Слева снизу", "bottom_left")
        self.level_meter_position_combo.addItem("Справа снизу", "bottom_right")
        self.level_meter_position_combo.addItem("Слева по центру", "center_left")
        self.level_meter_position_combo.addItem("Справа по центру", "center_right")
        self.level_meter_position_combo.setEnabled(False)
        self.history_toggle.setText("Показать график")
        self.history_toggle.setCheckable(True)
        self.history_toggle.setChecked(False)
        self.history_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.history_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.history_period_combo.addItem("1 мин", 60)
        self.history_period_combo.addItem("2 мин", 120)
        self.history_period_combo.addItem("5 мин", 300)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)

        source_group = QGroupBox("Источник")
        source_layout = QFormLayout(source_group)
        combo_row = QHBoxLayout()
        combo_row.addWidget(self.device_combo, 1)
        combo_row.addWidget(self.refresh_button)
        source_layout.addRow("Микрофон", combo_row)

        thresholds_group = QGroupBox("Пороги")
        thresholds_layout = QFormLayout(thresholds_group)
        thresholds_layout.addRow("Желтый уровень", self.warning_spin)
        thresholds_layout.addRow("Красный уровень", self.critical_spin)
        thresholds_layout.addRow("Задержка скрытия", self.hold_spin)
        thresholds_layout.addRow("Толщина рамки", self.thickness_spin)
        thresholds_layout.addRow(self.show_level_meter_checkbox)
        thresholds_layout.addRow("Позиция шкалы", self.level_meter_position_combo)

        level_group = QGroupBox("Текущий шум")
        level_layout = QVBoxLayout(level_group)
        level_layout.addWidget(self.level_bar)
        level_layout.addWidget(self.level_label, alignment=Qt.AlignmentFlag.AlignRight)

        history_group = QGroupBox("История шума")
        history_layout = QVBoxLayout(history_group)
        history_controls = QHBoxLayout()
        history_controls.addWidget(self.history_toggle)
        history_controls.addStretch(1)
        history_controls.addWidget(QLabel("Период"))
        history_controls.addWidget(self.history_period_combo)
        history_container_layout = QVBoxLayout(self.history_container)
        history_container_layout.setContentsMargins(0, 0, 0, 0)
        history_container_layout.addWidget(self.history_chart_view)
        self.history_container.hide()
        history_layout.addLayout(history_controls)
        history_layout.addWidget(self.history_container)

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview_warning_button)
        preview_row.addWidget(self.preview_critical_button)
        preview_row.addWidget(self.preview_off_button)

        actions_row = QHBoxLayout()
        actions_row.addWidget(self.version_label)
        actions_row.addStretch(1)
        actions_row.addWidget(self.save_button)

        root.addWidget(source_group)
        root.addWidget(thresholds_group)
        root.addWidget(level_group)
        root.addWidget(history_group)
        root.addLayout(preview_row)
        root.addWidget(self.status_label)
        root.addLayout(actions_row)

    def _wire_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.save_button.clicked.connect(self._emit_settings)
        self.preview_warning_button.clicked.connect(
            lambda: self.preview_requested.emit(OverlayState.WARNING)
        )
        self.preview_critical_button.clicked.connect(
            lambda: self.preview_requested.emit(OverlayState.CRITICAL)
        )
        self.preview_off_button.clicked.connect(
            lambda: self.preview_requested.emit(OverlayState.OFF)
        )
        self.warning_spin.valueChanged.connect(self._sync_thresholds)
        self.show_level_meter_checkbox.toggled.connect(
            self.level_meter_position_combo.setEnabled
        )
        self.history_toggle.toggled.connect(self._toggle_history)

    def set_devices(
        self, devices: list[AudioDeviceInfo], selected_name: str = ""
    ) -> None:
        self.device_combo.clear()
        for device in devices:
            self.device_combo.addItem(device.name, device.name)

        if not devices:
            self.device_combo.addItem("Микрофоны не найдены", "")
            self.device_combo.setEnabled(False)
            return

        self.device_combo.setEnabled(True)
        index = self.device_combo.findData(selected_name)
        if index < 0:
            index = 0
        self.device_combo.setCurrentIndex(index)

    def set_settings(self, settings: AppSettings) -> None:
        normalized = settings.normalized()
        self._smoothing_factor = normalized.smoothing_factor
        self._update_interval_ms = normalized.update_interval_ms
        self.warning_spin.setValue(normalized.warning_threshold)
        self.critical_spin.setValue(normalized.critical_threshold)
        self.hold_spin.setValue(normalized.hold_ms)
        self.thickness_spin.setValue(normalized.overlay_thickness)
        self.show_level_meter_checkbox.setChecked(normalized.show_level_meter)
        index = self.level_meter_position_combo.findData(normalized.level_meter_position)
        if index >= 0:
            self.level_meter_position_combo.setCurrentIndex(index)
        self.level_meter_position_combo.setEnabled(normalized.show_level_meter)

        if self.device_combo.count() > 0:
            index = self.device_combo.findData(normalized.input_device_name)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

    def set_level(self, level: float) -> None:
        rounded = int(round(level))
        self.level_bar.setValue(rounded)
        self.level_label.setText(f"{rounded} / 100")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def selected_history_period_seconds(self) -> int:
        return int(self.history_period_combo.currentData() or 60)

    def set_history_points(
        self, points: list[tuple[float, float]], period_seconds: int
    ) -> None:
        if not self.history_toggle.isChecked():
            return

        self.history_axis_x.setRange(0, period_seconds)
        self.history_series.replace(
            [QPointF(float(x), float(y)) for x, y in points]
        )

    def _emit_settings(self) -> None:
        self.settings_applied.emit(self.current_settings())

    def current_settings(self) -> AppSettings:
        input_device_name = self.device_combo.currentData() or ""
        return AppSettings(
            input_device_name=str(input_device_name),
            warning_threshold=self.warning_spin.value(),
            critical_threshold=self.critical_spin.value(),
            overlay_thickness=self.thickness_spin.value(),
            show_level_meter=self.show_level_meter_checkbox.isChecked(),
            level_meter_position=str(self.level_meter_position_combo.currentData() or "bottom_right"),
            hold_ms=self.hold_spin.value(),
            smoothing_factor=self._smoothing_factor,
            update_interval_ms=self._update_interval_ms,
        ).normalized()

    def _sync_thresholds(self, warning_value: int) -> None:
        self.critical_spin.setMinimum(min(100, warning_value + 1))

    def _toggle_history(self, checked: bool) -> None:
        self.history_container.setVisible(checked)
        self.history_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self.history_toggle.setText("Скрыть график" if checked else "Показать график")

    def changeEvent(self, event) -> None:  # type: ignore[override]
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self._hide_to_tray)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self._hide_to_tray()
            return

        event.accept()
        self.close_requested.emit()

    def _hide_to_tray(self) -> None:
        if not self.isMinimized():
            return
        self.hide()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)

    def _build_history_chart(self) -> QChartView:
        chart = QChart()
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.addSeries(self.history_series)

        self.history_axis_x.setTitleText("Время (сек)")
        self.history_axis_x.setLabelFormat("%d")
        self.history_axis_x.setRange(0, 60)
        self.history_axis_x.setTickCount(7)
        chart.addAxis(self.history_axis_x, Qt.AlignmentFlag.AlignBottom)
        self.history_series.attachAxis(self.history_axis_x)

        self.history_axis_y.setTitleText("Громкость")
        self.history_axis_y.setLabelFormat("%d")
        self.history_axis_y.setRange(0, 100)
        self.history_axis_y.setTickCount(6)
        chart.addAxis(self.history_axis_y, Qt.AlignmentFlag.AlignLeft)
        self.history_series.attachAxis(self.history_axis_y)

        pen = self.history_series.pen()
        pen.setWidth(2)
        pen.setColor(Qt.GlobalColor.yellow)
        self.history_series.setPen(pen)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        chart_view.setMinimumHeight(180)
        return chart_view
