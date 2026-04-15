from __future__ import annotations

from enum import Enum


class VerdictStatus(str, Enum):
    KNOWN_MALICIOUS = "known_malicious"
    SUSPICIOUS = "suspicious"
    CLEAN_BY_KNOWN_CHECKS = "clean_by_known_checks"
    SCAN_ERROR = "scan_error"
    PARTIAL_SCAN = "partial_scan"
    ENGINE_MISSING = "engine_missing"
    ENGINE_UNAVAILABLE = "engine_unavailable"


class ScanProfile(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class EngineState(str, Enum):
    OK = "ok"
    SKIPPED_POLICY = "skipped_policy"
    SKIPPED_NOT_APPLICABLE = "skipped_not_applicable"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    ERROR = "error"
