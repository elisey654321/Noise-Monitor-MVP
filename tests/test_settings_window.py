import unittest

from app.models import AppSettings, AudioDeviceInfo

try:
    from PySide6.QtWidgets import QApplication
    from app.settings_window import SettingsWindow
except ModuleNotFoundError:
    QApplication = None
    SettingsWindow = None


@unittest.skipIf(QApplication is None or SettingsWindow is None, "PySide6 is not installed")
class SettingsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_current_settings_preserves_hidden_fields(self) -> None:
        window = SettingsWindow()
        window.set_devices(
            [
                AudioDeviceInfo(
                    index=0,
                    name="Mic 1",
                    max_input_channels=1,
                    default_samplerate=44_100.0,
                )
            ],
            selected_name="Mic 1",
        )
        settings = AppSettings(
            input_device_name="Mic 1",
            warning_threshold=40,
            critical_threshold=70,
            overlay_thickness=20,
            show_level_meter=True,
            level_meter_position="top_right",
            hold_ms=500,
            smoothing_factor=0.81,
            update_interval_ms=135,
        )

        try:
            window.set_settings(settings)

            current = window.current_settings()

            self.assertEqual(current.smoothing_factor, 0.81)
            self.assertEqual(current.update_interval_ms, 135)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
