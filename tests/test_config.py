import tempfile
import unittest
from pathlib import Path

from app.config import ConfigStore
from app.models import AppSettings


class ConfigStoreTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            store = ConfigStore(config_path)
            settings = AppSettings(
                input_device_name="Test Mic",
                warning_threshold=42,
                critical_threshold=75,
                overlay_thickness=18,
                show_level_meter=True,
                level_meter_position="top_left",
                hold_ms=650,
                smoothing_factor=0.72,
                update_interval_ms=120,
            )

            store.save(settings)
            loaded = store.load()

            self.assertEqual(loaded, settings.normalized())

    def test_invalid_json_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text("{invalid json", encoding="utf-8")
            store = ConfigStore(config_path)

            with self.assertLogs("app.config", level="WARNING") as logs:
                loaded = store.load()

            self.assertEqual(loaded, AppSettings())
            self.assertTrue(logs.output)


if __name__ == "__main__":
    unittest.main()
