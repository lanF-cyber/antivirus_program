from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scanbox.core.models import ScanReport


def build_audit_record(report: ScanReport, original_path: Path, quarantine_path: Path, reason: str) -> dict:
    return {
        "scan_id": report.scan_id,
        "overall_status": report.overall_status.value,
        "original_path": str(original_path),
        "quarantine_path": str(quarantine_path),
        "moved_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "hashes": report.hashes.model_dump(),
    }


def write_audit_record(report: ScanReport, original_path: Path, quarantine_path: Path, reason: str) -> Path:
    audit_path = quarantine_path.with_suffix(quarantine_path.suffix + ".audit.json")
    audit_payload = build_audit_record(report, original_path, quarantine_path, reason)
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    return audit_path
