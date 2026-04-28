import unittest

from app.models import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_normalized_clamps_ranges(self) -> None:
        settings = AppSettings(
            warning_threshold=-5,
            critical_threshold=500,
            overlay_thickness=999,
            hold_ms=99999,
            smoothing_factor=5.0,
            update_interval_ms=1,
        ).normalized()

        self.assertEqual(settings.warning_threshold, 0)
        self.assertEqual(settings.critical_threshold, 100)
        self.assertEqual(settings.overlay_thickness, 256)
        self.assertEqual(settings.hold_ms, 5_000)
        self.assertEqual(settings.smoothing_factor, 0.99)
        self.assertEqual(settings.update_interval_ms, 16)

    def test_normalized_keeps_critical_above_warning(self) -> None:
        settings = AppSettings(
            warning_threshold=80,
            critical_threshold=70,
        ).normalized()

        self.assertEqual(settings.warning_threshold, 80)
        self.assertEqual(settings.critical_threshold, 81)


if __name__ == "__main__":
    unittest.main()
