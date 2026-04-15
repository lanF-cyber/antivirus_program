from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scanbox.config.models import AppConfig
from scanbox.core.enums import VerdictStatus
from scanbox.core.errors import QuarantineError
from scanbox.core.models import QuarantineAction, QuarantineMode, ScanReport
from scanbox.quarantine.audit import update_audit_state, utc_now_iso, write_audit_record
from scanbox.quarantine.models import (
    QuarantineIssue,
    QuarantineListResponse,
    QuarantineOperationResponse,
    QuarantineRecord,
    QuarantineRecordState,
)
from scanbox.quarantine.records import find_quarantine_record, list_quarantine_records
from scanbox.targets.file_target import FileTarget


class QuarantineService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def maybe_apply(
        self,
        report: ScanReport,
        target: FileTarget,
        requested_mode: QuarantineMode,
        dry_run: bool,
    ) -> QuarantineAction:
        destination = self._build_destination(target.path)
        action = QuarantineAction(
            requested_mode=requested_mode.value,
            dry_run=dry_run,
            performed=False,
            original_path=str(target.path),
            quarantine_path=str(destination),
        )

        if requested_mode == QuarantineMode.OFF:
            action.reason = "quarantine_disabled"
            return action

        if report.overall_status != VerdictStatus.KNOWN_MALICIOUS:
            action.reason = "verdict_not_eligible_for_quarantine"
            return action

        if requested_mode == QuarantineMode.ASK:
            action.reason = "user_confirmation_required"
            return action

        if dry_run:
            action.reason = "dry_run_requested"
            return action

        try:
            moved_at = datetime.now(timezone.utc)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target.path), str(destination))
            action.performed = True
            action.reason = "moved_to_quarantine"
            action.moved_at = moved_at
            audit_path = write_audit_record(
                report,
                target.path,
                destination,
                reason=report.overall_status.value,
                moved_at=moved_at.isoformat(),
            )
            action.audit_path = str(audit_path)
            return action
        except OSError as exc:
            raise QuarantineError(f"Failed to move file into quarantine: {exc}") from exc

    def list_records(self, state_filter: QuarantineRecordState | None = None) -> QuarantineListResponse:
        return list_quarantine_records(self._config.quarantine.directory, state_filter=state_filter)

    def restore(self, scan_id: str, output_path: Path | None = None) -> QuarantineOperationResponse:
        record, issues = find_quarantine_record(self._config.quarantine.directory, scan_id)
        response = QuarantineOperationResponse(
            operation="restore",
            scan_id=scan_id,
            ok=False,
            issues=list(issues),
        )
        if record is None:
            return response

        response.state_before = record.state
        response.audit_path = record.audit_path

        state_issue = self._validate_mutable_record(record)
        if state_issue is not None:
            response.issues.append(state_issue)
            return response

        target_path = self._resolve_restore_target(record, output_path)
        if target_path is None:
            response.issues.append(
                self._build_issue(
                    "restore_target_missing",
                    "No restore target path is available for this quarantine record.",
                    scan_id=scan_id,
                    audit_path=record.audit_path,
                )
            )
            return response

        response.target_path = str(target_path)
        if target_path.exists():
            response.issues.extend(
                [
                    self._build_issue(
                        "target_already_exists",
                        "Restore target already exists.",
                        scan_id=scan_id,
                        target_path=str(target_path),
                    ),
                    self._build_issue(
                        "restore_conflict",
                        "Restore was blocked because the target path already exists.",
                        scan_id=scan_id,
                        target_path=str(target_path),
                    ),
                ]
            )
            return response

        if not target_path.parent.exists():
            response.issues.append(
                self._build_issue(
                    "restore_parent_missing",
                    "Restore target parent directory does not exist.",
                    scan_id=scan_id,
                    target_path=str(target_path),
                    parent_path=str(target_path.parent),
                )
            )
            return response

        event_time = utc_now_iso()
        try:
            shutil.move(str(record.payload_path), str(target_path))
            update_audit_state(
                Path(record.audit_path),
                state=QuarantineRecordState.RESTORED.value,
                action="restore",
                result="success",
                details={
                    "quarantine_path": str(record.payload_path),
                    "target_path": str(target_path),
                },
                state_changed_at=event_time,
                restore_target_path=str(target_path),
            )
        except OSError as exc:
            raise QuarantineError(f"Failed to restore quarantine payload: {exc}") from exc

        response.ok = True
        response.state_after = QuarantineRecordState.RESTORED
        return response

    def delete(self, scan_id: str, confirmed: bool) -> QuarantineOperationResponse:
        response = QuarantineOperationResponse(
            operation="delete",
            scan_id=scan_id,
            ok=False,
        )
        if not confirmed:
            response.issues.append(
                self._build_issue(
                    "confirmation_required",
                    "Delete requires an explicit --yes confirmation.",
                    scan_id=scan_id,
                )
            )
            return response

        record, issues = find_quarantine_record(self._config.quarantine.directory, scan_id)
        response.issues.extend(issues)
        if record is None:
            return response

        response.state_before = record.state
        response.audit_path = record.audit_path

        state_issue = self._validate_mutable_record(record)
        if state_issue is not None:
            response.issues.append(state_issue)
            return response

        event_time = utc_now_iso()
        try:
            record.payload_path.unlink()
            update_audit_state(
                Path(record.audit_path),
                state=QuarantineRecordState.DELETED.value,
                action="delete",
                result="success",
                details={
                    "quarantine_path": str(record.payload_path),
                    "delete_reason": "user_confirmed",
                },
                state_changed_at=event_time,
                delete_reason="user_confirmed",
            )
        except OSError as exc:
            raise QuarantineError(f"Failed to delete quarantine payload: {exc}") from exc

        response.ok = True
        response.state_after = QuarantineRecordState.DELETED
        return response

    def _build_destination(self, file_path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = f"{timestamp}_{file_path.name}"
        return self._config.quarantine.directory / safe_name

    def _validate_mutable_record(self, record: QuarantineRecord) -> QuarantineIssue | None:
        if record.state != QuarantineRecordState.QUARANTINED:
            return self._build_issue(
                "state_not_quarantined",
                "Only records currently in quarantined state can be modified.",
                scan_id=record.scan_id,
                state=record.state.value,
                audit_path=record.audit_path,
            )
        if not record.payload_exists:
            return self._build_issue(
                "payload_missing",
                "Quarantine payload is missing and cannot be modified.",
                scan_id=record.scan_id,
                audit_path=record.audit_path,
                quarantine_path=record.quarantine_path,
            )
        return None

    def _resolve_restore_target(self, record: QuarantineRecord, output_path: Path | None) -> Path | None:
        if output_path is not None:
            return self._normalize_path(output_path)
        if not record.original_path:
            return None
        return self._normalize_path(Path(record.original_path))

    def _normalize_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return (self._config.root_dir / path).resolve()

    def _build_issue(self, code: str, message: str, **details: Any) -> QuarantineIssue:
        return QuarantineIssue(code=code, message=message, details=details)
