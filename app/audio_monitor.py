from __future__ import annotations

import math
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QTimer, Signal

from app.models import AppSettings, AudioDeviceInfo


class AudioMonitor(QObject):
    level_changed = Signal(float)
    status_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stream: sd.InputStream | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._publish_level)
        self._latest_level = 0.0
        self._display_level = 0.0
        self._lock = threading.Lock()
        self._settings = AppSettings()

    def list_input_devices(self) -> list[AudioDeviceInfo]:
        devices: list[AudioDeviceInfo] = []
        try:
            queried = sd.query_devices()
        except Exception as exc:
            self.status_changed.emit(f"Не удалось получить список микрофонов: {exc}")
            return devices

        for index, device in enumerate(queried):
            max_input_channels = int(device.get("max_input_channels", 0))
            if max_input_channels <= 0:
                continue
            devices.append(
                AudioDeviceInfo(
                    index=index,
                    name=str(device.get("name", f"Input {index}")),
                    max_input_channels=max_input_channels,
                    default_samplerate=float(device.get("default_samplerate", 44_100)),
                )
            )
        return devices

    def start(self, settings: AppSettings) -> str | None:
        self.stop()
        self._settings = settings.normalized()

        try:
            device_info = self._resolve_device(self._settings.input_device_name)
            samplerate = float(device_info.get("default_samplerate") or 44_100)
            channels = min(int(device_info.get("max_input_channels", 1)), 2)
            device_index = int(device_info["index"])

            self._stream = sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=samplerate,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            self.status_changed.emit(f"Не удалось запустить микрофон: {exc}")
            self.level_changed.emit(0.0)
            return None

        self._timer.start(self._settings.update_interval_ms)
        device_name = str(device_info.get("name", "микрофон"))
        self.status_changed.emit(f"Слушаю: {device_name}")
        return device_name

    def stop(self) -> None:
        self._timer.stop()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            self._latest_level = 0.0
            self._display_level = 0.0
        self.level_changed.emit(0.0)

    def _publish_level(self) -> None:
        with self._lock:
            level = self._display_level
        self.level_changed.emit(level)

    def _resolve_device(self, preferred_name: str) -> dict[str, object]:
        devices = self.list_input_devices()
        if not devices:
            raise RuntimeError("В системе не найдено ни одного входного устройства")

        if preferred_name:
            for device in devices:
                if device.name == preferred_name:
                    return {
                        "index": device.index,
                        "name": device.name,
                        "max_input_channels": device.max_input_channels,
                        "default_samplerate": device.default_samplerate,
                    }

        default_input = sd.default.device[0]
        if default_input is not None and int(default_input) >= 0:
            info = sd.query_devices(int(default_input))
            if int(info.get("max_input_channels", 0)) > 0:
                return {
                    "index": int(default_input),
                    "name": str(info.get("name", "Default input")),
                    "max_input_channels": int(info.get("max_input_channels", 1)),
                    "default_samplerate": float(info.get("default_samplerate", 44_100)),
                }

        fallback = devices[0]
        return {
            "index": fallback.index,
            "name": fallback.name,
            "max_input_channels": fallback.max_input_channels,
            "default_samplerate": fallback.default_samplerate,
        }

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Callable[..., object],
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            self.status_changed.emit(f"Проблема со звуком: {status}")

        if frames <= 0:
            return

        samples = np.asarray(indata, dtype=np.float32)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)

        rms = float(np.sqrt(np.mean(np.square(samples))))
        normalized = self._normalize_level(rms)

        with self._lock:
            previous = self._latest_level
            smoothed = (self._settings.smoothing_factor * normalized) + (
                (1.0 - self._settings.smoothing_factor) * previous
            )
            self._latest_level = smoothed
            self._display_level = smoothed

    @staticmethod
    def _normalize_level(rms: float) -> float:
        if rms <= 0.0:
            return 0.0

        db = 20.0 * math.log10(max(rms, 1e-7))
        normalized = (db + 60.0) / 60.0 * 100.0
        return max(0.0, min(100.0, normalized))
