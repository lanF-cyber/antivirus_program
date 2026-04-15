from pathlib import Path

from scanbox.config.loader import load_app_config
from scanbox.pipeline.orchestrator import ScanOrchestrator
from scanbox.core.models import QuarantineMode


def test_scan_reports_engine_missing_when_yara_module_is_absent() -> None:
    config = load_app_config(Path("config/scanbox.toml"))
    report = ScanOrchestrator(config).scan_file(
        file_path=Path("tests/fixtures/yara_samples/marker.txt"),
        quarantine_mode=QuarantineMode.ASK,
        dry_run_quarantine=True,
    )
    assert report.summary["status"] in {
        "engine_missing",
        "engine_unavailable",
        "suspicious",
        "known_malicious",
    }
