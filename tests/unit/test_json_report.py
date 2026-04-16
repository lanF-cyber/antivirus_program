import json
from pathlib import Path

from scanbox.core.enums import EngineState, ScanProfile, VerdictStatus
from scanbox.core.models import (
    DirectoryScanAccounting,
    DirectoryScanEntry,
    DirectoryScanReport,
    DirectoryScanSummary,
    DirectoryTargetInfo,
    EngineScanResult,
    QuarantineAction,
    ScanReport,
    TargetInfo,
)
from scanbox.reporting.json_report import ReportDetailLevel, build_directory_error_report, emit_report, serialize_report


def make_report() -> ScanReport:
    report = ScanReport(
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.CLEAN_BY_KNOWN_CHECKS,
        target=TargetInfo(
            original_path="sample.exe",
            normalized_path=str(Path("sample.exe").resolve()),
            size=123,
            detected_type="pe",
            extension=".exe",
            mime_guess="application/vnd.microsoft.portable-executable",
        ),
        quarantine=QuarantineAction(requested_mode="ask"),
    )
    report.engines = {
        "capa": EngineScanResult(
            engine="capa",
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            raw_summary={
                "command": ["capa.exe", "--json", "sample.exe"],
                "returncode": 0,
                "runtime_temp_dir": "C:\\temp\\scanbox-capa",
                "rule_count": 21,
                "analysis_summary": {
                    "capa_version": "9.3.1",
                    "flavor": "static",
                    "format": "pe",
                    "arch": "amd64",
                    "os": "windows",
                    "extractor": "VivisectFeatureExtractor",
                    "matched_rule_count": 21,
                },
                "meta": {
                    "version": "9.3.1",
                    "analysis": {
                        "layout": {"functions": [1, 2, 3]},
                    },
                },
            },
        )
    }
    report.summary = {"status": report.overall_status.value}
    return report


def make_directory_report() -> DirectoryScanReport:
    child_report = make_report()
    return DirectoryScanReport(
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.CLEAN_BY_KNOWN_CHECKS,
        target=DirectoryTargetInfo(
            original_path="samples",
            normalized_path=str(Path("samples").resolve()),
            recursive=True,
        ),
        target_count=1,
        scanned_count=1,
        error_count=0,
        summary=DirectoryScanSummary(clean_by_known_checks=1),
        accounting=DirectoryScanAccounting(
            ignored_directory_count=3,
            ignored_file_count=0,
            top_level_issue_count=0,
            directory_access_error_count=0,
        ),
        results=[
            DirectoryScanEntry(
                relative_path="sample.exe",
                report=child_report,
            )
        ],
    )


def test_serialize_report_default_compacts_capa_raw_summary() -> None:
    report = make_report()

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    raw_summary = payload["engines"]["capa"]["raw_summary"]

    assert raw_summary == {
        "returncode": 0,
        "rule_count": 21,
        "runtime_temp_dir": "C:\\temp\\scanbox-capa",
        "analysis_summary": {
            "capa_version": "9.3.1",
            "flavor": "static",
            "format": "pe",
            "arch": "amd64",
            "os": "windows",
            "extractor": "VivisectFeatureExtractor",
            "matched_rule_count": 21,
        },
    }


def test_serialize_report_full_keeps_capa_meta() -> None:
    report = make_report()

    payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))
    raw_summary = payload["engines"]["capa"]["raw_summary"]

    assert "meta" in raw_summary
    assert "command" in raw_summary
    assert raw_summary["meta"]["analysis"]["layout"] == {"functions": [1, 2, 3]}


def test_emit_report_uses_default_for_stdout_and_full_for_report_out(capsys, tmp_path: Path) -> None:
    report = make_report()
    output_path = tmp_path / "report.json"

    emit_report(report, report_out=output_path)

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert "meta" not in stdout_payload["engines"]["capa"]["raw_summary"]
    assert "meta" in file_payload["engines"]["capa"]["raw_summary"]
    assert stdout_payload["overall_status"] == file_payload["overall_status"]


def test_serialize_directory_report_default_compacts_nested_capa_raw_summary() -> None:
    report = make_directory_report()

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    raw_summary = payload["results"][0]["report"]["engines"]["capa"]["raw_summary"]

    assert raw_summary == {
        "returncode": 0,
        "rule_count": 21,
        "runtime_temp_dir": "C:\\temp\\scanbox-capa",
        "analysis_summary": {
            "capa_version": "9.3.1",
            "flavor": "static",
            "format": "pe",
            "arch": "amd64",
            "os": "windows",
            "extractor": "VivisectFeatureExtractor",
            "matched_rule_count": 21,
        },
    }
    assert payload["accounting"] == {
        "ignored_directory_count": 3,
        "ignored_file_count": 0,
        "top_level_issue_count": 0,
        "directory_access_error_count": 0,
    }


def test_emit_directory_report_uses_default_for_stdout_and_full_for_report_out(capsys, tmp_path: Path) -> None:
    report = make_directory_report()
    output_path = tmp_path / "directory-report.json"

    emit_report(report, report_out=output_path)

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert "meta" not in stdout_payload["results"][0]["report"]["engines"]["capa"]["raw_summary"]
    assert "meta" in file_payload["results"][0]["report"]["engines"]["capa"]["raw_summary"]
    assert stdout_payload["overall_status"] == file_payload["overall_status"]
    assert stdout_payload["accounting"] == file_payload["accounting"]


def test_build_directory_error_report_keeps_error_count_semantics_and_accounting() -> None:
    report = build_directory_error_report(
        original_path="samples",
        error_code="input_error",
        error_message="directory mode rejected the requested quarantine action",
        scanbox_version="test-version",
    )

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))

    assert payload["error_count"] == 1
    assert payload["accounting"] == {
        "ignored_directory_count": 0,
        "ignored_file_count": 0,
        "top_level_issue_count": 1,
        "directory_access_error_count": 0,
    }


def test_directory_report_serialization_does_not_expose_filter_configuration_fields() -> None:
    report = make_directory_report()

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    for payload in (default_payload, full_payload):
        assert "directory_scan" not in payload
        assert "patterns_enabled" not in payload
        assert "active_filters" not in payload
        assert set(payload["accounting"].keys()) == {
            "ignored_directory_count",
            "ignored_file_count",
            "top_level_issue_count",
            "directory_access_error_count",
        }
