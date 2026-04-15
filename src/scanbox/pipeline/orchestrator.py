from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scanbox.adapters.base import ScannerAdapter
from scanbox.adapters.capa import CapaAdapter
from scanbox.adapters.clamav import ClamAvAdapter
from scanbox.adapters.yara import YaraAdapter
from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.errors import ScanBoxError
from scanbox.core.filetypes import detect_file_type
from scanbox.core.hashing import HashingService
from scanbox.core.models import DISCLAIMER_TEXT, EngineIssue, QuarantineMode, ScanReport, TargetInfo, build_report_shell
from scanbox.core.timeouts import TimeoutPolicy
from scanbox.pipeline.preflight import apply_preflight
from scanbox.pipeline.verdicts import VerdictResolver
from scanbox.quarantine.service import QuarantineService
from scanbox.targets.file_target import FileTarget


class ScanOrchestrator:
    def __init__(self, config: AppConfig, adapters: list[ScannerAdapter] | None = None) -> None:
        self.config = config
        self.adapters = adapters or [ClamAvAdapter(), YaraAdapter(), CapaAdapter()]
        self.hashing = HashingService()
        self.timeouts = TimeoutPolicy(config)
        self.verdicts = VerdictResolver()
        self.quarantine = QuarantineService(config)

    def scan_file(self, file_path: Path, quarantine_mode: QuarantineMode, dry_run_quarantine: bool) -> ScanReport:
        target = FileTarget.from_path(file_path)
        report = build_report_shell(str(target.path), self.config.app.default_profile)
        report.quarantine.requested_mode = quarantine_mode.value
        report.started_at = datetime.now(timezone.utc)

        try:
            report.hashes = self.hashing.compute(target.path, include_sha1=True)
            file_type = detect_file_type(target.path)
            report.target = TargetInfo(
                original_path=str(file_path),
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
