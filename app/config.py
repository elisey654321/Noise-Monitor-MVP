from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import AppSettings


def default_config_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "NoiseMonitorMVP" / "config.json"
    return Path.home() / ".noise-monitor-mvp.json"


class ConfigStore:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or default_config_path()

    def load(self) -> AppSettings:
        if not self.config_path.exists():
            return AppSettings()

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()

        return AppSettings.from_dict(payload)

    def save(self, settings: AppSettings) -> None:
        normalized = settings.normalized()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
