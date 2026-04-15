from __future__ import annotations

import shutil
from datetime import datetime, timezone

from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.errors import EngineExecutionError, EngineTimeoutError
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
            return EngineIssue(engine=self.name, code="executable_missing", message="ClamAV executable is not configured")
        if executable.exists() and not executable.is_file():
            return EngineIssue(
                engine=self.name,
                code="configured_path_invalid",
                message="ClamAV executable path exists but is not a file",
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
                message="ClamAV executable was not found",
                details={"path": str(executable)},
            )
        if engine.database_dir is None or not engine.database_dir.exists():
            return EngineIssue(
                engine=self.name,
                code="database_missing",
                message="ClamAV database directory was not found",
                details={"database_dir": str(engine.database_dir) if engine.database_dir else None},
            )
        if not engine.database_dir.is_dir():
            return EngineIssue(
                engine=self.name,
                code="configured_path_invalid",
                message="ClamAV database path exists but is not a directory",
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
                message="ClamAV database directory exists but does not contain any database files",
                details={
                    "database_dir": str(engine.database_dir),
                    "database_file_count": database_file_count,
                },
            )
        return None

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        return True

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
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.TIMEOUT,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="timeout", message=str(exc))],
            )
        except EngineExecutionError as exc:
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=EngineState.UNAVAILABLE,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code="execution_failed", message=str(exc))],
            )

        detections: list[Detection] = []
        issues: list[EngineIssue] = []
        state = EngineState.OK
        stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

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
            issues.append(
                EngineIssue(
                    engine=self.name,
                    code="clamav_runtime_error",
                    message="ClamAV returned a runtime error",
                    details={"stderr": result.stderr.strip(), "stdout": result.stdout.strip()},
                )
            )

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
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
        )
