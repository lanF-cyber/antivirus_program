from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scanbox.core.errors import InputError


@dataclass(slots=True)
class DirectoryTarget:
    path: Path
    recursive: bool = True

    @classmethod
    def from_path(cls, path: Path) -> "DirectoryTarget":
        resolved = path if path.is_absolute() else (Path.cwd() / path)
        resolved = resolved.resolve()
        if not resolved.exists():
            raise InputError(f"Target directory does not exist: {resolved}")
        if resolved.is_file():
            raise InputError(f"Target is not a directory: {resolved}")
        if not resolved.is_dir():
            raise InputError(f"Target is not a directory: {resolved}")
        return cls(path=resolved, recursive=True)
