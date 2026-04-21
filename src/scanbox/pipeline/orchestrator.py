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
from scanbox.core import issue_text
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
from scanbox.pipeline.archive_expansion import ArchiveExpansionBudget, expand_zip_archive
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
        return self._scan_file_target_with_archive_expansion(
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

        candidates, directory_issues, ignored_directory_count, ignored_file_count = self._enumerate_directory_files(
            target.path
        )
        report.target = DirectoryTargetInfo(
            original_path=str(directory_path),
            normalized_path=str(target.path),
            recursive=target.recursive,
        )
        report.target_count = len(candidates)
        report.issues.extend(directory_issues)
        report.accounting = DirectoryScanAccounting(
            ignored_directory_count=ignored_directory_count,
            ignored_file_count=ignored_file_count,
        )

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
                    message=issue_text.scanbox_issue("no_files_found"),
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
        archive_path: str | None = None,
        archive_member_path: str | None = None,
        archive_depth: int | None = None,
        allow_quarantine: bool = True,
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
                archive_path=archive_path,
                archive_member_path=archive_member_path,
                archive_depth=archive_depth,
            )

            report.engines = apply_preflight(self.adapters, target, report, self.config)

            for adapter in self.adapters:
                current = report.engines[adapter.name]
                if current.state != EngineState.OK or not current.enabled or not current.applicable:
                    if adapter.name == "capa" and file_type.is_script:
                        current.raw_summary["capa_skipped"] = True
                        current.raw_summary["skip_reason"] = "script_file_not_supported_in_v1_policy"
                        current.raw_summary["result_summary"] = issue_text.scan_skipped_result_summary()
                    report.engines[adapter.name] = current
                    continue

                result = adapter.scan(target, report, self.config, self.timeouts.for_engine(adapter.name))
                report.engines[adapter.name] = result
                report.issues.extend(result.issues)

            report.overall_status = self.verdicts.resolve(report)
            if allow_quarantine:
                report.quarantine = self.quarantine.maybe_apply(report, target, quarantine_mode, dry_run_quarantine)
            report.summary = self._build_summary(report)
            report.ended_at = datetime.now(timezone.utc)
            report.disclaimer = DISCLAIMER_TEXT
            return report
        except ScanBoxError as exc:
            report.issues.append(
                EngineIssue(
                    engine="scanbox",
                    code="scan_error",
                    message=issue_text.scanbox_issue("scan_error", clue=str(exc)),
                )
            )
            report.overall_status = self.verdicts.resolve(report)
            report.summary = self._build_summary(report)
            report.ended_at = datetime.now(timezone.utc)
            return report

    def _build_summary(self, report: ScanReport) -> dict:
        detections = [
            detection
            for nested_report in self._iter_report_tree(report)
            for result in nested_report.engines.values()
            for detection in result.detections
        ]
        archive_member_count, archive_scanned_member_count, archive_total_extracted_bytes = self._collect_archive_accounting(
            report
        )
        return {
            "engine_count": len(report.engines),
            "detections": len(detections),
            "known_malicious_hits": len([d for d in detections if d.category == "malicious"]),
            "suspicious_hits": len([d for d in detections if d.category == "suspicious"]),
            "archive_member_count": archive_member_count,
            "archive_scanned_member_count": archive_scanned_member_count,
            "archive_total_extracted_bytes": archive_total_extracted_bytes,
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

        return self._scan_file_target_with_archive_expansion(
            target=target,
            original_path=str(target.path),
            quarantine_mode=quarantine_mode,
            dry_run_quarantine=dry_run_quarantine,
        )

    def _scan_file_target_with_archive_expansion(
        self,
        target: FileTarget,
        original_path: str,
        quarantine_mode: QuarantineMode,
        dry_run_quarantine: bool,
        archive_root_path: str | None = None,
        archive_member_path: str | None = None,
        archive_depth: int | None = None,
        budget: ArchiveExpansionBudget | None = None,
    ) -> ScanReport:
        report = self._scan_file_target(
            target=target,
            original_path=original_path,
            quarantine_mode=quarantine_mode,
            dry_run_quarantine=dry_run_quarantine,
            archive_path=archive_root_path,
            archive_member_path=archive_member_path,
            archive_depth=archive_depth,
            allow_quarantine=archive_member_path is None,
        )
        container_status = report.overall_status

        if not self.config.directory_scan.zip_expansion_enabled:
            return report
        if report.target.detected_type != "zip_archive":
            return report

        current_archive_depth = archive_depth or 0
        max_depth = self.config.directory_scan.max_archive_expansion_depth
        if current_archive_depth >= max_depth:
            if archive_member_path is not None:
                report.issues.append(
                    self._build_archive_issue(
                        code="archive_depth_limit_exceeded",
                        archive_path=archive_root_path or str(target.path),
                        member_path=archive_member_path,
                        details={"max_archive_expansion_depth": max_depth},
                    )
                )
                report.overall_status = self._resolve_archive_aware_overall_status(report, container_status)
                report.summary = self._build_summary(report)
            return report

        active_budget = budget or ArchiveExpansionBudget(
            max_member_count=self.config.directory_scan.max_archive_member_count,
            max_total_bytes=self.config.directory_scan.max_archive_total_bytes,
        )
        effective_archive_root = archive_root_path or str(target.path)

        def _scan_member(extracted_path: Path, member_path: str) -> ScanReport:
            child_target = FileTarget.from_path(extracted_path)
            full_member_path = member_path if archive_member_path is None else f"{archive_member_path}::{member_path}"
            return self._scan_file_target_with_archive_expansion(
                target=child_target,
                original_path=f"{effective_archive_root}::{full_member_path}",
                quarantine_mode=quarantine_mode,
                dry_run_quarantine=dry_run_quarantine,
                archive_root_path=effective_archive_root,
                archive_member_path=full_member_path,
                archive_depth=current_archive_depth + 1,
                budget=active_budget,
            )

        archive_expansion, archive_issues = expand_zip_archive(
            archive_path=target.path,
            expansion_depth=current_archive_depth,
            max_expansion_depth=max_depth,
            budget=active_budget,
            scan_member=_scan_member,
        )
        report.archive_expansion = archive_expansion
        report.issues.extend(archive_issues)
        report.overall_status = self._resolve_archive_aware_overall_status(report, container_status)
        report.summary = self._build_summary(report)
        return report

    def _enumerate_directory_files(
        self,
        root_path: Path,
    ) -> tuple[list[tuple[str, Path]], list[EngineIssue], int, int]:
        candidates: list[tuple[str, Path]] = []
        issues: list[EngineIssue] = []
        ignored_directory_count = 0
        ignored_file_count = 0

        def _on_error(error: OSError) -> None:
            issues.append(
                EngineIssue(
                    engine="scanbox",
                    code="directory_access_error",
                    message=issue_text.scanbox_issue("directory_access_error", clue=str(error)),
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
                if self.directory_policy.should_ignore_file(relative_path=relative_path, file_name=file_name):
                    ignored_file_count += 1
                    continue
                candidates.append((relative_path, absolute_path))

        candidates.sort(key=lambda item: item[0])
        return candidates, issues, ignored_directory_count, ignored_file_count

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

    def _resolve_archive_aware_overall_status(
        self,
        report: ScanReport,
        container_status: VerdictStatus,
    ) -> VerdictStatus:
        present_statuses = {container_status.value}
        present_statuses.update(
            nested_report.overall_status.value
            for nested_report in self._iter_report_tree(report)
            if nested_report is not report
        )

        issue_codes = {
            issue.code
            for nested_report in self._iter_report_tree(report)
            for issue in nested_report.issues
        }
        if "archive_corrupt" in issue_codes:
            present_statuses.add(VerdictStatus.SCAN_ERROR.value)
        if issue_codes.intersection(
            {
                "archive_password_protected",
                "archive_member_unsupported",
                "archive_depth_limit_exceeded",
                "archive_member_limit_exceeded",
                "archive_byte_budget_exceeded",
            }
        ):
            present_statuses.add(VerdictStatus.PARTIAL_SCAN.value)

        for status in self._VERDICT_PRIORITY:
            if status in present_statuses:
                return VerdictStatus(status)

        return VerdictStatus.SCAN_ERROR

    def _iter_report_tree(self, report: ScanReport):
        yield report
        if report.archive_expansion is None:
            return
        for result in report.archive_expansion.results:
            yield from self._iter_report_tree(result.report)

    def _collect_archive_accounting(self, report: ScanReport) -> tuple[int, int, int]:
        if report.archive_expansion is None:
            return (0, 0, 0)

        member_count = report.archive_expansion.member_count
        scanned_member_count = report.archive_expansion.scanned_member_count
        total_extracted_bytes = report.archive_expansion.total_extracted_bytes
        for result in report.archive_expansion.results:
            child_member_count, child_scanned_member_count, child_total_extracted_bytes = self._collect_archive_accounting(
                result.report
            )
            member_count += child_member_count
            scanned_member_count += child_scanned_member_count
            total_extracted_bytes += child_total_extracted_bytes

        return member_count, scanned_member_count, total_extracted_bytes

    def _build_archive_issue(
        self,
        *,
        code: str,
        archive_path: str,
        member_path: str | None = None,
        clue: str | None = None,
        details: dict[str, object] | None = None,
    ) -> EngineIssue:
        issue_details: dict[str, object] = {"archive_path": archive_path}
        if member_path is not None:
            issue_details["member_path"] = member_path
        if details:
            issue_details.update(details)

        return EngineIssue(
            engine="scanbox",
            code=code,
            message=issue_text.scanbox_issue(code, clue=clue),
            details=issue_details,
        )

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
        report.issues.append(
            EngineIssue(
                engine="scanbox",
                code=code,
                message=issue_text.scanbox_issue(code, clue=message),
            )
        )
        report.overall_status = self.verdicts.resolve(report)
        report.summary = self._build_summary(report)
        report.disclaimer = DISCLAIMER_TEXT
        return report
