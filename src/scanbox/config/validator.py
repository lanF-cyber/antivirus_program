from __future__ import annotations

from pathlib import Path

from scanbox.config.models import AppConfig
from scanbox.core.errors import ConfigError


def normalize_path(base_dir: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    if value.is_absolute():
        return value.resolve()
    return (base_dir / value).resolve()


def normalize_config_paths(config: AppConfig) -> AppConfig:
    base_dir = config.root_dir
    config.app.report_output_dir = normalize_path(base_dir, config.app.report_output_dir) or config.app.report_output_dir
    config.quarantine.directory = normalize_path(base_dir, config.quarantine.directory) or config.quarantine.directory

    for engine in (config.engines.clamav, config.engines.yara, config.engines.capa):
        engine.executable = normalize_path(base_dir, engine.executable)
        engine.database_dir = normalize_path(base_dir, engine.database_dir)
        engine.rules_dir = normalize_path(base_dir, engine.rules_dir)
        engine.manifest = normalize_path(base_dir, engine.manifest)

    return config


def validate_config(config: AppConfig) -> AppConfig:
    if config.timeouts.hash_seconds <= 0:
        raise ConfigError("timeouts.hash_seconds must be greater than zero")
    if config.timeouts.clamav_seconds <= 0:
        raise ConfigError("timeouts.clamav_seconds must be greater than zero")
    if config.timeouts.yara_seconds <= 0:
        raise ConfigError("timeouts.yara_seconds must be greater than zero")
    if config.timeouts.capa_seconds <= 0:
        raise ConfigError("timeouts.capa_seconds must be greater than zero")
    if config.directory_scan.max_archive_expansion_depth < 0:
        raise ConfigError("directory_scan.max_archive_expansion_depth must be greater than or equal to zero")
    if config.directory_scan.max_archive_member_count <= 0:
        raise ConfigError("directory_scan.max_archive_member_count must be greater than zero")
    if config.directory_scan.max_archive_total_bytes <= 0:
        raise ConfigError("directory_scan.max_archive_total_bytes must be greater than zero")

    for name, engine in {
        "clamav": config.engines.clamav,
        "yara": config.engines.yara,
        "capa": config.engines.capa,
    }.items():
        if name in {"clamav", "capa"} and engine.enabled and engine.executable is None:
            raise ConfigError(f"engines.{name}.executable must be configured when the engine is enabled")
        if name == "clamav" and engine.enabled and engine.database_dir is None:
            raise ConfigError("engines.clamav.database_dir must be configured when ClamAV is enabled")
        if name in {"yara", "capa"} and engine.enabled and engine.rules_dir is None:
            raise ConfigError(f"engines.{name}.rules_dir must be configured when the engine is enabled")
        if name in {"yara", "capa"} and engine.enabled and engine.manifest is None:
            raise ConfigError(f"engines.{name}.manifest must be configured when the engine is enabled")

    return config
