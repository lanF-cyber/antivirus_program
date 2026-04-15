from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from scanbox import __version__
from scanbox.core.enums import EngineState, ScanProfile, VerdictStatus


DISCLAIMER_TEXT = "ScanBox only reports what the enabled local checks observed. No non-hit or clean status guarantees that a file is safe."


class FileHashes(BaseModel):
    sha256: str
    md5: str | None = None
    sha1: str | None = None


class TargetInfo(BaseModel):
    original_path: str
    normalized_path: str
    size: int
    detected_type: str
    extension: str | None = None
    mime_guess: str | None = None


class RuleSetInfo(BaseModel):
    name: str
    version: str
    source: str
    pinned_ref: str
    manifest_path: str | None = None
    build_time: str | None = None
    enabled_rule_count: int | None = None
    vendor_status: str | None = None
    vendored_at: str | None = None
    rule_count: int | None = None
    notes: str | None = None


class Detection(BaseModel):
    source: str
    rule_id: str
    title: str | None = None
    severity: Literal["high", "medium", "low"]
    confidence: Literal["high", "medium", "low"]
    category: Literal["malicious", "suspicious", "informational"]
    description: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class EngineIssue(BaseModel):
    engine: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EngineScanResult(BaseModel):
    engine: str
    enabled: bool
    applicable: bool
    state: EngineState
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    detections: list[Detection] = Field(default_factory=list)
    issues: list[EngineIssue] = Field(default_factory=list)
    raw_summary: dict[str, Any] = Field(default_factory=dict)


class QuarantineMode(str, Enum):
    OFF = "off"
    ASK = "ask"
    MOVE = "move"


class QuarantineAction(BaseModel):
    requested_mode: Literal["off", "ask", "move"]
    dry_run: bool = False
    performed: bool = False
    original_path: str | None = None
    quarantine_path: str | None = None
    moved_at: datetime | None = None
    reason: str | None = None
    audit_path: str | None = None


class ScanReport(BaseModel):
    schema_version: str = "1.0.0"
    scanbox_version: str = __version__
    scan_id: str = Field(default_factory=lambda: uuid4().hex)
    profile: ScanProfile = ScanProfile.BALANCED
    overall_status: VerdictStatus = VerdictStatus.SCAN_ERROR
    disclaimer: str = DISCLAIMER_TEXT
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target: TargetInfo = Field(
        default_factory=lambda: TargetInfo(
            original_path="",
            normalized_path="",
            size=0,
            detected_type="unknown",
        )
    )
    hashes: FileHashes = Field(default_factory=lambda: FileHashes(sha256="", md5=None, sha1=None))
    rulesets: dict[str, RuleSetInfo] = Field(default_factory=dict)
    engines: dict[str, EngineScanResult] = Field(default_factory=dict)
    quarantine: QuarantineAction = Field(default_factory=lambda: QuarantineAction(requested_mode="ask"))
    ioc: dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "matched": False,
            "source": None,
            "matches": [],
        }
    )
    issues: list[EngineIssue] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


def build_report_shell(original_path: str, profile: ScanProfile) -> ScanReport:
    return ScanReport(
        profile=profile,
        target=TargetInfo(
            original_path=original_path,
            normalized_path=original_path,
            size=0,
            detected_type="unknown",
        ),
        quarantine=QuarantineAction(requested_mode=QuarantineMode.ASK.value),
    )
