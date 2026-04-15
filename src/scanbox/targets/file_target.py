from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanbox.core.errors import InputError


@dataclass(slots=True)
class FileTarget:
    path: Path
    size: int
    extension: str | None

    @classmethod
    def from_path(cls, path: Path) -> "FileTarget":
        resolved = path if path.is_absolute() else (Path.cwd() / path)
        resolved = resolved.resolve()
        if not resolved.exists():
            raise InputError(f"Target file does not exist: {resolved}")
        if resolved.is_dir():
            raise InputError("Directory input is not supported in ScanBox v1")
        if not resolved.is_file():
            raise InputError(f"Target is not a regular file: {resolved}")
        return cls(path=resolved, size=resolved.stat().st_size, extension=resolved.suffix.lower() or None)
