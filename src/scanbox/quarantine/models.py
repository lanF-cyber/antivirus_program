from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuarantineRecordState(str, Enum):
    QUARANTINED = "quarantined"
    RESTORED = "restored"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class QuarantineIssue(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QuarantineEvent(BaseModel):
    timestamp: str
    action: str
    result: str
    details: dict[str, Any] = Field(default_factory=dict)


class QuarantineHashSummary(BaseModel):
    sha256: str | None = None


class QuarantineRecord(BaseModel):
    scan_id: str
    state: QuarantineRecordState
    original_path: str | None = None
    quarantine_path: str
    hashes: QuarantineHashSummary = Field(default_factory=QuarantineHashSummary)
    moved_at: str | None = None
    audit_path: str
    payload_exists: bool
    payload_path: Path
    reason: str | None = None
    state_changed_at: str | None = None
    restore_target_path: str | None = None
    delete_reason: str | None = None
    events: list[QuarantineEvent] = Field(default_factory=list)
    issues: list[QuarantineIssue] = Field(default_factory=list)

    def to_summary(self) -> "QuarantineRecordSummary":
        return QuarantineRecordSummary(
            scan_id=self.scan_id,
            state=self.state,
            original_path=self.original_path,
            quarantine_path=self.quarantine_path,
            hashes=self.hashes,
            moved_at=self.moved_at,
            audit_path=self.audit_path,
            payload_exists=self.payload_exists,
        )


class QuarantineRecordSummary(BaseModel):
    scan_id: str
    state: QuarantineRecordState
    original_path: str | None = None
    quarantine_path: str
    hashes: QuarantineHashSummary = Field(default_factory=QuarantineHashSummary)
    moved_at: str | None = None
    audit_path: str
    payload_exists: bool


class QuarantineListSummary(BaseModel):
    total: int = 0
    quarantined: int = 0
    restored: int = 0
    deleted: int = 0
    unknown: int = 0


class QuarantineListResponse(BaseModel):
    records: list[QuarantineRecordSummary] = Field(default_factory=list)
    issues: list[QuarantineIssue] = Field(default_factory=list)
    summary: QuarantineListSummary = Field(default_factory=QuarantineListSummary)


class QuarantineOperationResponse(BaseModel):
    operation: Literal["restore", "delete"]
    scan_id: str
    ok: bool
    state_before: QuarantineRecordState | None = None
    state_after: QuarantineRecordState | None = None
    target_path: str | None = None
    audit_path: str | None = None
    issues: list[QuarantineIssue] = Field(default_factory=list)
