from scanbox.core.enums import EngineState, ScanProfile, VerdictStatus
from scanbox.core.models import Detection, EngineScanResult, ScanReport
from scanbox.pipeline.verdicts import VerdictResolver


def test_known_malicious_beats_missing_engine() -> None:
    report = ScanReport(profile=ScanProfile.BALANCED)
    report.engines = {
        "clamav": EngineScanResult(
            engine="clamav",
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            detections=[
                Detection(
                    source="clamav",
                    rule_id="Eicar-Test-Signature",
                    severity="high",
                    confidence="high",
                    category="malicious",
                )
            ],
        ),
        "capa": EngineScanResult(
            engine="capa",
            enabled=True,
            applicable=True,
            state=EngineState.MISSING,
        ),
    }

    verdict = VerdictResolver().resolve(report)
    assert verdict == VerdictStatus.KNOWN_MALICIOUS


def test_partial_scan_when_engine_times_out_and_no_hits() -> None:
    report = ScanReport(profile=ScanProfile.BALANCED)
    report.engines = {
        "clamav": EngineScanResult(engine="clamav", enabled=True, applicable=True, state=EngineState.OK),
        "yara": EngineScanResult(engine="yara", enabled=True, applicable=True, state=EngineState.TIMEOUT),
    }

    verdict = VerdictResolver().resolve(report)
    assert verdict == VerdictStatus.PARTIAL_SCAN
