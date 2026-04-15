from __future__ import annotations

from typing import Protocol

from scanbox.config.models import AppConfig
from scanbox.core.models import EngineIssue, EngineScanResult, ScanReport
from scanbox.targets.file_target import FileTarget


class ScannerAdapter(Protocol):
    name: str

    def is_enabled(self, settings: AppConfig) -> bool:
        """Return whether the adapter is enabled in the current configuration."""

    def discover(self, settings: AppConfig) -> EngineIssue | None:
        """Check whether binaries, modules, or rules are available."""

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        """Return whether the adapter supports this target."""

    def scan(
        self,
        target: FileTarget,
        report: ScanReport,
        settings: AppConfig,
        timeout_seconds: int,
    ) -> EngineScanResult:
        """Execute the scan and return a normalized result."""
