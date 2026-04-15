from __future__ import annotations

import json
import stat as statmod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CAPA_RULE_EXTENSIONS = (".yml", ".yaml")
YARA_RULE_EXTENSIONS = (".yar", ".yara")
VALID_VENDOR_STATUSES = {"placeholder", "vendored"}


def is_hidden_path(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        file_attributes = getattr(path.stat(), "st_file_attributes", 0)
        return bool(file_attributes & getattr(statmod, "FILE_ATTRIBUTE_HIDDEN", 0))
    except OSError:
        return False


def has_hidden_part(path: Path, relative_to: Path | None = None) -> bool:
    try:
        parts = path.relative_to(relative_to).parts if relative_to is not None else path.parts
    except ValueError:
        parts = path.parts
    return any(part.startswith(".") for part in parts)


def count_visible_files(directory: Path | None, extensions: tuple[str, ...] | None = None) -> int:
    if directory is None or not directory.exists() or not directory.is_dir():
        return 0

    normalized_extensions = {extension.lower() for extension in extensions or ()}
    count = 0
    for candidate in directory.rglob("*"):
        if not candidate.is_file() or is_hidden_path(candidate) or has_hidden_part(candidate, directory):
            continue
        if normalized_extensions and candidate.suffix.lower() not in normalized_extensions:
            continue
        count += 1
    return count


@dataclass(slots=True)
class RuleSetInspection:
    engine: str
    rules_dir: Path | None
    manifest_path: Path | None
    rule_extensions: tuple[str, ...]
    rules_dir_exists: bool = False
    manifest_exists: bool = False
    rule_count: int = 0
    manifest: dict[str, Any] | None = None
    manifest_error: str | None = None
    vendor_status: str | None = None
    declared_rule_count: int | None = None
    mismatch_reasons: list[str] = field(default_factory=list)

    @property
    def placeholder(self) -> bool:
        return self.vendor_status == "placeholder"

    @property
    def vendored(self) -> bool:
        return self.vendor_status == "vendored"

    @property
    def has_mismatch(self) -> bool:
        return bool(self.mismatch_reasons)

    def to_details(self) -> dict[str, Any]:
        return {
            "rules_dir": str(self.rules_dir) if self.rules_dir else None,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "rules_dir_exists": self.rules_dir_exists,
            "manifest_exists": self.manifest_exists,
            "rule_count": self.rule_count,
            "declared_rule_count": self.declared_rule_count,
            "vendor_status": self.vendor_status,
            "mismatch_reasons": self.mismatch_reasons,
            "manifest_error": self.manifest_error,
        }


def inspect_ruleset(
    *,
    engine: str,
    rules_dir: Path | None,
    manifest_path: Path | None,
    rule_extensions: tuple[str, ...],
    require_vendor_status: bool = False,
) -> RuleSetInspection:
    inspection = RuleSetInspection(
        engine=engine,
        rules_dir=rules_dir,
        manifest_path=manifest_path,
        rule_extensions=rule_extensions,
    )

    inspection.rules_dir_exists = bool(rules_dir and rules_dir.exists() and rules_dir.is_dir())
    inspection.rule_count = count_visible_files(rules_dir, rule_extensions)

    if manifest_path is None:
        return inspection
    if not manifest_path.exists() or not manifest_path.is_file():
        return inspection

    inspection.manifest_exists = True
    try:
        inspection.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        inspection.manifest_error = str(exc)
        inspection.mismatch_reasons.append("manifest_unreadable")
        return inspection

    vendor_status = inspection.manifest.get("vendor_status")
    if isinstance(vendor_status, str):
        inspection.vendor_status = vendor_status

    declared_rule_count = inspection.manifest.get("rule_count", inspection.manifest.get("enabled_rule_count"))
    if isinstance(declared_rule_count, int):
        inspection.declared_rule_count = declared_rule_count

    if require_vendor_status:
        if inspection.vendor_status is None:
            inspection.mismatch_reasons.append("vendor_status_missing")
        elif inspection.vendor_status not in VALID_VENDOR_STATUSES:
            inspection.mismatch_reasons.append("invalid_vendor_status")

    if inspection.declared_rule_count is not None and inspection.declared_rule_count != inspection.rule_count:
        inspection.mismatch_reasons.append("rule_count_mismatch")

    if inspection.vendor_status == "placeholder" and inspection.rule_count > 0:
        inspection.mismatch_reasons.append("placeholder_with_rules")
    if inspection.vendor_status == "vendored" and inspection.rule_count == 0:
        inspection.mismatch_reasons.append("vendored_without_rules")

    return inspection
