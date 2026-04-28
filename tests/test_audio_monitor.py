import unittest

try:
    from app.audio_monitor import AudioMonitor
except ModuleNotFoundError:
    AudioMonitor = None


@unittest.skipIf(AudioMonitor is None, "sounddevice is not installed")
class AudioMonitorTests(unittest.TestCase):
    def test_normalize_level_clamps_to_supported_range(self) -> None:
        self.assertEqual(AudioMonitor._normalize_level(0.0), 0.0)
        self.assertGreater(AudioMonitor._normalize_level(0.01), 0.0)
        self.assertEqual(AudioMonitor._normalize_level(10.0), 100.0)


if __name__ == "__main__":
    unittest.main()
