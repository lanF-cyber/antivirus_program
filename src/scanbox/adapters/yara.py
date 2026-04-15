from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.models import Detection, EngineIssue, EngineScanResult, ScanReport
from scanbox.core.rulesets import YARA_RULE_EXTENSIONS, inspect_ruleset
from scanbox.targets.file_target import FileTarget

try:
    import yara as yara_lib
except ImportError:  # pragma: no cover
    yara_lib = None


def _normalize_level(value: Any, default: str) -> str:
    if isinstance(value, str) and value.lower() in {"high", "medium", "low"}:
        return value.lower()
    return default


class YaraAdapter:
    name = "yara"

    def is_enabled(self, settings: AppConfig) -> bool:
        return settings.engines.yara.enabled

    def discover(self, settings: AppConfig) -> EngineIssue | None:
        engine = settings.engines.yara
        if yara_lib is None:
            return EngineIssue(engine=self.name, code="python_module_missing", message="yara-python is not installed")
        inspection = inspect_ruleset(
            engine=self.name,
            rules_dir=engine.rules_dir,
            manifest_path=engine.manifest,
            rule_extensions=YARA_RULE_EXTENSIONS,
            require_vendor_status=False,
        )
        if not inspection.rules_dir_exists:
            return EngineIssue(
                engine=self.name,
                code="rules_missing",
                message="YARA rules directory was not found",
                details=inspection.to_details(),
            )
        if not inspection.manifest_exists:
            return EngineIssue(
                engine=self.name,
                code="manifest_missing",
                message="YARA rules manifest was not found",
                details=inspection.to_details(),
            )
        if inspection.has_mismatch:
            return EngineIssue(
                engine=self.name,
                code="manifest_mismatch",
                message="YARA rules manifest could not be validated against the bundled rules directory",
                details=inspection.to_details(),
            )
        if inspection.rule_count == 0:
            return EngineIssue(
                engine=self.name,
                code="rules_empty",
                message="No YARA rule files were found in the configured rules directory",
                details=inspection.to_details(),
            )
        return None

    def supports(self, target: FileTarget, report: ScanReport) -> bool:
        return True

    def _compile_rules(self, settings: AppConfig):
        filepaths: dict[str, str] = {}
        rules_dir = settings.engines.yara.rules_dir
        for rule_file in sorted(list(rules_dir.rglob("*.yar")) + list(rules_dir.rglob("*.yara"))):
            filepaths[rule_file.stem] = str(rule_file)
        return yara_lib.compile(filepaths=filepaths)

    def _detection_from_match(self, match: Any) -> Detection:
        meta = dict(getattr(match, "meta", {}) or {})
        if meta.get("malicious") is True or str(meta.get("category", "")).lower() == "malicious":
            category = "malicious"
            severity = _normalize_level(meta.get("severity"), "high")
            confidence = _normalize_level(meta.get("confidence"), "high")
        else:
            category = "suspicious"
            severity = _normalize_level(meta.get("severity"), "medium")
            confidence = _normalize_level(meta.get("confidence"), "medium")
        return Detection(
            source=self.name,
            rule_id=getattr(match, "rule", "unknown_rule"),
            title=meta.get("title") or getattr(match, "rule", "unknown_rule"),
            severity=severity,
            confidence=confidence,
            category=category,
            description=meta.get("description"),
            evidence={
                "namespace": getattr(match, "namespace", None),
                "tags": list(getattr(match, "tags", []) or []),
                "meta": meta,
            },
        )

    def scan(self, target: FileTarget, report: ScanReport, settings: AppConfig, timeout_seconds: int) -> EngineScanResult:
        started_at = datetime.now(timezone.utc)
        try:
            compiled = self._compile_rules(settings)
            matches = compiled.match(str(target.path), timeout=timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            state = EngineState.TIMEOUT if "timeout" in exc.__class__.__name__.lower() or "timeout" in str(exc).lower() else EngineState.UNAVAILABLE
            code = "timeout" if state == EngineState.TIMEOUT else "yara_scan_failed"
            return EngineScanResult(
                engine=self.name,
                enabled=True,
                applicable=True,
                state=state,
                started_at=started_at,
                ended_at=datetime.now(timezone.utc),
                issues=[EngineIssue(engine=self.name, code=code, message=str(exc))],
            )

        detections = [self._detection_from_match(match) for match in matches]
        return EngineScanResult(
            engine=self.name,
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            detections=detections,
            raw_summary={
                "match_count": len(detections),
                "match_rules": [d.rule_id for d in detections],
            },
        )
