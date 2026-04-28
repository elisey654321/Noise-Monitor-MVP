from __future__ import annotations

from dataclasses import asdict, dataclass

METER_POSITIONS = (
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "center_left",
    "center_right",
)


@dataclass(slots=True)
class AudioDeviceInfo:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


@dataclass(slots=True)
class AppSettings:
    input_device_name: str = ""
    warning_threshold: int = 35
    critical_threshold: int = 55
    overlay_thickness: int = 12
    show_level_meter: bool = False
    level_meter_position: str = "bottom_right"
    hold_ms: int = 400
    smoothing_factor: float = 0.35
    update_interval_ms: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> "AppSettings":
        if not data:
            return cls()

        return cls(
            input_device_name=str(data.get("input_device_name", "")),
            warning_threshold=int(data.get("warning_threshold", 35)),
            critical_threshold=int(data.get("critical_threshold", 55)),
            overlay_thickness=int(data.get("overlay_thickness", 12)),
            show_level_meter=bool(data.get("show_level_meter", False)),
            level_meter_position=str(data.get("level_meter_position", "bottom_right")),
            hold_ms=int(data.get("hold_ms", 400)),
            smoothing_factor=float(data.get("smoothing_factor", 0.35)),
            update_interval_ms=int(data.get("update_interval_ms", 50)),
        ).normalized()

    def normalized(self) -> "AppSettings":
        warning = max(0, min(100, self.warning_threshold))
        critical = max(warning + 1, min(100, self.critical_threshold))
        thickness = max(2, min(256, self.overlay_thickness))
        meter_position = (
            self.level_meter_position
            if self.level_meter_position in METER_POSITIONS
            else "bottom_right"
        )
        hold_ms = max(0, min(5_000, self.hold_ms))
        smoothing = max(0.01, min(0.99, self.smoothing_factor))
        update_interval = max(16, min(500, self.update_interval_ms))

        return AppSettings(
            input_device_name=self.input_device_name.strip(),
            warning_threshold=warning,
            critical_threshold=critical,
            overlay_thickness=thickness,
            show_level_meter=bool(self.show_level_meter),
            level_meter_position=meter_position,
            hold_ms=hold_ms,
            smoothing_factor=smoothing,
            update_interval_ms=update_interval,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self.normalized())
