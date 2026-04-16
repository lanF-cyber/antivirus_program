from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from scanbox.adapters.base import ScannerAdapter
from scanbox.adapters.capa import CapaAdapter
from scanbox.adapters.clamav import ClamAvAdapter
from scanbox.adapters.yara import YaraAdapter
from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState, VerdictStatus
from scanbox.core.errors import InputError, ScanBoxError
from scanbox.core.filetypes import detect_file_type
from scanbox.core.hashing import HashingService
from scanbox.core.models import (
    DISCLAIMER_TEXT,
    DirectoryScanAccounting,
    DirectoryScanEntry,
    DirectoryScanReport,
    DirectoryScanSummary,
    DirectoryTargetInfo,
    EngineIssue,
    QuarantineMode,
    ScanReport,
    TargetInfo,
    build_directory_report_shell,
    build_report_shell,
)
from scanbox.pipeline.directory_scan_policy import DirectoryScanPolicy
from scanbox.core.timeouts import TimeoutPolicy
from scanbox.pipeline.preflight import apply_preflight
from scanbox.pipeline.verdicts import VerdictResolver
from scanbox.quarantine.service import QuarantineService
from scanbox.targets.directory_target import DirectoryTarget
from scanbox.targets.file_target import FileTarget


class ScanOrchestrator:
    _VERDICT_PRIORITY = (
        "scan_error",
        "known_malicious",
        "suspicious",
        "engine_missing",
        "engine_unavailable",
        "partial_scan",
        "clean_by_known_checks",
    )

    def __init__(
        self,
        config: AppConfig,
        adapters: list[ScannerAdapter] | None = None,
        directory_policy: DirectoryScanPolicy | None = None,
    ) -> None:
        self.config = config
        self.adapters = adapters or [ClamAvAdapter(), YaraAdapter(), CapaAdapter()]
        self.directory_policy = directory_policy or DirectoryScanPolicy.from_settings(config.directory_scan)
        self.hashing = HashingService()
        self.timeouts = TimeoutPolicy(config)
        self.verdicts = VerdictResolver()
        self.quarantine = QuarantineService(config)

    def scan_file(self, file_path: Path, quarantine_mode: QuarantineMode, dry_run_quarantine: bool) -> ScanReport:
        target = FileTarget.from_path(file_path)
        return self._scan_file_target(
            target=target,
            original_path=str(target.path),
            quarantine_mode=quarantine_mode,
            dry_run_quarantine=dry_run_quarantine,
        )

    def scan_directory(
        self,
        directory_path: Path,
        quarantine_mode: QuarantineMode,
        dry_run_quarantine: bool,
    ) -> DirectoryScanReport:
        target = DirectoryTarget.from_path(directory_path)
        report = build_directory_report_shell(str(target.path), self.config.app.default_profile)
        report.started_at = datetime.now(timezone.utc)

        candidates, directory_issues, ignored_directory_count = self._enumerate_directory_files(target.path)
        report.target = DirectoryTargetInfo(
            original_path=str(directory_path),
            normalized_path=str(target.path),
            recursive=target.recursive,
        )
        report.target_count = len(candidates)
        report.issues.extend(directory_issues)
        report.accounting = DirectoryScanAccounting(ignored_directory_count=ignored_directory_count)

        for relative_path, absolute_path in candidates:
            child_report = self._scan_directory_entry(
                file_path=absolute_path,
                quarantine_mode=quarantine_mode,
                dry_run_quarantine=dry_run_quarantine,
            )
            report.results.append(
                DirectoryScanEntry(
                    relative_path=relative_path,
                    report=child_report,
                )
            )

        report.scanned_count = len(report.results)
        report.summary = self._build_directory_summary(report.results)
        report.overall_status = self._resolve_directory_overall_status(report.results)
        if not report.results:
            report.issues.append(
                EngineIssue(
                    engine="scanbox",
                    code="no_files_found",
                    message="Directory scan found no files after applying the default ignore rules.",
                    details={"path": str(target.path)},
                )
            )
        self._refresh_directory_accounting(report)
        report.ended_at = datetime.now(timezone.utc)
        return report

    def _scan_file_target(
        self,
        target: FileTarget,
        original_path: str,
        quarantine_mode: QuarantineMode,
        dry_run_quarantine: bool,
    ) -> ScanReport:
        report = build_report_shell(original_path, self.config.app.default_profile)
        report.quarantine.requested_mode = quarantine_mode.value
        report.started_at = datetime.now(timezone.utc)

        try:
            report.hashes = self.hashing.compute(target.path, include_sha1=True)
            file_type = detect_file_type(target.path)
            report.target = TargetInfo(
                original_path=original_path,
                normalized_path=str(target.path),
                size=target.size,
                detected_type=file_type.kind,
                extension=target.extension,
                mime_guess=file_type.mime_guess,
            )

            report.engines = apply_preflight(self.adapters, target, report, self.config)

            for adapter in self.adapters:
                current = report.engines[adapter.name]
                if current.state != EngineState.OK or not current.enabled or not current.applicable:
                    if adapter.name == "capa" and file_type.is_script:
                        current.raw_summary["capa_skipped"] = True
                        current.raw_summary["skip_reason"] = "script_file_not_supported_in_v1_policy"
                    report.engines[adapter.name] = current
                    continue

                result = adapter.scan(target, report, self.config, self.timeouts.for_engine(adapter.name))
                report.engines[adapter.name] = result
                report.issues.extend(result.issues)

            report.overall_status = self.verdicts.resolve(report)
            report.quarantine = self.quarantine.maybe_apply(report, target, quarantine_mode, dry_run_quarantine)
            report.summary = self._build_summary(report)
            report.ended_at = datetime.now(timezone.utc)
            report.disclaimer = DISCLAIMER_TEXT
            return report
        except ScanBoxError as exc:
            report.issues.append(EngineIssue(engine="scanbox", code="scan_error", message=str(exc)))
            report.overall_status = self.verdicts.resolve(report)
            report.summary = self._build_summary(report)
            report.ended_at = datetime.now(timezone.utc)
            return report

    def _build_summary(self, report: ScanReport) -> dict:
        detections = [detection for result in report.engines.values() for detection in result.detections]
        return {
            "engine_count": len(report.engines),
            "detections": len(detections),
            "known_malicious_hits": len([d for d in detections if d.category == "malicious"]),
            "suspicious_hits": len([d for d in detections if d.category == "suspicious"]),
            "status": report.overall_status.value,
        }

    def _scan_directory_entry(
        self,
        file_path: Path,
        quarantine_mode: QuarantineMode,
        dry_run_quarantine: bool,
    ) -> ScanReport:
        try:
            target = FileTarget.from_path(file_path)
        except InputError as exc:
            return self._build_file_error_report(file_path, "file_access_error", str(exc))
        except OSError as exc:
            return self._build_file_error_report(file_path, "file_access_error", str(exc))

        return self._scan_file_target(
            target=target,
            original_path=str(target.path),
            quarantine_mode=quarantine_mode,
            dry_run_quarantine=dry_run_quarantine,
        )

    def _enumerate_directory_files(self, root_path: Path) -> tuple[list[tuple[str, Path]], list[EngineIssue], int]:
        candidates: list[tuple[str, Path]] = []
        issues: list[EngineIssue] = []
        ignored_directory_count = 0

        def _on_error(error: OSError) -> None:
            issues.append(
                EngineIssue(
                    engine="scanbox",
                    code="directory_access_error",
                    message=str(error),
                    details={"path": error.filename or str(root_path)},
                )
            )

        for current_root, dir_names, file_names in os.walk(root_path, topdown=True, onerror=_on_error, followlinks=False):
            filtered_dir_names, ignored_count = self.directory_policy.filter_directory_names(dir_names)
            dir_names[:] = filtered_dir_names
            ignored_directory_count += ignored_count
            current_root_path = Path(current_root)
            for file_name in file_names:
                absolute_path = (current_root_path / file_name).resolve()
                relative_path = absolute_path.relative_to(root_path).as_posix()
                candidates.append((relative_path, absolute_path))

        candidates.sort(key=lambda item: item[0])
        return candidates, issues, ignored_directory_count

    def _build_directory_summary(self, results: list[DirectoryScanEntry]) -> DirectoryScanSummary:
        summary = DirectoryScanSummary()
        for entry in results:
            status = entry.report.overall_status.value
            if hasattr(summary, status):
                current_value = getattr(summary, status)
                setattr(summary, status, current_value + 1)
        return summary

    def _resolve_directory_overall_status(self, results: list[DirectoryScanEntry]) -> VerdictStatus:
        if not results:
            return VerdictStatus.SCAN_ERROR

        present_statuses = {entry.report.overall_status.value for entry in results}
        for status in self._VERDICT_PRIORITY:
            if status in present_statuses:
                return VerdictStatus(status)

        return VerdictStatus.SCAN_ERROR

    def _refresh_directory_accounting(self, report: DirectoryScanReport) -> None:
        report.accounting.top_level_issue_count = len(report.issues)
        report.accounting.directory_access_error_count = sum(
            1 for issue in report.issues if issue.code == "directory_access_error"
        )
        report.error_count = report.summary.scan_error + report.accounting.top_level_issue_count

    def _build_file_error_report(self, file_path: Path, code: str, message: str) -> ScanReport:
        report = build_report_shell(str(file_path), self.config.app.default_profile)
        report.started_at = datetime.now(timezone.utc)
        report.ended_at = datetime.now(timezone.utc)
        report.target = TargetInfo(
            original_path=str(file_path),
            normalized_path=str(file_path),
            size=0,
            detected_type="unknown",
        )
        report.issues.append(EngineIssue(engine="scanbox", code=code, message=message))
        report.overall_status = self.verdicts.resolve(report)
        report.summary = self._build_summary(report)
        report.disclaimer = DISCLAIMER_TEXT
        return report
