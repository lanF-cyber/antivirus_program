from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from scanbox.config.models import AppConfig
from scanbox.core.enums import VerdictStatus
from scanbox.core.errors import QuarantineError
from scanbox.core.models import QuarantineAction, QuarantineMode, ScanReport
from scanbox.quarantine.audit import write_audit_record
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
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target.path), str(destination))
            action.performed = True
            action.reason = "moved_to_quarantine"
            action.moved_at = datetime.now(timezone.utc)
            audit_path = write_audit_record(report, target.path, destination, reason=report.overall_status.value)
            action.audit_path = str(audit_path)
            return action
        except OSError as exc:
            raise QuarantineError(f"Failed to move file into quarantine: {exc}") from exc

    def _build_destination(self, file_path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = f"{timestamp}_{file_path.name}"
        return self._config.quarantine.directory / safe_name
