from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DirectoryScanPolicy:
    ignored_directory_names: frozenset[str] = field(
        default_factory=lambda: frozenset({".git", ".venv", "__pycache__"})
    )

    @classmethod
    def default(cls) -> "DirectoryScanPolicy":
        return cls()

    def should_ignore_directory_name(self, name: str) -> bool:
        return name in self.ignored_directory_names

    def filter_directory_names(self, names: Iterable[str]) -> tuple[list[str], int]:
        kept: list[str] = []
        ignored_count = 0
        for name in names:
            if self.should_ignore_directory_name(name):
                ignored_count += 1
                continue
            kept.append(name)
        return kept, ignored_count
