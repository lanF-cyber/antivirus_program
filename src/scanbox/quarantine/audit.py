from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scanbox.core.models import ScanReport


AUDIT_SCHEMA_VERSION = "1.0.0"
AUDIT_SUFFIX = ".audit.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_payload_path(audit_path: Path) -> Path:
    raw_path = str(audit_path)
    if not raw_path.endswith(AUDIT_SUFFIX):
        raise ValueError(f"Audit path does not end with {AUDIT_SUFFIX}: {audit_path}")
    return Path(raw_path[: -len(AUDIT_SUFFIX)])


def read_audit_payload(audit_path: Path) -> dict[str, Any]:
    return json.loads(audit_path.read_text(encoding="utf-8"))


def build_audit_event(action: str, result: str, details: dict[str, Any] | None = None, timestamp: str | None = None) -> dict[str, Any]:
    return {
        "timestamp": timestamp or utc_now_iso(),
        "action": action,
        "result": result,
        "details": details or {},
    }


def build_audit_record(
    report: ScanReport,
    original_path: Path,
    quarantine_path: Path,
    reason: str,
    moved_at: str | None = None,
) -> dict[str, Any]:
    event_time = moved_at or utc_now_iso()
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "scan_id": report.scan_id,
        "overall_status": report.overall_status.value,
        "original_path": str(original_path),
        "quarantine_path": str(quarantine_path),
        "moved_at": event_time,
        "reason": reason,
        "hashes": report.hashes.model_dump(),
        "state": "quarantined",
        "state_changed_at": event_time,
        "restore_target_path": None,
        "delete_reason": None,
        "events": [
            build_audit_event(
                action="quarantine_move",
                result="success",
                timestamp=event_time,
                details={
                    "reason": reason,
                    "overall_status": report.overall_status.value,
                },
            )
        ],
    }


def write_audit_record(
    report: ScanReport,
    original_path: Path,
    quarantine_path: Path,
    reason: str,
    moved_at: str | None = None,
) -> Path:
    audit_path = quarantine_path.with_suffix(quarantine_path.suffix + AUDIT_SUFFIX)
    audit_payload = build_audit_record(report, original_path, quarantine_path, reason, moved_at=moved_at)
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    return audit_path


def update_audit_state(
    audit_path: Path,
    *,
    state: str,
    action: str,
    result: str,
    details: dict[str, Any] | None = None,
    state_changed_at: str | None = None,
    restore_target_path: str | None = None,
    delete_reason: str | None = None,
) -> dict[str, Any]:
    event_time = state_changed_at or utc_now_iso()
    payload = read_audit_payload(audit_path)
    events = payload.get("events")
    if not isinstance(events, list):
        events = []

    payload.setdefault("audit_schema_version", AUDIT_SCHEMA_VERSION)
    payload["state"] = state
    payload["state_changed_at"] = event_time

    if restore_target_path is not None:
        payload["restore_target_path"] = restore_target_path
    elif "restore_target_path" not in payload:
        payload["restore_target_path"] = None

    if delete_reason is not None:
        payload["delete_reason"] = delete_reason
    elif "delete_reason" not in payload:
        payload["delete_reason"] = None

    events.append(build_audit_event(action=action, result=result, details=details, timestamp=event_time))
    payload["events"] = events
    audit_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
