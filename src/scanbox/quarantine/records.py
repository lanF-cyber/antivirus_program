from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scanbox.quarantine.audit import AUDIT_SUFFIX, derive_payload_path, read_audit_payload
from scanbox.quarantine.models import (
    QuarantineEvent,
    QuarantineHashSummary,
    QuarantineIssue,
    QuarantineListResponse,
    QuarantineListSummary,
    QuarantineRecord,
    QuarantineRecordState,
)


def _build_issue(code: str, message: str, **details: Any) -> QuarantineIssue:
    return QuarantineIssue(code=code, message=message, details=details)


def _coerce_event(raw_event: Any) -> QuarantineEvent | None:
    if not isinstance(raw_event, dict):
        return None
    timestamp = raw_event.get("timestamp")
    action = raw_event.get("action")
    result = raw_event.get("result")
    if not isinstance(timestamp, str) or not isinstance(action, str) or not isinstance(result, str):
        return None
    details = raw_event.get("details")
    if not isinstance(details, dict):
        details = {}
    return QuarantineEvent(timestamp=timestamp, action=action, result=result, details=details)


def load_quarantine_record(audit_path: Path) -> QuarantineRecord:
    raw_payload = read_audit_payload(audit_path)
    if not isinstance(raw_payload, dict):
        raise ValueError(f"Audit payload is not an object: {audit_path}")

    scan_id = raw_payload.get("scan_id")
    if not isinstance(scan_id, str) or not scan_id:
        raise ValueError(f"Audit payload is missing scan_id: {audit_path}")

    payload_path = derive_payload_path(audit_path)
    payload_exists = payload_path.exists()
    issues: list[QuarantineIssue] = []

    raw_state = raw_payload.get("state")
    if isinstance(raw_state, str):
        try:
            state = QuarantineRecordState(raw_state)
        except ValueError:
            state = QuarantineRecordState.UNKNOWN
            issues.append(
                _build_issue(
                    "invalid_state_value",
                    "Audit record has an unsupported state value.",
                    scan_id=scan_id,
                    audit_path=str(audit_path),
                    raw_state=raw_state,
                )
            )
    elif payload_exists:
        state = QuarantineRecordState.QUARANTINED
    else:
        state = QuarantineRecordState.UNKNOWN
        issues.append(
            _build_issue(
                "legacy_state_missing",
                "Legacy audit record has no explicit state and payload is no longer present.",
                scan_id=scan_id,
                payload_exists=payload_exists,
                audit_path=str(audit_path),
            )
        )

    if state == QuarantineRecordState.QUARANTINED and not payload_exists:
        issues.append(
            _build_issue(
                "payload_missing",
                "Quarantine payload is missing for a record that is still marked quarantined.",
                scan_id=scan_id,
                payload_exists=payload_exists,
                audit_path=str(audit_path),
                quarantine_path=str(payload_path),
            )
        )
    if state in {QuarantineRecordState.RESTORED, QuarantineRecordState.DELETED} and payload_exists:
        issues.append(
            _build_issue(
                "payload_still_present",
                "Quarantine payload is still present even though the record is not quarantined anymore.",
                scan_id=scan_id,
                payload_exists=payload_exists,
                audit_path=str(audit_path),
                quarantine_path=str(payload_path),
                state=state.value,
            )
        )

    events: list[QuarantineEvent] = []
    raw_events = raw_payload.get("events")
    if isinstance(raw_events, list):
        for raw_event in raw_events:
            event = _coerce_event(raw_event)
            if event is not None:
                events.append(event)

    stored_quarantine_path = raw_payload.get("quarantine_path")
    if isinstance(stored_quarantine_path, str) and stored_quarantine_path and stored_quarantine_path != str(payload_path):
        issues.append(
            _build_issue(
                "quarantine_path_mismatch",
                "Stored quarantine_path does not match the audit sidecar location.",
                scan_id=scan_id,
                audit_path=str(audit_path),
                stored_quarantine_path=stored_quarantine_path,
                derived_quarantine_path=str(payload_path),
            )
        )

    hashes = raw_payload.get("hashes")
    sha256 = None
    if isinstance(hashes, dict):
        raw_sha256 = hashes.get("sha256")
        if isinstance(raw_sha256, str) and raw_sha256:
            sha256 = raw_sha256

    return QuarantineRecord(
        scan_id=scan_id,
        state=state,
        original_path=raw_payload.get("original_path") if isinstance(raw_payload.get("original_path"), str) else None,
        quarantine_path=str(payload_path),
        hashes=QuarantineHashSummary(sha256=sha256),
        moved_at=raw_payload.get("moved_at") if isinstance(raw_payload.get("moved_at"), str) else None,
        audit_path=str(audit_path),
        payload_exists=payload_exists,
        payload_path=payload_path,
        reason=raw_payload.get("reason") if isinstance(raw_payload.get("reason"), str) else None,
        state_changed_at=raw_payload.get("state_changed_at")
        if isinstance(raw_payload.get("state_changed_at"), str)
        else None,
        restore_target_path=raw_payload.get("restore_target_path")
        if isinstance(raw_payload.get("restore_target_path"), str)
        else None,
        delete_reason=raw_payload.get("delete_reason") if isinstance(raw_payload.get("delete_reason"), str) else None,
        events=events,
        issues=issues,
    )


def list_quarantine_records(
    quarantine_dir: Path,
    state_filter: QuarantineRecordState | None = None,
) -> QuarantineListResponse:
    if not quarantine_dir.exists():
        return QuarantineListResponse()

    response = QuarantineListResponse()
    audit_paths = sorted(quarantine_dir.rglob(f"*{AUDIT_SUFFIX}"))
    summaries = []

    for audit_path in audit_paths:
        try:
            record = load_quarantine_record(audit_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            response.issues.append(
                _build_issue(
                    "audit_load_failed",
                    "Failed to load quarantine audit record.",
                    audit_path=str(audit_path),
                    error=str(exc),
                )
            )
            continue

        if state_filter is not None and record.state != state_filter:
            continue

        response.issues.extend(record.issues)
        summaries.append(record.to_summary())

    response.records = summaries
    response.summary = QuarantineListSummary(
        total=len(summaries),
        quarantined=sum(1 for item in summaries if item.state == QuarantineRecordState.QUARANTINED),
        restored=sum(1 for item in summaries if item.state == QuarantineRecordState.RESTORED),
        deleted=sum(1 for item in summaries if item.state == QuarantineRecordState.DELETED),
        unknown=sum(1 for item in summaries if item.state == QuarantineRecordState.UNKNOWN),
    )
    return response


def find_quarantine_record(
    quarantine_dir: Path,
    scan_id: str,
) -> tuple[QuarantineRecord | None, list[QuarantineIssue]]:
    if not quarantine_dir.exists():
        return None, [
            _build_issue(
                "scan_id_not_found",
                "No quarantine record matched the requested scan_id.",
                scan_id=scan_id,
                quarantine_dir=str(quarantine_dir),
            )
        ]

    matches: list[QuarantineRecord] = []
    issues: list[QuarantineIssue] = []
    for audit_path in sorted(quarantine_dir.rglob(f"*{AUDIT_SUFFIX}")):
        try:
            record = load_quarantine_record(audit_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(
                _build_issue(
                    "audit_load_failed",
                    "Failed to load quarantine audit record while resolving scan_id.",
                    scan_id=scan_id,
                    audit_path=str(audit_path),
                    error=str(exc),
                )
            )
            continue
        if record.scan_id == scan_id:
            matches.append(record)

    if not matches:
        issues.append(
            _build_issue(
                "scan_id_not_found",
                "No quarantine record matched the requested scan_id.",
                scan_id=scan_id,
                quarantine_dir=str(quarantine_dir),
            )
        )
        return None, issues

    if len(matches) > 1:
        issues.append(
            _build_issue(
                "duplicate_scan_id",
                "Multiple quarantine records matched the requested scan_id.",
                scan_id=scan_id,
                match_count=len(matches),
                quarantine_dir=str(quarantine_dir),
            )
        )
        return None, issues

    record = matches[0]
    return record, issues + record.issues
