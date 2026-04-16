from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.errors import EngineExecutionError, EngineTimeoutError
from scanbox.core import issue_text
from scanbox.core.models import Detection, EngineIssue, EngineScanResult, ScanReport
from scanbox.core.rulesets import CAPA_RULE_EXTENSIONS, inspect_ruleset
from scanbox.core.subprocess_runner import SubprocessRunner
from scanbox.targets.file_target import FileTarget


class CapaAdapter:
    name = "capa"
    _SUSPICIOUS_KEYWORDS = (
        "process injection",
        "create thread",
        "download",
        "http",
        "https",
        "persistence",
        "credential",
        "shellcode",
        "anti-debug",
    )

    def __init__(self, runner: SubprocessRunner | None = None) -> None:
        self._runner = runner or SubprocessRunner()

    def is_enabled(self, settings: AppConfig) -> bool:
        return settings.engines.capa.enabled

    def discover(self, settings: AppConfig) -> EngineIssue | None:
        engine = settings.engines.capa
        executable = engine.executable
        if executable is None:
            return EngineIssue(
                engine=self.name,
                code="executable_missing",
                message=issue_text.executable_not_configured(self.name),
            )
        if not executable.exists() and shutil.which(str(executable)) is None:
            return EngineIssue(
                engine=self.name,
                code="executable_missing",
                message=issue_text.executable_not_found(self.name),
                details={"path": str(executable)},
            )
        inspection = inspect_ruleset(
            engine=self.name,
            rules_dir=engine.rules_dir,
            manifest_path=engine.manifest,
            rule_extensions=CAPA_RULE_EXTENSIONS,
            require_vendor_status=True,
        )
        if not inspection.rules_dir_exists:
            return EngineIssue(
                engine=self.name,
                code="rules_missing",
                message=issue_text.rules_missing(self.name),
                details=inspection.to_details(),
            )
        if not inspection.manifest_exists:
            return EngineIssue(
                engine=self.name,
                code="manifest_missing",
                message=issue_text.manifest_missing(self.name),
                details=inspection.to_details(),
            )
        if inspection.has_mismatch:
            return EngineIssue(
                engine=self.name,
                code="manifest_mismatch",
                message=issue_text.manifest_mismatch(self.name),
                details=inspection.to_details(),
            )
        if inspection.placeholder:
            return EngineIssue(
                engine=self.name,
                code="rules_placeholder",
                message=issue_text.rules_placeholder(self.name),
                details=inspection.to_details(),
            )
        if inspection.rule_count == 0:
            return EngineIssue(
                engine=self.name,
                code="rules_empty",
                message=issue_text.rules_empty(self.name, usable=True),
                details=inspection.to_details(),
            )
        return None

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        return report.target.detected_type in {"pe", "elf", "macho"}

    def _build_runtime_environment(self, settings: AppConfig) -> tuple[dict[str, str], Path]:
        runtime_tmp = settings.root_dir / ".local-tools" / "capa" / "runtime-tmp"
        runtime_tmp.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        environment["TMP"] = str(runtime_tmp)
        environment["TEMP"] = str(runtime_tmp)
        return environment, runtime_tmp

    def _extract_detections(self, payload: dict[str, Any]) -> list[Detection]:
        detections: list[Detection] = []
        rules = payload.get("rules", {})
        if isinstance(rules, dict):
            for rule_name, details in rules.items():
                lowered = str(rule_name).lower()
                if any(keyword in lowered for keyword in self._SUSPICIOUS_KEYWORDS):
                    detections.append(
                        Detection(
                            source=self.name,
                            rule_id=str(rule_name),
                            title=str(rule_name),
                            severity="medium",
                            confidence="medium",
                            category="suspicious",
                            description="capa reported a potentially risky capability.",
                            evidence={"details": details},
                        )
                    )
        return detections

    def _build_analysis_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            return {}

        analysis = meta.get("analysis")
        if not isinstance(analysis, dict):
            analysis = {}

        rule_count = payload.get("rules", {})
        matched_rule_count = len(rule_count) if isinstance(rule_count, dict) else 0

        summary: dict[str, Any] = {
            "matched_rule_count": matched_rule_count,
        }
        if meta.get("version") is not None:
            summary["capa_version"] = meta["version"]
        if meta.get("flavor") is not None:
            summary["flavor"] = meta["flavor"]
        if analysis.get("format") is not None:
            summary["format"] = analysis["format"]
        if analysis.get("arch") is not None:
            summary["arch"] = analysis["arch"]
        if analysis.get("os") is not None:
            summary["os"] = analysis["os"]
        if analysis.get("extractor") is not None:
            summary["extractor"] = analysis["extractor"]
        return summary

    def scan(self, target: FileTarget, report: ScanReport, settings: AppConfig, timeout_seconds: int) -> EngineScanResult:
        started_at = datetime.now(timezone.utc)
        engine = settings.engines.capa
        command = [str(engine.executable), "--json", "--rules", str(engine.rules_dir), str(target.path)]
        runtime_environment, runtime_tmp = self._build_runtime_environment(settings)

        try:
            result = self._runner.run(command, timeout_seconds=timeout_seconds, env=runtime_environment)
        except EngineTimeoutError as exc:
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.TIMEOUT,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="timeout", message=issue_text.timed_out(self.name))],
                raw_summary={"command": command, "runtime_temp_dir": str(runtime_tmp)},
            )
        except EngineExecutionError as exc:
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.UNAVAILABLE,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="execution_failed", message=issue_text.execution_failed(self.name))],
                raw_summary={"command": command, "runtime_temp_dir": str(runtime_tmp)},
            )

        if result.returncode != 0:
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.UNAVAILABLE,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                duration_ms=result.duration_ms,
                issues=[
                    EngineIssue(
                        engine=self.name,
                        code="capa_runtime_error",
                        message=issue_text.runtime_error(self.name),
                        details={"stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
                    )
                ],
                raw_summary={
                    "command": command,
                    "returncode": result.returncode,
                    "runtime_temp_dir": str(runtime_tmp),
                },
            )

        try:
            payload = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError as exc:
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.ERROR,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                duration_ms=result.duration_ms,
                issues=[EngineIssue(engine=self.name, code="invalid_json", message=issue_text.invalid_json(self.name))],
                raw_summary={"stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
            )

        detections = self._extract_detections(payload)
        return EngineScanResult(
            engine=self.name,
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            duration_ms=result.duration_ms,
            detections=detections,
            raw_summary={
                "command": command,
                "returncode": result.returncode,
                "runtime_temp_dir": str(runtime_tmp),
                "analysis_summary": self._build_analysis_summary(payload),
                "meta": payload.get("meta"),
                "rule_count": len(payload.get("rules", {})) if isinstance(payload.get("rules"), dict) else None,
            },
        )
