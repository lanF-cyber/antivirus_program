import json
from pathlib import Path

from scanbox.adapters.capa import CapaAdapter
from scanbox.config.models import AppConfig, AppSettings, EngineBinarySettings, EngineSettings, QuarantineSettings, TimeoutSettings
from scanbox.core.enums import ScanProfile
from scanbox.core.models import build_report_shell
from scanbox.core.subprocess_runner import CommandResult
from scanbox.targets.file_target import FileTarget


def test_capa_extracts_suspicious_keyword_rules() -> None:
    payload = json.loads(Path("tests/stubs/capa_result.json").read_text(encoding="utf-8"))
    detections = CapaAdapter()._extract_detections(payload)

    assert len(detections) == 1
    assert detections[0].rule_id == "create thread in remote process"
    assert detections[0].category == "suspicious"


def test_capa_builds_stable_analysis_summary() -> None:
    payload = {
        "meta": {
            "version": "9.3.1",
            "flavor": "static",
            "analysis": {
                "format": "pe",
                "arch": "amd64",
                "os": "windows",
                "extractor": "VivisectFeatureExtractor",
                "layout": {"too": "large"},
            },
        },
        "rules": {
            "rule-a": {"matches": 1},
            "rule-b": {"matches": 2},
        },
    }

    summary = CapaAdapter()._build_analysis_summary(payload)

    assert summary == {
        "matched_rule_count": 2,
        "capa_version": "9.3.1",
        "flavor": "static",
        "format": "pe",
        "arch": "amd64",
        "os": "windows",
        "extractor": "VivisectFeatureExtractor",
    }


def make_config(tmp_path: Path, executable: Path | None, rules_dir: Path | None, manifest: Path | None) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(
            capa=EngineBinarySettings(
                enabled=True,
                executable=executable,
                rules_dir=rules_dir,
                manifest=manifest,
            )
        ),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


class _FakeRunner:
    def __init__(self, result: CommandResult) -> None:
        self._result = result

    def run(self, command, timeout_seconds, cwd=None, env=None):
        return self._result


def _make_target_file(tmp_path: Path) -> FileTarget:
    sample = tmp_path / "sample.exe"
    sample.write_bytes(b"MZ")
    return FileTarget.from_path(sample)


def test_capa_discover_reports_placeholder_rules(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "README.md").write_text("placeholder", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"name":"official-capa-rules","version":"v9.3.0","source":"https://github.com/mandiant/capa-rules","pinned_ref":"v9.3.0","vendor_status":"placeholder","vendored_at":null,"rule_count":0}',
        encoding="utf-8",
    )

    issue = CapaAdapter().discover(make_config(tmp_path, executable, rules_dir, manifest))

    assert issue is not None
    assert issue.code == "rules_placeholder"
    assert issue.message == "capa rules are still placeholder content."


def test_capa_discover_reports_manifest_mismatch(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "rule.yml").write_text("rule: sample", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"name":"official-capa-rules","version":"v9.3.0","source":"https://github.com/mandiant/capa-rules","pinned_ref":"v9.3.0","vendor_status":"vendored","vendored_at":"2026-04-14T00:00:00Z","rule_count":2}',
        encoding="utf-8",
    )

    issue = CapaAdapter().discover(make_config(tmp_path, executable, rules_dir, manifest))

    assert issue is not None
    assert issue.code == "manifest_mismatch"


def test_capa_discover_reports_missing_manifest(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    issue = CapaAdapter().discover(make_config(tmp_path, executable, rules_dir, tmp_path / "missing-manifest.json"))

    assert issue is not None
    assert issue.code == "manifest_missing"
    assert issue.message == "capa rules manifest was not found."


def test_capa_runtime_environment_uses_repo_local_temp(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"name":"official-capa-rules","version":"v9.3.0","source":"https://github.com/mandiant/capa-rules","pinned_ref":"v9.3.0","vendor_status":"vendored","vendored_at":"2026-04-15T01:11:12Z","rule_count":0}',
        encoding="utf-8",
    )
    adapter = CapaAdapter()

    environment, runtime_tmp = adapter._build_runtime_environment(make_config(tmp_path, executable, rules_dir, manifest))

    assert runtime_tmp == tmp_path / ".local-tools" / "capa" / "runtime-tmp"
    assert runtime_tmp.is_dir()
    assert environment["TMP"] == str(runtime_tmp)
    assert environment["TEMP"] == str(runtime_tmp)


def test_capa_scan_builds_fixed_result_summary_without_expanding_analysis_summary(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    target = _make_target_file(tmp_path)
    payload = {
        "meta": {
            "version": "9.3.1",
            "flavor": "static",
            "analysis": {
                "format": "pe",
                "arch": "amd64",
                "os": "windows",
                "extractor": "VivisectFeatureExtractor",
                "layout": {"ignored": True},
            },
        },
        "rules": {
            "rule-a": {"matches": 1},
            "rule-b": {"matches": 2},
        },
    }
    runner = _FakeRunner(
        CommandResult(
            command=["capa.exe", "--json", str(target.path)],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
            duration_ms=12,
        )
    )
    report = build_report_shell(str(target.path), ScanProfile.BALANCED)

    result = CapaAdapter(runner=runner).scan(target, report, make_config(tmp_path, executable, rules_dir, None), 30)

    assert result.raw_summary["result_summary"] == "2 capability rule(s) matched"
    assert result.raw_summary["analysis_summary"] == {
        "matched_rule_count": 2,
        "capa_version": "9.3.1",
        "flavor": "static",
        "format": "pe",
        "arch": "amd64",
        "os": "windows",
        "extractor": "VivisectFeatureExtractor",
    }


def test_capa_scan_builds_short_failure_summary_for_runtime_errors(tmp_path: Path) -> None:
    executable = tmp_path / "capa.exe"
    executable.write_text("stub", encoding="utf-8")
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    target = _make_target_file(tmp_path)
    runner = _FakeRunner(
        CommandResult(
            command=["capa.exe", "--json", str(target.path)],
            returncode=10,
            stdout="runtime failure details\nwith extra context",
            stderr="fatal capa error\nfull stack trace follows",
            duration_ms=9,
        )
    )
    report = build_report_shell(str(target.path), ScanProfile.BALANCED)

    result = CapaAdapter(runner=runner).scan(target, report, make_config(tmp_path, executable, rules_dir, None), 30)

    assert result.raw_summary["result_summary"] == "runtime error"
    assert result.raw_summary["failure_summary"] == "fatal capa error"
