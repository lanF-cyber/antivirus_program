from __future__ import annotations

import json
from pathlib import Path

from scanbox.adapters.base import ScannerAdapter
from scanbox.config.models import AppConfig
from scanbox.core.enums import EngineState
from scanbox.core.models import EngineIssue, EngineScanResult, RuleSetInfo, ScanReport
from scanbox.core.rulesets import inspect_ruleset, CAPA_RULE_EXTENSIONS, YARA_RULE_EXTENSIONS
from scanbox.targets.file_target import FileTarget


PRECHECK_STATE_BY_ISSUE_CODE: dict[str, EngineState] = {
    "executable_missing": EngineState.MISSING,
    "configured_path_invalid": EngineState.MISSING,
    "python_module_missing": EngineState.MISSING,
    "database_missing": EngineState.MISSING,
    "database_empty": EngineState.MISSING,
    "rules_missing": EngineState.MISSING,
    "rules_empty": EngineState.MISSING,
    "rules_placeholder": EngineState.MISSING,
    "manifest_missing": EngineState.MISSING,
    "manifest_mismatch": EngineState.UNAVAILABLE,
}


def load_ruleset_info(manifest_path: Path | None) -> RuleSetInfo | None:
    if manifest_path is None or not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return RuleSetInfo(
        name=payload["name"],
        version=payload["version"],
        source=payload["source"],
        pinned_ref=payload["pinned_ref"],
        manifest_path=str(manifest_path),
        build_time=payload.get("build_time"),
        enabled_rule_count=payload.get("enabled_rule_count", payload.get("rule_count")),
        vendor_status=payload.get("vendor_status"),
        vendored_at=payload.get("vendored_at"),
        rule_count=payload.get("rule_count", payload.get("enabled_rule_count")),
        notes=payload.get("notes"),
    )


def build_engine_result(
    *,
    engine: str,
    enabled: bool,
    applicable: bool,
    state: EngineState,
    issue: EngineIssue | None = None,
    raw_summary: dict | None = None,
) -> EngineScanResult:
    return EngineScanResult(
        engine=engine,
        enabled=enabled,
        applicable=applicable,
        state=state,
        issues=[issue] if issue else [],
        raw_summary=(raw_summary or {})
        | (
            {
                "preflight_issue_code": issue.code,
                "preflight_message": issue.message,
            }
            | issue.details
            if issue
            else {}
        ),
    )


def apply_preflight(
    adapters: list[ScannerAdapter],
    target: FileTarget,
    report: ScanReport,
    settings: AppConfig,
) -> dict[str, EngineScanResult]:
    results: dict[str, EngineScanResult] = {}
    yara_inspection = inspect_ruleset(
        engine="yara",
        rules_dir=settings.engines.yara.rules_dir,
        manifest_path=settings.engines.yara.manifest,
        rule_extensions=YARA_RULE_EXTENSIONS,
    )
    capa_inspection = inspect_ruleset(
        engine="capa",
        rules_dir=settings.engines.capa.rules_dir,
        manifest_path=settings.engines.capa.manifest,
        rule_extensions=CAPA_RULE_EXTENSIONS,
        require_vendor_status=True,
    )

    report.rulesets["yara"] = load_ruleset_info(settings.engines.yara.manifest) or RuleSetInfo(
        name="missing_yara_manifest",
        version="unknown",
        source="unavailable",
        pinned_ref="unknown",
        rule_count=yara_inspection.rule_count,
    )
    report.rulesets["capa"] = load_ruleset_info(settings.engines.capa.manifest) or RuleSetInfo(
        name="missing_capa_manifest",
        version="unknown",
        source="unavailable",
        pinned_ref="unknown",
        vendor_status=capa_inspection.vendor_status,
        rule_count=capa_inspection.rule_count,
    )

    for adapter in adapters:
        enabled = adapter.is_enabled(settings)
        if not enabled:
            results[adapter.name] = build_engine_result(
                engine=adapter.name,
                enabled=False,
                applicable=False,
                state=EngineState.SKIPPED_POLICY,
            )
            continue

        applicable = adapter.supports(target, report)
        if not applicable:
            results[adapter.name] = build_engine_result(
                engine=adapter.name,
                enabled=True,
                applicable=False,
                state=EngineState.SKIPPED_NOT_APPLICABLE,
                raw_summary={"skip_reason": "not_applicable_for_target"},
            )
            continue

        issue = adapter.discover(settings)
        if issue is not None:
            results[adapter.name] = build_engine_result(
                engine=adapter.name,
                enabled=True,
                applicable=True,
                state=PRECHECK_STATE_BY_ISSUE_CODE.get(issue.code, EngineState.UNAVAILABLE),
                issue=issue,
            )
            report.issues.append(issue)
            continue

        results[adapter.name] = build_engine_result(
            engine=adapter.name,
            enabled=True,
            applicable=True,
            state=EngineState.OK,
        )

    return results
