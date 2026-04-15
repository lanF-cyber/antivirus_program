from __future__ import annotations

from copy import deepcopy
import json
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from scanbox.core.enums import ScanProfile, VerdictStatus
from scanbox.core.models import EngineIssue, FileHashes, QuarantineAction, ScanReport, TargetInfo


class ReportDetailLevel(str, Enum):
    DEFAULT = "default"
    FULL = "full"


def _compact_capa_raw_summary(raw_summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("returncode", "rule_count", "runtime_temp_dir", "skip_reason", "capa_skipped"):
        if key in raw_summary:
            compact[key] = raw_summary[key]

    analysis_summary = raw_summary.get("analysis_summary")
    if isinstance(analysis_summary, dict) and analysis_summary:
        compact["analysis_summary"] = deepcopy(analysis_summary)

    return compact


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    engines = payload.get("engines")
    if not isinstance(engines, dict):
        return payload

    capa = engines.get("capa")
    if isinstance(capa, dict):
        raw_summary = capa.get("raw_summary")
        if isinstance(raw_summary, dict):
            capa["raw_summary"] = _compact_capa_raw_summary(raw_summary)

    return payload


def serialize_report(report: ScanReport, detail_level: ReportDetailLevel = ReportDetailLevel.DEFAULT) -> str:
    payload = report.model_dump(mode="json")
    if detail_level == ReportDetailLevel.DEFAULT:
        payload = _compact_payload(payload)
    return json.dumps(payload, indent=2)


def emit_report(report: ScanReport, report_out: Path | None = None) -> None:
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
        issues=[EngineIssue(engine="scanbox", code=error_code, message=error_message)],
        summary={"error": True, "error_code": error_code},
    )
