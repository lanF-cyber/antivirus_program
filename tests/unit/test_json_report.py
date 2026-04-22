import json
from pathlib import Path

from scanbox.core.enums import EngineState, ScanProfile, VerdictStatus
from scanbox.core.models import (
    ArchiveExpansionReport,
    ArchiveMemberResult,
    Detection,
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
                "result_summary": "21 capability rule(s) matched",
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


def make_yara_report(raw_summary: dict[str, object], detections: list[dict[str, object]] | None = None) -> ScanReport:
    report = ScanReport(
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.SUSPICIOUS,
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
        "yara": EngineScanResult(
            engine="yara",
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            detections=[
                Detection(
                    source="yara",
                    rule_id=str(detection["rule_id"]),
                    title=str(detection.get("title", detection["rule_id"])),
                    severity=str(detection.get("severity", "medium")),
                    confidence=str(detection.get("confidence", "medium")),
                    category=str(detection.get("category", "suspicious")),
                )
                for detection in (detections or [])
            ],
            raw_summary=raw_summary,
        )
    }
    report.summary = {"status": report.overall_status.value}
    return report


def make_clamav_report(raw_summary: dict[str, object]) -> ScanReport:
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
        "clamav": EngineScanResult(
            engine="clamav",
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            raw_summary=raw_summary,
        )
    }
    report.summary = {"status": report.overall_status.value}
    return report


def make_directory_report(child_report: ScanReport | None = None) -> DirectoryScanReport:
    child_report = child_report or make_report()
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


def make_directory_report_with_mixed_counts() -> DirectoryScanReport:
    return DirectoryScanReport(
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.SUSPICIOUS,
        target=DirectoryTargetInfo(
            original_path="samples",
            normalized_path=str(Path("samples").resolve()),
            recursive=True,
        ),
        target_count=4,
        scanned_count=4,
        error_count=2,
        summary=DirectoryScanSummary(
            suspicious=2,
            scan_error=1,
            clean_by_known_checks=1,
        ),
        accounting=DirectoryScanAccounting(
            ignored_directory_count=3,
            ignored_file_count=0,
            top_level_issue_count=2,
            directory_access_error_count=1,
        ),
        results=[],
    )


def make_archive_report() -> ScanReport:
    parent_report = make_report()
    child_report = make_report()
    child_report.target = TargetInfo(
        original_path="sample.zip::nested/sample.exe",
        normalized_path=str(Path("nested-sample.exe").resolve()),
        size=321,
        detected_type="pe",
        extension=".exe",
        mime_guess="application/vnd.microsoft.portable-executable",
        archive_path=str(Path("sample.zip").resolve()),
        archive_member_path="nested/sample.exe",
        archive_depth=1,
    )
    parent_report.archive_expansion = ArchiveExpansionReport(
        expansion_depth=0,
        max_expansion_depth=1,
        member_count=1,
        scanned_member_count=1,
        total_extracted_bytes=321,
        results=[
            ArchiveMemberResult(
                member_path="nested/sample.exe",
                report=child_report,
            )
        ],
    )
    parent_report.summary = {
        "engine_count": 1,
        "detections": 0,
        "known_malicious_hits": 0,
        "suspicious_hits": 0,
        "archive_member_count": 1,
        "archive_scanned_member_count": 1,
        "archive_total_extracted_bytes": 321,
        "status": parent_report.overall_status.value,
    }
    return parent_report


def test_serialize_report_default_compacts_capa_raw_summary() -> None:
    report = make_report()

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    raw_summary = payload["engines"]["capa"]["raw_summary"]

    assert raw_summary == {
        "returncode": 0,
        "rule_count": 21,
        "result_summary": "21 capability rule(s) matched",
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


def test_serialize_report_default_compacts_yara_raw_summary_and_keeps_detections() -> None:
    report = make_yara_report(
        {
            "match_count": 1,
            "match_rules": ["yara-eicar"],
            "result_summary": "1 rule match(es)",
        },
        detections=[
            {
                "rule_id": "yara-eicar",
                "title": "yara-eicar",
                "severity": "high",
                "confidence": "high",
                "category": "malicious",
            }
        ],
    )

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    assert default_payload["engines"]["yara"]["raw_summary"] == {
        "match_count": 1,
        "result_summary": "1 rule match(es)",
    }
    assert default_payload["engines"]["yara"]["detections"][0]["rule_id"] == "yara-eicar"
    assert full_payload["engines"]["yara"]["raw_summary"]["match_rules"] == ["yara-eicar"]


def test_serialize_report_full_keeps_capa_meta() -> None:
    report = make_report()

    payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))
    raw_summary = payload["engines"]["capa"]["raw_summary"]

    assert "meta" in raw_summary
    assert "command" in raw_summary
    assert raw_summary["meta"]["analysis"]["layout"] == {"functions": [1, 2, 3]}


def test_serialize_report_default_compacts_clamav_raw_summary() -> None:
    report = make_clamav_report(
        {
            "command": ["clamscan.exe", "--stdout", "sample.exe"],
            "returncode": 1,
            "match_count": 2,
            "result_summary": "2 signature hit(s)",
            "stdout": "sample.exe: Eicar-Test-Signature FOUND",
            "stderr": "",
        }
    )

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    raw_summary = payload["engines"]["clamav"]["raw_summary"]

    assert raw_summary == {
        "returncode": 1,
        "match_count": 2,
        "result_summary": "2 signature hit(s)",
    }


def test_serialize_report_default_keeps_clamav_failure_summary() -> None:
    report = make_clamav_report(
        {
            "command": ["clamscan.exe", "--stdout", "sample.exe"],
            "returncode": 2,
            "match_count": 0,
            "result_summary": "runtime error",
            "failure_summary": "LibClamAV Error: database load failed",
            "stdout": "",
            "stderr": "LibClamAV Error: database load failed",
        }
    )

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    assert default_payload["engines"]["clamav"]["raw_summary"] == {
        "returncode": 2,
        "match_count": 0,
        "result_summary": "runtime error",
        "failure_summary": "LibClamAV Error: database load failed",
    }
    assert full_payload["engines"]["clamav"]["raw_summary"]["command"] == ["clamscan.exe", "--stdout", "sample.exe"]
    assert full_payload["engines"]["clamav"]["raw_summary"]["stderr"] == "LibClamAV Error: database load failed"


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
        "result_summary": "21 capability rule(s) matched",
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


def test_serialize_directory_report_default_reorders_summary_with_non_zero_first() -> None:
    report = make_directory_report_with_mixed_counts()

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))

    assert list(payload["summary"].keys()) == [
        "suspicious",
        "scan_error",
        "clean_by_known_checks",
        "known_malicious",
        "partial_scan",
        "engine_missing",
        "engine_unavailable",
    ]
    assert payload["summary"] == {
        "suspicious": 2,
        "scan_error": 1,
        "clean_by_known_checks": 1,
        "known_malicious": 0,
        "partial_scan": 0,
        "engine_missing": 0,
        "engine_unavailable": 0,
    }


def test_serialize_directory_report_default_reorders_accounting_with_non_zero_first() -> None:
    report = make_directory_report_with_mixed_counts()

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))

    assert list(payload["accounting"].keys()) == [
        "top_level_issue_count",
        "directory_access_error_count",
        "ignored_directory_count",
        "ignored_file_count",
    ]
    assert payload["accounting"] == {
        "top_level_issue_count": 2,
        "directory_access_error_count": 1,
        "ignored_directory_count": 3,
        "ignored_file_count": 0,
    }


def test_serialize_directory_report_full_keeps_original_summary_and_accounting_order() -> None:
    report = make_directory_report_with_mixed_counts()

    payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    assert list(payload["summary"].keys()) == [
        "known_malicious",
        "suspicious",
        "clean_by_known_checks",
        "partial_scan",
        "scan_error",
        "engine_missing",
        "engine_unavailable",
    ]
    assert list(payload["accounting"].keys()) == [
        "ignored_directory_count",
        "ignored_file_count",
        "top_level_issue_count",
        "directory_access_error_count",
    ]


def test_serialize_directory_report_default_uses_single_file_clamav_compaction() -> None:
    report = make_directory_report(
        make_clamav_report(
            {
                "command": ["clamscan.exe", "--stdout", "sample.exe"],
                "returncode": None,
                "match_count": 0,
                "result_summary": "execution failed",
                "failure_summary": "Failed to execute command: clamscan.exe",
                "stdout": "",
                "stderr": "",
            }
        )
    )

    payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    raw_summary = payload["results"][0]["report"]["engines"]["clamav"]["raw_summary"]

    assert raw_summary == {
        "returncode": None,
        "match_count": 0,
        "result_summary": "execution failed",
        "failure_summary": "Failed to execute command: clamscan.exe",
    }


def test_serialize_report_default_compacts_capa_failure_summary_without_runtime_temp_dir() -> None:
    report = make_report()
    report.engines["capa"] = EngineScanResult(
        engine="capa",
        enabled=True,
        applicable=True,
        state=EngineState.UNAVAILABLE,
        raw_summary={
            "command": ["capa.exe", "--json", "sample.exe"],
            "returncode": 10,
            "runtime_temp_dir": "C:\\temp\\scanbox-capa",
            "result_summary": "runtime error",
            "failure_summary": "fatal capa error",
            "stdout": "fatal capa error\nwith more text",
            "stderr": "fatal capa error\nwith stack",
        },
    )

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    assert default_payload["engines"]["capa"]["raw_summary"] == {
        "returncode": 10,
        "result_summary": "runtime error",
        "failure_summary": "fatal capa error",
    }
    assert full_payload["engines"]["capa"]["raw_summary"]["runtime_temp_dir"] == "C:\\temp\\scanbox-capa"
    assert full_payload["engines"]["capa"]["raw_summary"]["stderr"] == "fatal capa error\nwith stack"


def test_serialize_report_default_keeps_capa_skip_summary_without_runtime_temp_dir() -> None:
    report = make_report()
    report.engines["capa"] = EngineScanResult(
        engine="capa",
        enabled=True,
        applicable=False,
        state=EngineState.SKIPPED_NOT_APPLICABLE,
        raw_summary={
            "capa_skipped": True,
            "skip_reason": "script_file_not_supported_in_v1_policy",
            "result_summary": "scan skipped",
            "runtime_temp_dir": "C:\\temp\\scanbox-capa",
        },
    )

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    assert default_payload["engines"]["capa"]["raw_summary"] == {
        "result_summary": "scan skipped",
        "skip_reason": "script_file_not_supported_in_v1_policy",
        "capa_skipped": True,
    }
    assert full_payload["engines"]["capa"]["raw_summary"]["runtime_temp_dir"] == "C:\\temp\\scanbox-capa"


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


def test_serialize_report_default_compacts_nested_archive_member_raw_summary() -> None:
    report = make_archive_report()
    report.quarantine.archive_triggered = True
    report.quarantine.archive_member_paths = ["nested/sample.exe"]
    report.quarantine.reason = "archive_member_known_malicious"

    default_payload = json.loads(serialize_report(report, ReportDetailLevel.DEFAULT))
    full_payload = json.loads(serialize_report(report, ReportDetailLevel.FULL))

    nested_default = default_payload["archive_expansion"]["results"][0]["report"]["engines"]["capa"]["raw_summary"]
    nested_full = full_payload["archive_expansion"]["results"][0]["report"]["engines"]["capa"]["raw_summary"]

    assert nested_default == {
        "returncode": 0,
        "rule_count": 21,
        "result_summary": "21 capability rule(s) matched",
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
    assert "meta" in nested_full
    assert default_payload["archive_expansion"]["results"][0]["report"]["target"]["archive_member_path"] == "nested/sample.exe"
    assert default_payload["quarantine"]["archive_triggered"] is True
    assert default_payload["quarantine"]["archive_member_paths"] == ["nested/sample.exe"]
    assert default_payload["quarantine"]["reason"] == "archive_member_known_malicious"


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
