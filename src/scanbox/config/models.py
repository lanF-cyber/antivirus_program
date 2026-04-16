from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from scanbox.core.enums import ScanProfile


class AppSettings(BaseModel):
    default_profile: ScanProfile = ScanProfile.BALANCED
    report_output_dir: Path = Path("reports")
    verbose: bool = False


class TimeoutSettings(BaseModel):
    hash_seconds: int = 10
    clamav_seconds: int = 60
    yara_seconds: int = 30
    capa_seconds: int = 90


class EngineBinarySettings(BaseModel):
    enabled: bool = True
    executable: Path | None = None
    database_dir: Path | None = None
    rules_dir: Path | None = None
    manifest: Path | None = None


class EngineSettings(BaseModel):
    clamav: EngineBinarySettings = Field(default_factory=EngineBinarySettings)
    yara: EngineBinarySettings = Field(default_factory=EngineBinarySettings)
    capa: EngineBinarySettings = Field(default_factory=EngineBinarySettings)


class QuarantineSettings(BaseModel):
    directory: Path = Path("quarantine")


class DirectoryScanSettings(BaseModel):
    ignored_directory_names: list[str] = Field(default_factory=lambda: [".git", ".venv", "__pycache__"])
    ignored_file_names: list[str] = Field(default_factory=list)
    ignored_suffixes: list[str] = Field(default_factory=list)
    ignored_patterns: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    root_dir: Path
    config_path: Path
    app: AppSettings = Field(default_factory=AppSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)
    engines: EngineSettings = Field(default_factory=EngineSettings)
    quarantine: QuarantineSettings = Field(default_factory=QuarantineSettings)
    directory_scan: DirectoryScanSettings = Field(default_factory=DirectoryScanSettings)
