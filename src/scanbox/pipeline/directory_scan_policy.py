from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from scanbox.config.models import DirectoryScanSettings


@dataclass(frozen=True, slots=True)
class DirectoryScanPolicy:
    ignored_directory_names: frozenset[str] = field(
        default_factory=lambda: frozenset({".git", ".venv", "__pycache__"})
    )
    ignored_file_names: tuple[str, ...] = ()
    ignored_suffixes: tuple[str, ...] = ()
    ignored_patterns: tuple[str, ...] = ()

    @classmethod
    def default(cls) -> "DirectoryScanPolicy":
        return cls.from_settings(DirectoryScanSettings())

    @classmethod
    def from_settings(cls, settings: DirectoryScanSettings) -> "DirectoryScanPolicy":
        return cls(
            ignored_directory_names=frozenset(settings.ignored_directory_names),
            ignored_file_names=tuple(settings.ignored_file_names),
            ignored_suffixes=tuple(settings.ignored_suffixes),
            ignored_patterns=tuple(settings.ignored_patterns),
        )

    def should_ignore_directory_name(self, name: str) -> bool:
        return name in self.ignored_directory_names

    def should_ignore_file_name(self, name: str) -> bool:
        return name in self.ignored_file_names

    def should_ignore_suffix(self, name: str) -> bool:
        return any(name.endswith(suffix) for suffix in self.ignored_suffixes)

    def should_ignore_file(self, *, relative_path: str, file_name: str) -> bool:
        del relative_path
        return self.should_ignore_file_name(file_name) or self.should_ignore_suffix(file_name)

    def filter_directory_names(self, names: Iterable[str]) -> tuple[list[str], int]:
        kept: list[str] = []
        ignored_count = 0
        for name in names:
            if self.should_ignore_directory_name(name):
                ignored_count += 1
                continue
            kept.append(name)
        return kept, ignored_count
