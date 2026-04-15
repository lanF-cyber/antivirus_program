from __future__ import annotations

from scanbox.core.enums import EngineState, ScanProfile, VerdictStatus
from scanbox.core.models import Detection, ScanReport


class VerdictResolver:
    _PROFILE_THRESHOLDS = {
        ScanProfile.CONSERVATIVE: 4,
        ScanProfile.BALANCED: 3,
        ScanProfile.AGGRESSIVE: 2,
    }

    def resolve(self, report: ScanReport) -> VerdictStatus:
        if any(issue.code in {"input_error", "config_error", "scan_error"} for issue in report.issues):
            return VerdictStatus.SCAN_ERROR

        detections = [detection for engine in report.engines.values() for detection in engine.detections]
        if self._has_known_malicious(detections):
            return VerdictStatus.KNOWN_MALICIOUS
        if self._is_suspicious(report.profile, detections):
            return VerdictStatus.SUSPICIOUS

        applicable_results = [result for result in report.engines.values() if result.enabled and result.applicable]
        if any(result.state == EngineState.MISSING for result in applicable_results):
            return VerdictStatus.ENGINE_MISSING
        if any(result.state == EngineState.UNAVAILABLE for result in applicable_results):
            return VerdictStatus.ENGINE_UNAVAILABLE
        if any(result.state in {EngineState.ERROR, EngineState.TIMEOUT} for result in applicable_results):
            return VerdictStatus.PARTIAL_SCAN
        if applicable_results and all(result.state == EngineState.OK for result in applicable_results):
            return VerdictStatus.CLEAN_BY_KNOWN_CHECKS
        return VerdictStatus.SCAN_ERROR

    def _has_known_malicious(self, detections: list[Detection]) -> bool:
        return any(d.category == "malicious" and d.confidence == "high" for d in detections)

    def _score(self, detection: Detection) -> int:
        severity_weight = {"low": 1, "medium": 2, "high": 3}[detection.severity]
        confidence_weight = {"low": 0, "medium": 1, "high": 2}[detection.confidence]
        category_bonus = 1 if detection.category == "suspicious" else 2 if detection.category == "malicious" else 0
        return severity_weight + confidence_weight + category_bonus

    def _is_suspicious(self, profile: ScanProfile, detections: list[Detection]) -> bool:
        score = sum(self._score(detection) for detection in detections if detection.category != "informational")
        return score >= self._PROFILE_THRESHOLDS[profile]
