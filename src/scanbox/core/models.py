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


class DirectoryTargetInfo(BaseModel):
    original_path: str
    normalized_path: str
    recursive: bool = True


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


class DirectoryScanEntry(BaseModel):
    relative_path: str
    report: ScanReport


class DirectoryScanSummary(BaseModel):
    known_malicious: int = 0
    suspicious: int = 0
    clean_by_known_checks: int = 0
    partial_scan: int = 0
    scan_error: int = 0
    engine_missing: int = 0
    engine_unavailable: int = 0


class DirectoryScanAccounting(BaseModel):
    ignored_directory_count: int = 0
    top_level_issue_count: int = 0
    directory_access_error_count: int = 0


class DirectoryScanReport(BaseModel):
    schema_version: str = "1.0.0"
    scanbox_version: str = __version__
    scan_id: str = Field(default_factory=lambda: uuid4().hex)
    mode: Literal["directory"] = "directory"
    profile: ScanProfile = ScanProfile.BALANCED
    disclaimer: str = DISCLAIMER_TEXT
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    target: DirectoryTargetInfo = Field(
        default_factory=lambda: DirectoryTargetInfo(
            original_path="",
            normalized_path="",
        )
    )
    target_count: int = 0
    scanned_count: int = 0
    error_count: int = 0
    overall_status: VerdictStatus = VerdictStatus.SCAN_ERROR
    issues: list[EngineIssue] = Field(default_factory=list)
    summary: DirectoryScanSummary = Field(default_factory=DirectoryScanSummary)
    accounting: DirectoryScanAccounting = Field(default_factory=DirectoryScanAccounting)
    results: list[DirectoryScanEntry] = Field(default_factory=list)


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


def build_directory_report_shell(original_path: str, profile: ScanProfile) -> DirectoryScanReport:
    return DirectoryScanReport(
        profile=profile,
        target=DirectoryTargetInfo(
            original_path=original_path,
            normalized_path=original_path,
            recursive=True,
        ),
    )
