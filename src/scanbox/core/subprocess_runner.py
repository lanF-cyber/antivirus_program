from __future__ import annotations

import subprocess
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from time import perf_counter
from typing import Mapping

from scanbox.core.errors import EngineExecutionError, EngineTimeoutError


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


class SubprocessRunner:
    def run(
        self,
        command: list[str],
        timeout_seconds: int,
        cwd: Path | None = None,
        env: Mapping[str, str | PathLike[str]] | None = None,
    ) -> CommandResult:
        started = perf_counter()
        try:
            normalized_env = None
            if env is not None:
                normalized_env = {key: str(value) for key, value in env.items()}
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                cwd=str(cwd) if cwd else None,
                env=normalized_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EngineTimeoutError(f"Command timed out after {timeout_seconds}s: {' '.join(command)}") from exc
        except OSError as exc:
            raise EngineExecutionError(f"Failed to execute command: {' '.join(command)} ({exc})") from exc

        duration_ms = int((perf_counter() - started) * 1000)
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration_ms,
        )
