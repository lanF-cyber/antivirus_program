from pathlib import Path

from scanbox.config.models import AppConfig, AppSettings, EngineSettings, QuarantineSettings, TimeoutSettings
from scanbox.core.enums import VerdictStatus
from scanbox.core.models import QuarantineMode, ScanReport
from scanbox.quarantine.service import QuarantineService
from scanbox.targets.file_target import FileTarget


def test_quarantine_dry_run_for_known_malicious(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"malicious")

    config = AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )

    report = ScanReport()
    report.overall_status = VerdictStatus.KNOWN_MALICIOUS

    action = QuarantineService(config).maybe_apply(
        report=report,
        target=FileTarget.from_path(sample),
        requested_mode=QuarantineMode.MOVE,
        dry_run=True,
    )

    assert action.performed is False
    assert action.reason == "dry_run_requested"
    assert sample.exists()
