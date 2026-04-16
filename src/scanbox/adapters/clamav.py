from __future__ import annotations

import shutil
from datetime import datetime, timezone

from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.errors import EngineExecutionError, EngineTimeoutError
from scanbox.core import issue_text
from scanbox.core.models import Detection, EngineIssue, EngineScanResult, ScanReport
from scanbox.core.rulesets import count_visible_files
from scanbox.core.subprocess_runner import SubprocessRunner
from scanbox.targets.file_target import FileTarget


class ClamAvAdapter:
    name = "clamav"

    def __init__(self, runner: SubprocessRunner | None = None) -> None:
        self._runner = runner or SubprocessRunner()

    def is_enabled(self, settings: AppConfig) -> bool:
        return settings.engines.clamav.enabled

    def discover(self, settings: AppConfig) -> EngineIssue | None:
        engine = settings.engines.clamav
        executable = engine.executable
        if executable is None:
            return EngineIssue(
                engine=self.name,
                code="executable_missing",
                message=issue_text.executable_not_configured(self.name),
            )
        if executable.exists() and not executable.is_file():
            return EngineIssue(
                engine=self.name,
                code="configured_path_invalid",
                message=issue_text.configured_path_invalid(self.name, "executable", "file"),
                details={
                    "field": "executable",
                    "path": str(executable),
                    "expected": "file",
                },
            )
        if not executable.exists() and shutil.which(str(executable)) is None:
            return EngineIssue(
                engine=self.name,
                code="executable_missing",
                message=issue_text.executable_not_found(self.name),
                details={"path": str(executable)},
            )
        if engine.database_dir is None or not engine.database_dir.exists():
            return EngineIssue(
                engine=self.name,
                code="database_missing",
                message=issue_text.database_missing(self.name),
                details={"database_dir": str(engine.database_dir) if engine.database_dir else None},
            )
        if not engine.database_dir.is_dir():
            return EngineIssue(
                engine=self.name,
                code="configured_path_invalid",
                message=issue_text.configured_path_invalid(self.name, "database", "directory"),
                details={
                    "field": "database_dir",
                    "database_dir": str(engine.database_dir),
                    "expected": "directory",
                },
            )
        database_file_count = count_visible_files(engine.database_dir)
        if database_file_count == 0:
            return EngineIssue(
                engine=self.name,
                code="database_empty",
                message=issue_text.database_empty(self.name),
                details={
                    "database_dir": str(engine.database_dir),
                    "database_file_count": database_file_count,
                },
            )
        return None

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        return True

    def _build_failure_summary(self, *candidates: str | None) -> str | None:
        for candidate in candidates:
            summary = issue_text.shorten_clue(candidate)
            if summary:
                return summary
        return None

    def _build_result_summary(self, returncode: int | None, match_count: int, failure_kind: str | None = None) -> str:
        if failure_kind == "timeout":
            return "timed out"
        if failure_kind == "execution_failed":
            return "execution failed"
        if returncode == 2:
            return "runtime error"
        if match_count > 0:
            return f"{match_count} signature hit(s)"
        return "no signatures detected"

    def scan(self, target: FileTarget, report: ScanReport, settings: AppConfig, timeout_seconds: int) -> EngineScanResult:
        started_at = datetime.now(timezone.utc)
        engine = settings.engines.clamav
        command = [str(engine.executable), "--no-summary", "--stdout"]
        if engine.database_dir:
            command.extend(["--database", str(engine.database_dir)])
        command.append(str(target.path))

        try:
            result = self._runner.run(command, timeout_seconds=timeout_seconds)
        except EngineTimeoutError as exc:
            failure_summary = self._build_failure_summary(str(exc))
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.TIMEOUT,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="timeout", message=issue_text.timed_out(self.name))],
                raw_summary={
                    "command": command,
                    "returncode": None,
                    "match_count": 0,
                    "result_summary": self._build_result_summary(None, 0, failure_kind="timeout"),
                    "stdout": "",
                    "stderr": "",
                    "failure_summary": failure_summary,
                },
            )
        except EngineExecutionError as exc:
            failure_summary = self._build_failure_summary(str(exc))
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.UNAVAILABLE,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="execution_failed", message=issue_text.execution_failed(self.name))],
                raw_summary={
                    "command": command,
                    "returncode": None,
                    "match_count": 0,
                    "result_summary": self._build_result_summary(None, 0, failure_kind="execution_failed"),
                    "stdout": "",
                    "stderr": "",
                    "failure_summary": failure_summary,
                },
            )

        detections: list[Detection] = []
        issues: list[EngineIssue] = []
        state = EngineState.OK
        stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

        failure_summary = None

        if result.returncode == 1:
            for line in stdout_lines:
                if line.endswith("FOUND") and ": " in line:
                    _, signature = line.rsplit(": ", 1)
                    signature = signature.removesuffix(" FOUND").strip()
                    detections.append(
                        Detection(
                            source=self.name,
                            rule_id=signature,
                            title=signature,
                            severity="high",
                            confidence="high",
                            category="malicious",
                            description="ClamAV reported a malicious signature hit.",
                            evidence={"line": line},
                        )
                    )
        elif result.returncode == 2:
            state = EngineState.UNAVAILABLE
            failure_summary = self._build_failure_summary(result.stderr, result.stdout)
            issues.append(
                EngineIssue(
                    engine=self.name,
                    code="clamav_runtime_error",
                    message=issue_text.runtime_error(self.name),
                    details={"stderr": result.stderr.strip(), "stdout": result.stdout.strip()},
                )
            )

        match_count = len(detections)
        return EngineScanResult(
            engine=self.name,
            enabled=True,
            applicable=True,
            state=state,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            duration_ms=result.duration_ms,
            detections=detections,
            issues=issues,
            raw_summary={
                "command": result.command,
                "returncode": result.returncode,
                "match_count": match_count,
                "result_summary": self._build_result_summary(result.returncode, match_count),
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                **({"failure_summary": failure_summary} if failure_summary else {}),
            },
        )
