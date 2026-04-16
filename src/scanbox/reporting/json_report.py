from __future__ import annotations

from copy import deepcopy
import json
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from scanbox.core.enums import ScanProfile, VerdictStatus
from scanbox.core import issue_text
from scanbox.core.models import (
    DirectoryScanAccounting,
    DirectoryScanReport,
    DirectoryScanSummary,
    DirectoryTargetInfo,
    EngineIssue,
    FileHashes,
    QuarantineAction,
    ScanReport,
    TargetInfo,
)


class ReportDetailLevel(str, Enum):
    DEFAULT = "default"
    FULL = "full"


_DIRECTORY_SUMMARY_DEFAULT_ORDER = (
    "known_malicious",
    "suspicious",
    "scan_error",
    "partial_scan",
    "engine_missing",
    "engine_unavailable",
    "clean_by_known_checks",
)

_DIRECTORY_ACCOUNTING_DEFAULT_ORDER = (
    "top_level_issue_count",
    "directory_access_error_count",
    "ignored_directory_count",
    "ignored_file_count",
)


def _stable_non_zero_first(
    payload: dict[str, Any],
    ordered_keys: tuple[str, ...],
) -> dict[str, Any]:
    reordered: dict[str, Any] = {}
    remaining_keys = [key for key in payload if key not in ordered_keys]

    for key in ordered_keys:
        if key in payload and payload[key] != 0:
            reordered[key] = payload[key]

    for key in ordered_keys:
        if key in payload and payload[key] == 0:
            reordered[key] = payload[key]

    for key in remaining_keys:
        reordered[key] = payload[key]

    return reordered


def _compact_capa_raw_summary(raw_summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("returncode", "rule_count", "result_summary", "skip_reason", "capa_skipped", "failure_summary"):
        if key in raw_summary:
            compact[key] = raw_summary[key]

    analysis_summary = raw_summary.get("analysis_summary")
    if isinstance(analysis_summary, dict) and analysis_summary:
        compact["analysis_summary"] = deepcopy(analysis_summary)

    return compact


def _compact_clamav_raw_summary(raw_summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("returncode", "match_count", "result_summary", "failure_summary"):
        if key in raw_summary:
            compact[key] = raw_summary[key]
    return compact


def _compact_yara_raw_summary(raw_summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("match_count", "result_summary", "failure_summary"):
        if key in raw_summary:
            compact[key] = raw_summary[key]
    return compact


def _compact_scan_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    engines = payload.get("engines")
    if not isinstance(engines, dict):
        return payload

    capa = engines.get("capa")
    if isinstance(capa, dict):
        raw_summary = capa.get("raw_summary")
        if isinstance(raw_summary, dict):
            capa["raw_summary"] = _compact_capa_raw_summary(raw_summary)

    clamav = engines.get("clamav")
    if isinstance(clamav, dict):
        raw_summary = clamav.get("raw_summary")
        if isinstance(raw_summary, dict):
            clamav["raw_summary"] = _compact_clamav_raw_summary(raw_summary)

    yara = engines.get("yara")
    if isinstance(yara, dict):
        raw_summary = yara.get("raw_summary")
        if isinstance(raw_summary, dict):
            yara["raw_summary"] = _compact_yara_raw_summary(raw_summary)

    return payload


def _compact_directory_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        payload["summary"] = _stable_non_zero_first(summary, _DIRECTORY_SUMMARY_DEFAULT_ORDER)

    accounting = payload.get("accounting")
    if isinstance(accounting, dict):
        payload["accounting"] = _stable_non_zero_first(accounting, _DIRECTORY_ACCOUNTING_DEFAULT_ORDER)

    results = payload.get("results")
    if not isinstance(results, list):
        return payload

    for entry in results:
        if not isinstance(entry, dict):
            continue
        report_payload = entry.get("report")
        if isinstance(report_payload, dict):
            entry["report"] = _compact_scan_report_payload(report_payload)
    return payload


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("mode") == "directory":
        return _compact_directory_report_payload(payload)
    return _compact_scan_report_payload(payload)


def serialize_report(report: ScanReport | DirectoryScanReport, detail_level: ReportDetailLevel = ReportDetailLevel.DEFAULT) -> str:
    payload = report.model_dump(mode="json")
    if detail_level == ReportDetailLevel.DEFAULT:
        payload = _compact_payload(payload)
    return json.dumps(payload, indent=2)


def emit_report(report: ScanReport | DirectoryScanReport, report_out: Path | None = None) -> None:
    stdout_payload = serialize_report(report, detail_level=ReportDetailLevel.DEFAULT)
    sys.stdout.write(stdout_payload)
    sys.stdout.write("\n")
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        full_payload = serialize_report(report, detail_level=ReportDetailLevel.FULL)
        report_out.write_text(full_payload + "\n", encoding="utf-8")


def build_error_report(
    original_path: str,
    error_code: str,
    error_message: str,
    scanbox_version: str,
) -> ScanReport:
    now = datetime.now(timezone.utc)
    return ScanReport(
        scanbox_version=scanbox_version,
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.SCAN_ERROR,
        started_at=now,
        ended_at=now,
        target=TargetInfo(
            original_path=original_path,
            normalized_path=original_path,
            size=0,
            detected_type="unknown",
        ),
        hashes=FileHashes(sha256="", md5=None, sha1=None),
        quarantine=QuarantineAction(requested_mode="ask"),
        issues=[
            EngineIssue(
                engine="scanbox",
                code=error_code,
                message=issue_text.scanbox_issue(error_code, clue=error_message),
            )
        ],
        summary={"error": True, "error_code": error_code},
    )


def build_directory_error_report(
    original_path: str,
    error_code: str,
    error_message: str,
    scanbox_version: str,
) -> DirectoryScanReport:
    now = datetime.now(timezone.utc)
    return DirectoryScanReport(
        scanbox_version=scanbox_version,
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.SCAN_ERROR,
        started_at=now,
        ended_at=now,
        target=DirectoryTargetInfo(
            original_path=original_path,
            normalized_path=original_path,
            recursive=True,
        ),
        issues=[
            EngineIssue(
                engine="scanbox",
                code=error_code,
                message=issue_text.scanbox_issue(error_code, clue=error_message),
            )
        ],
        summary=DirectoryScanSummary(),
        accounting=DirectoryScanAccounting(
            ignored_directory_count=0,
            top_level_issue_count=1,
            directory_access_error_count=0,
        ),
        target_count=0,
        scanned_count=0,
        error_count=1,
        results=[],
    )
