from __future__ import annotations

from scanbox.config.models import AppConfig


class TimeoutPolicy:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def for_engine(self, engine_name: str) -> int:
        mapping = {
            "hash": self._config.timeouts.hash_seconds,
            "clamav": self._config.timeouts.clamav_seconds,
            "yara": self._config.timeouts.yara_seconds,
            "capa": self._config.timeouts.capa_seconds,
        }
        return mapping[engine_name]
