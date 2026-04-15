from pathlib import Path

from scanbox.config.models import AppConfig, AppSettings, EngineSettings, QuarantineSettings, TimeoutSettings
from scanbox.core.enums import EngineState, ScanProfile
from scanbox.core.models import EngineIssue, RuleSetInfo, ScanReport, TargetInfo
from scanbox.pipeline.preflight import apply_preflight
from scanbox.targets.file_target import FileTarget


class FakeAdapter:
    def __init__(self, name: str, issue: EngineIssue | None) -> None:
        self.name = name
        self._issue = issue

    def is_enabled(self, settings: AppConfig) -> bool:
        return True

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        return True

    def discover(self, settings: AppConfig) -> EngineIssue | None:
        return self._issue


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


def make_target(tmp_path: Path) -> FileTarget:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"sample")
    return FileTarget.from_path(sample)


def make_report(target: FileTarget) -> ScanReport:
    return ScanReport(
        profile=ScanProfile.BALANCED,
        target=TargetInfo(
            original_path=str(target.path),
            normalized_path=str(target.path),
            size=target.size,
            detected_type="pe",
            extension=target.extension,
        ),
        rulesets={
            "yara": RuleSetInfo(name="yara", version="1", source="test", pinned_ref="x"),
            "capa": RuleSetInfo(name="capa", version="1", source="test", pinned_ref="x"),
        },
    )


def test_preflight_maps_rules_placeholder_to_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    target = make_target(tmp_path)
    report = make_report(target)
    issue = EngineIssue(engine="capa", code="rules_placeholder", message="placeholder", details={"rules_dir": "x"})

    results = apply_preflight([FakeAdapter("capa", issue)], target, report, config)

    assert results["capa"].state == EngineState.MISSING
    assert results["capa"].raw_summary["preflight_issue_code"] == "rules_placeholder"


def test_preflight_maps_manifest_mismatch_to_unavailable(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    target = make_target(tmp_path)
    report = make_report(target)
    issue = EngineIssue(engine="capa", code="manifest_mismatch", message="mismatch", details={"manifest_path": "x"})

    results = apply_preflight([FakeAdapter("capa", issue)], target, report, config)

    assert results["capa"].state == EngineState.UNAVAILABLE
    assert results["capa"].raw_summary["preflight_issue_code"] == "manifest_mismatch"


def test_preflight_maps_configured_path_invalid_to_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    target = make_target(tmp_path)
    report = make_report(target)
    issue = EngineIssue(
        engine="clamav",
        code="configured_path_invalid",
        message="invalid path",
        details={"field": "executable", "path": "x"},
    )

    results = apply_preflight([FakeAdapter("clamav", issue)], target, report, config)

    assert results["clamav"].state == EngineState.MISSING
    assert results["clamav"].raw_summary["preflight_issue_code"] == "configured_path_invalid"
