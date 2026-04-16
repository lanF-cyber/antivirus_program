from pathlib import Path
from types import SimpleNamespace

import scanbox.adapters.yara as yara_module
from scanbox.adapters.yara import YaraAdapter
from scanbox.config.models import AppConfig, AppSettings, EngineBinarySettings, EngineSettings, QuarantineSettings, TimeoutSettings


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
