from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient, QScreen
from PySide6.QtWidgets import QWidget


class OverlayState(str, Enum):
    OFF = "off"
    WARNING = "warning"
    CRITICAL = "critical"


class ScreenOverlay(QWidget):
    def __init__(self, thickness: int = 12) -> None:
        super().__init__(None)
        self._state = OverlayState.OFF
        self._target_thickness = max(2, thickness)
        self._display_thickness = float(max(2, thickness))
        self._warning_color = QColor(255, 215, 0, 190)
        self._critical_color = QColor(255, 64, 64, 210)
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._tick_thickness_animation)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.hide()

    def attach_to_screen(self, screen: QScreen | None) -> None:
        if screen is None:
            return

        screen.geometryChanged.connect(self._update_geometry)
        self._update_geometry(screen.geometry())

    def set_thickness(self, thickness: int) -> None:
        self._target_thickness = max(2, thickness)
        if abs(self._display_thickness - self._target_thickness) < 0.01:
            self._display_thickness = float(self._target_thickness)
            if self._animation_timer.isActive():
                self._animation_timer.stop()
        elif not self._animation_timer.isActive():
            self._animation_timer.start()
        self.update()

    def set_state(self, state: OverlayState) -> None:
        if self._state == state:
            return

        self._state = state
        if state == OverlayState.OFF:
            self.hide()
        else:
            self.show()
            self.raise_()
            self.update()

    def preview_state(self, state: OverlayState) -> None:
        self.set_state(state)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._state == OverlayState.OFF:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        full_rect = self.rect()
        thickness = max(2, int(round(self._display_thickness)))

        top_rect = QRect(thickness, 0, max(0, full_rect.width() - (2 * thickness)), thickness)
        bottom_rect = QRect(
            thickness,
            full_rect.height() - thickness,
            max(0, full_rect.width() - (2 * thickness)),
            thickness,
        )
        left_rect = QRect(
            0,
            thickness,
            thickness,
            max(0, full_rect.height() - (2 * thickness)),
        )
        right_rect = QRect(
            full_rect.width() - thickness,
            thickness,
            thickness,
            max(0, full_rect.height() - (2 * thickness)),
        )
        top_left_rect = QRect(0, 0, thickness, thickness)
        top_right_rect = QRect(full_rect.width() - thickness, 0, thickness, thickness)
        bottom_left_rect = QRect(0, full_rect.height() - thickness, thickness, thickness)
        bottom_right_rect = QRect(
            full_rect.width() - thickness,
            full_rect.height() - thickness,
            thickness,
            thickness,
        )

        painter.fillRect(top_rect, self._build_vertical_gradient(top_rect, reverse=True))
        painter.fillRect(bottom_rect, self._build_vertical_gradient(bottom_rect, reverse=False))
        painter.fillRect(left_rect, self._build_horizontal_gradient(left_rect, reverse=True))
        painter.fillRect(right_rect, self._build_horizontal_gradient(right_rect, reverse=False))
        painter.fillRect(top_left_rect, self._build_corner_gradient(top_left_rect, "top_left"))
        painter.fillRect(top_right_rect, self._build_corner_gradient(top_right_rect, "top_right"))
        painter.fillRect(
            bottom_left_rect,
            self._build_corner_gradient(bottom_left_rect, "bottom_left"),
        )
        painter.fillRect(
            bottom_right_rect,
            self._build_corner_gradient(bottom_right_rect, "bottom_right"),
        )
        painter.end()

    def _update_geometry(self, geometry) -> None:
        self.setGeometry(geometry)

    def _tick_thickness_animation(self) -> None:
        delta = float(self._target_thickness) - self._display_thickness
        if abs(delta) < 0.01:
            self._display_thickness = float(self._target_thickness)
            self._animation_timer.stop()
        else:
            step = min(6.0, max(1.0, abs(delta) * 0.12))
            if delta > 0:
                self._display_thickness = min(
                    float(self._target_thickness),
                    self._display_thickness + step,
                )
            else:
                self._display_thickness = max(
                    float(self._target_thickness),
                    self._display_thickness - step,
                )

        if self.isVisible():
            self.update()

    def _base_color(self) -> QColor:
        return self._critical_color if self._state == OverlayState.CRITICAL else self._warning_color

    def _transparent_color(self) -> QColor:
        color = QColor(self._base_color())
        color.setAlpha(0)
        return color

    def _build_vertical_gradient(self, rect: QRect, reverse: bool) -> QLinearGradient:
        start_y = rect.bottom() if reverse else rect.top()
        end_y = rect.top() if reverse else rect.bottom()
        gradient = QLinearGradient(rect.left(), start_y, rect.left(), end_y)
        gradient.setColorAt(0.0, self._transparent_color())
        gradient.setColorAt(1.0, self._base_color())
        return gradient

    def _build_horizontal_gradient(self, rect: QRect, reverse: bool) -> QLinearGradient:
        start_x = rect.right() if reverse else rect.left()
        end_x = rect.left() if reverse else rect.right()
        gradient = QLinearGradient(start_x, rect.top(), end_x, rect.top())
        gradient.setColorAt(0.0, self._transparent_color())
        gradient.setColorAt(1.0, self._base_color())
        return gradient

    def _build_corner_gradient(
        self, rect: QRect, corner: str
    ) -> QRadialGradient:
        base_color = self._base_color()
        transparent = self._transparent_color()
        rect_f = QRectF(rect)

        centers = {
            "top_left": rect_f.bottomRight(),
            "top_right": rect_f.bottomLeft(),
            "bottom_left": rect_f.topRight(),
            "bottom_right": rect_f.topLeft(),
        }

        center = centers[corner]
        radius = max(rect_f.width(), rect_f.height())
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(1.0, base_color)
        return gradient


class NoiseLevelOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self._screen: QScreen | None = None
        self._target_level = 0.0
        self._display_level = 0.0
        self._position = "bottom_right"
        self._margin = 24
        self._overlay_width = 54
        self._overlay_height = 180
        self._decay_step = 1.6
        self._decay_timer = QTimer(self)
        self._decay_timer.setInterval(16)
        self._decay_timer.timeout.connect(self._tick_decay)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.hide()

    def attach_to_screen(self, screen: QScreen | None) -> None:
        if screen is None:
            return

        self._screen = screen
        screen.geometryChanged.connect(self._update_geometry)
        self._update_geometry(screen.geometry())

    def configure(self, visible: bool, position: str) -> None:
        self._position = position
        self._reposition()
        if visible:
            self.show()
            self.raise_()
            self.update()
            return
        self.hide()

    def set_level(self, level: float) -> None:
        self._target_level = max(0.0, min(100.0, level))
        if self._target_level >= self._display_level:
            self._display_level = self._target_level
            if self._decay_timer.isActive():
                self._decay_timer.stop()
        elif not self._decay_timer.isActive():
            self._decay_timer.start()

        if self.isVisible():
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        outer_rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QColor(18, 18, 22, 145))
        painter.drawRoundedRect(outer_rect, 14, 14)

        text_rect = QRect(outer_rect.left() + 4, outer_rect.top() + 6, outer_rect.width() - 8, 18)
        inner_rect = outer_rect.adjusted(9, 30, -9, -9)
        painter.setBrush(QColor(255, 255, 255, 26))
        painter.drawRoundedRect(inner_rect, 10, 10)

        fill_height = int(inner_rect.height() * (self._display_level / 100.0))
        if fill_height > 0:
            fill_rect = QRect(
                inner_rect.left(),
                inner_rect.bottom() - fill_height + 1,
                inner_rect.width(),
                fill_height,
            )
            gradient = QLinearGradient(fill_rect.left(), fill_rect.bottom(), fill_rect.left(), fill_rect.top())
            gradient.setColorAt(0.0, QColor(70, 210, 120, 210))
            gradient.setColorAt(0.65, QColor(255, 210, 70, 220))
            gradient.setColorAt(1.0, QColor(255, 95, 95, 235))
            painter.setBrush(gradient)
            painter.drawRoundedRect(fill_rect, 10, 10)

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(outer_rect, 14, 14)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor(245, 245, 245, 220))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            str(int(round(self._display_level))),
        )
        painter.end()

    def _tick_decay(self) -> None:
        if self._display_level <= self._target_level:
            self._display_level = self._target_level
            self._decay_timer.stop()
        else:
            self._display_level = max(self._target_level, self._display_level - self._decay_step)

        if self.isVisible():
            self.update()

    def _update_geometry(self, geometry) -> None:
        self._reposition(geometry)

    def _reposition(self, geometry=None) -> None:
        if geometry is None:
            geometry = self._screen.geometry() if self._screen is not None else None
        if geometry is None:
            return

        width = self._overlay_width
        height = self._overlay_height
        margin = self._margin
        bottom_extra_offset = 20

        x_map = {
            "top_left": geometry.left() + margin,
            "bottom_left": geometry.left() + margin,
            "center_left": geometry.left() + margin,
            "top_right": geometry.right() - width - margin + 1,
            "bottom_right": geometry.right() - width - margin + 1,
            "center_right": geometry.right() - width - margin + 1,
        }
        y_map = {
            "top_left": geometry.top() + margin,
            "top_right": geometry.top() + margin,
            "bottom_left": geometry.bottom() - height - margin - bottom_extra_offset + 1,
            "bottom_right": geometry.bottom() - height - margin - bottom_extra_offset + 1,
            "center_left": geometry.center().y() - (height // 2),
            "center_right": geometry.center().y() - (height // 2),
        }

        self.setGeometry(x_map[self._position], y_map[self._position], width, height)
