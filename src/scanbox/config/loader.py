from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from scanbox.config.models import AppConfig
from scanbox.config.validator import normalize_config_paths, validate_config
from scanbox.core.enums import ScanProfile
from scanbox.core.errors import ConfigError


ENV_MAP: dict[str, tuple[str, ...]] = {
    "SCANBOX_DEFAULT_PROFILE": ("app", "default_profile"),
    "SCANBOX_VERBOSE": ("app", "verbose"),
    "SCANBOX_REPORT_OUTPUT_DIR": ("app", "report_output_dir"),
    "SCANBOX_CLAMAV_EXECUTABLE": ("engines", "clamav", "executable"),
    "SCANBOX_CLAMAV_DATABASE_DIR": ("engines", "clamav", "database_dir"),
    "SCANBOX_YARA_RULES_DIR": ("engines", "yara", "rules_dir"),
    "SCANBOX_YARA_MANIFEST": ("engines", "yara", "manifest"),
    "SCANBOX_CAPA_EXECUTABLE": ("engines", "capa", "executable"),
    "SCANBOX_CAPA_RULES_DIR": ("engines", "capa", "rules_dir"),
    "SCANBOX_CAPA_MANIFEST": ("engines", "capa", "manifest"),
    "SCANBOX_QUARANTINE_DIRECTORY": ("quarantine", "directory"),
}


def _set_nested(mapping: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    current = mapping
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_env_value(value: str) -> str | bool:
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def _read_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    try:
        with config_path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Config file is not valid TOML: {config_path} ({exc})") from exc


def _derive_local_override_path(config_path: Path) -> Path | None:
    if config_path.stem.endswith(".local"):
        return None
    return config_path.with_name(f"{config_path.stem}.local{config_path.suffix}")


def _read_env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for env_name, keys in ENV_MAP.items():
        if env_name in os.environ:
            _set_nested(overrides, keys, _parse_env_value(os.environ[env_name]))
    return overrides


def load_app_config(
    config_path: Path,
    profile_override: str | None = None,
    verbose_override: bool = False,
) -> AppConfig:
    root_dir = Path.cwd().resolve()
    config_file = config_path if config_path.is_absolute() else (root_dir / config_path)
    config_file = config_file.resolve()
    config_data = _read_config_file(config_file)

    local_override_file = _derive_local_override_path(config_file)
    if local_override_file and local_override_file.exists():
        config_data = _deep_merge(config_data, _read_config_file(local_override_file))

    env_data = _read_env_overrides()

    cli_data: dict[str, Any] = {}
    if profile_override:
        _set_nested(cli_data, ("app", "default_profile"), profile_override)
    if verbose_override:
        _set_nested(cli_data, ("app", "verbose"), True)

    merged = _deep_merge(config_data, env_data)
    merged = _deep_merge(merged, cli_data)

    config = AppConfig(root_dir=root_dir, config_path=config_file, **merged)
    if isinstance(config.app.default_profile, str):
        config.app.default_profile = ScanProfile(config.app.default_profile)
    config = normalize_config_paths(config)
    return validate_config(config)
