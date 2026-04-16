from pathlib import Path
from types import SimpleNamespace

import scanbox.adapters.yara as yara_module
from scanbox.adapters.yara import YaraAdapter
from scanbox.core.enums import ScanProfile
from scanbox.core.models import build_report_shell
from scanbox.config.models import AppConfig, AppSettings, EngineBinarySettings, EngineSettings, QuarantineSettings, TimeoutSettings
from scanbox.targets.file_target import FileTarget


def test_yara_detection_uses_meta_not_legacy_strings_shape() -> None:
    fake_match = SimpleNamespace(
        rule="scanbox_test_rule",
        namespace="default",
        tags=["suspicious"],
        meta={
            "title": "Test rule",
            "description": "Test description",
            "severity": "medium",
            "confidence": "medium",
            "category": "suspicious",
        },
    )

    detection = YaraAdapter()._detection_from_match(fake_match)

    assert detection.rule_id == "scanbox_test_rule"
    assert detection.category == "suspicious"
    assert detection.evidence["meta"]["title"] == "Test rule"


def make_config(tmp_path: Path, rules_dir: Path | None, manifest: Path | None) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(
            yara=EngineBinarySettings(
                enabled=True,
                rules_dir=rules_dir,
                manifest=manifest,
            )
        ),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


class _FakeCompiledRules:
    def __init__(self, matches, error: Exception | None = None) -> None:
        self._matches = matches
        self._error = error

    def match(self, path: str, timeout: int):
        if self._error is not None:
            raise self._error
        return self._matches


class _FakeYaraModule:
    def __init__(self, compiled: _FakeCompiledRules) -> None:
        self._compiled = compiled

    def compile(self, *, filepaths):
        assert filepaths
        return self._compiled


def _make_target_file(tmp_path: Path) -> FileTarget:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"sample")
    return FileTarget.from_path(sample)


def _make_rules_dir(tmp_path: Path) -> Path:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "sample.yar").write_text("rule sample { condition: true }", encoding="utf-8")
    return rules_dir


def test_yara_discover_reports_missing_rules_dir_with_shorter_wording(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(yara_module, "yara_lib", object())

    issue = YaraAdapter().discover(make_config(tmp_path, tmp_path / "missing-rules", tmp_path / "manifest.json"))

    assert issue is not None
    assert issue.code == "rules_missing"
    assert issue.message == "YARA rules directory was not found."


def test_yara_discover_reports_missing_manifest_with_shorter_wording(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(yara_module, "yara_lib", object())
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "rule.yar").write_text("rule test { condition: true }", encoding="utf-8")

    issue = YaraAdapter().discover(make_config(tmp_path, rules_dir, tmp_path / "missing-manifest.json"))

    assert issue is not None
    assert issue.code == "manifest_missing"
    assert issue.message == "YARA rules manifest was not found."


def test_yara_scan_builds_hit_result_summary(tmp_path: Path, monkeypatch) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    target = _make_target_file(tmp_path)
    report = build_report_shell(str(target.path), ScanProfile.BALANCED)
    fake_match = SimpleNamespace(
        rule="eicar_hit",
        namespace="default",
        tags=["malicious"],
        meta={"category": "malicious", "severity": "high", "confidence": "high"},
    )
    monkeypatch.setattr(yara_module, "yara_lib", _FakeYaraModule(_FakeCompiledRules([fake_match])))

    result = YaraAdapter().scan(target, report, make_config(tmp_path, rules_dir, None), timeout_seconds=30)

    assert result.raw_summary == {
        "match_count": 1,
        "match_rules": ["eicar_hit"],
        "result_summary": "1 rule match(es)",
    }


def test_yara_scan_builds_clean_result_summary(tmp_path: Path, monkeypatch) -> None:
    rules_dir = _make_rules_dir(tmp_path)
    target = _make_target_file(tmp_path)
    report = build_report_shell(str(target.path), ScanProfile.BALANCED)
    monkeypatch.setattr(yara_module, "yara_lib", _FakeYaraModule(_FakeCompiledRules([])))

    result = YaraAdapter().scan(target, report, make_config(tmp_path, rules_dir, None), timeout_seconds=30)

    assert result.raw_summary == {
        "match_count": 0,
        "match_rules": [],
        "result_summary": "no rules matched",
    }
