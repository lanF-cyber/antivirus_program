from __future__ import annotations

import json
from pathlib import Path

from scanbox.config.models import AppConfig, AppSettings, EngineSettings, QuarantineSettings, TimeoutSettings
from scanbox.core.enums import VerdictStatus
from scanbox.core.models import QuarantineMode, ScanReport
from scanbox.quarantine.audit import derive_payload_path, read_audit_payload
from scanbox.quarantine.models import QuarantineRecordState
from scanbox.quarantine.records import list_quarantine_records, load_quarantine_record
from scanbox.quarantine.service import QuarantineService
from scanbox.targets.file_target import FileTarget


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


def make_report(status: VerdictStatus = VerdictStatus.KNOWN_MALICIOUS) -> ScanReport:
    report = ScanReport()
    report.overall_status = status
    report.hashes.sha256 = "a" * 64
    return report


def create_quarantined_record(tmp_path: Path, filename: str = "sample.bin") -> tuple[AppConfig, QuarantineService, ScanReport, Path]:
    config = make_config(tmp_path)
    service = QuarantineService(config)
    report = make_report()
    sample = tmp_path / filename
    sample.write_bytes(b"malicious")
    action = service.maybe_apply(
        report=report,
        target=FileTarget.from_path(sample),
        requested_mode=QuarantineMode.MOVE,
        dry_run=False,
    )
    assert action.performed is True
    return config, service, report, Path(action.audit_path)


def write_legacy_audit(audit_path: Path, *, scan_id: str = "legacy123", payload_exists: bool = True) -> Path:
    payload_path = derive_payload_path(audit_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    if payload_exists:
        payload_path.write_bytes(b"payload")
    audit_payload = {
        "scan_id": scan_id,
        "overall_status": "known_malicious",
        "original_path": str(payload_path.parent / "original.bin"),
        "quarantine_path": str(payload_path),
        "moved_at": "2026-04-15T00:00:00+00:00",
        "reason": "known_malicious",
        "hashes": {"sha256": "b" * 64},
    }
    audit_path.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    return audit_path


def test_quarantine_dry_run_for_known_malicious(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"malicious")
    config = make_config(tmp_path)

    report = ScanReport()
    report.overall_status = VerdictStatus.KNOWN_MALICIOUS

    action = QuarantineService(config).maybe_apply(
        report=report,
        target=FileTarget.from_path(sample),
        requested_mode=QuarantineMode.MOVE,
        dry_run=True,
    )

    assert action.performed is False
    assert action.reason == "dry_run_requested"
    assert sample.exists()


def test_quarantine_move_for_known_malicious_keeps_non_archive_reason_and_audit_shape(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    service = QuarantineService(config)
    report = make_report()
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"malicious")

    action = service.maybe_apply(
        report=report,
        target=FileTarget.from_path(sample),
        requested_mode=QuarantineMode.MOVE,
        dry_run=False,
    )

    assert action.performed is True
    assert action.reason == "moved_to_quarantine"
    assert action.archive_triggered is False
    assert action.archive_member_paths == []

    payload = read_audit_payload(Path(action.audit_path))
    assert payload["reason"] == "known_malicious"
    assert payload["archive_triggered"] is False
    assert payload["archive_member_paths"] == []


def test_new_audit_record_includes_state_and_events(tmp_path: Path) -> None:
    _, _, _, audit_path = create_quarantined_record(tmp_path)
    payload = read_audit_payload(audit_path)

    assert payload["state"] == "quarantined"
    assert payload["events"][0]["action"] == "quarantine_move"
    assert payload["events"][0]["result"] == "success"


def test_legacy_audit_with_payload_present_defaults_to_quarantined(tmp_path: Path) -> None:
    audit_path = write_legacy_audit(tmp_path / "quarantine" / "legacy.bin.audit.json", payload_exists=True)
    record = load_quarantine_record(audit_path)

    assert record.state == QuarantineRecordState.QUARANTINED
    assert not any(issue.code == "legacy_state_missing" for issue in record.issues)


def test_legacy_audit_with_missing_payload_becomes_unknown(tmp_path: Path) -> None:
    audit_path = write_legacy_audit(tmp_path / "quarantine" / "legacy.bin.audit.json", payload_exists=False)
    record = load_quarantine_record(audit_path)

    assert record.state == QuarantineRecordState.UNKNOWN
    assert any(issue.code == "legacy_state_missing" for issue in record.issues)


def test_list_empty_directory_returns_empty_summary(tmp_path: Path) -> None:
    response = QuarantineService(make_config(tmp_path)).list_records()

    assert response.records == []
    assert response.summary.total == 0


def test_list_records_returns_summary_without_events(tmp_path: Path) -> None:
    _, service, _, _ = create_quarantined_record(tmp_path)
    response = service.list_records()

    assert response.summary.total == 1
    record = response.records[0]
    assert set(record.model_dump().keys()) == {
        "scan_id",
        "state",
        "original_path",
        "quarantine_path",
        "hashes",
        "moved_at",
        "audit_path",
        "payload_exists",
    }


def test_list_records_filters_by_state(tmp_path: Path) -> None:
    _, service, report, audit_path = create_quarantined_record(tmp_path)
    restore_target = tmp_path / "restored.bin"
    restore_response = service.restore(report.scan_id, output_path=restore_target)
    assert restore_response.ok is True

    response = service.list_records(state_filter=QuarantineRecordState.RESTORED)

    assert response.summary.total == 1
    assert response.records[0].scan_id == report.scan_id
    assert response.records[0].state == QuarantineRecordState.RESTORED
    assert Path(audit_path).exists()


def test_restore_success_updates_state_and_appends_event(tmp_path: Path) -> None:
    _, service, report, audit_path = create_quarantined_record(tmp_path)
    payload_before = derive_payload_path(audit_path)
    restore_target = tmp_path / "restored.bin"

    response = service.restore(report.scan_id, output_path=restore_target)

    assert response.ok is True
    assert response.state_before == QuarantineRecordState.QUARANTINED
    assert response.state_after == QuarantineRecordState.RESTORED
    assert restore_target.exists()
    assert not payload_before.exists()

    payload = read_audit_payload(audit_path)
    assert payload["state"] == "restored"
    assert payload["restore_target_path"] == str(restore_target)
    assert [event["action"] for event in payload["events"]] == ["quarantine_move", "restore"]


def test_restore_returns_not_found_for_unknown_scan_id(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    response = QuarantineService(config).restore("missing-scan-id")

    assert response.ok is False
    assert any(issue.code == "scan_id_not_found" for issue in response.issues)


def test_restore_rejects_when_state_is_not_quarantined(tmp_path: Path) -> None:
    _, service, report, _ = create_quarantined_record(tmp_path)
    restore_target = tmp_path / "restored.bin"
    assert service.restore(report.scan_id, output_path=restore_target).ok is True

    second_response = service.restore(report.scan_id, output_path=tmp_path / "restored-again.bin")

    assert second_response.ok is False
    assert any(issue.code == "state_not_quarantined" for issue in second_response.issues)


def test_restore_rejects_missing_payload(tmp_path: Path) -> None:
    _, service, report, audit_path = create_quarantined_record(tmp_path)
    derive_payload_path(audit_path).unlink()

    response = service.restore(report.scan_id, output_path=tmp_path / "restored.bin")

    assert response.ok is False
    assert any(issue.code == "payload_missing" for issue in response.issues)


def test_restore_rejects_existing_target(tmp_path: Path) -> None:
    _, service, report, _ = create_quarantined_record(tmp_path)
    restore_target = tmp_path / "restored.bin"
    restore_target.write_bytes(b"existing")

    response = service.restore(report.scan_id, output_path=restore_target)

    assert response.ok is False
    issue_codes = {issue.code for issue in response.issues}
    assert "target_already_exists" in issue_codes
    assert "restore_conflict" in issue_codes


def test_restore_rejects_missing_parent_directory(tmp_path: Path) -> None:
    _, service, report, _ = create_quarantined_record(tmp_path)
    response = service.restore(report.scan_id, output_path=Path("missing-parent") / "restored.bin")

    assert response.ok is False
    assert any(issue.code == "restore_parent_missing" for issue in response.issues)


def test_delete_requires_explicit_confirmation(tmp_path: Path) -> None:
    _, service, report, _ = create_quarantined_record(tmp_path)
    response = service.delete(report.scan_id, confirmed=False)

    assert response.ok is False
    assert any(issue.code == "confirmation_required" for issue in response.issues)


def test_delete_success_keeps_audit_and_appends_event(tmp_path: Path) -> None:
    _, service, report, audit_path = create_quarantined_record(tmp_path)
    payload_path = derive_payload_path(audit_path)

    response = service.delete(report.scan_id, confirmed=True)

    assert response.ok is True
    assert response.state_after == QuarantineRecordState.DELETED
    assert not payload_path.exists()
    assert audit_path.exists()

    payload = read_audit_payload(audit_path)
    assert payload["state"] == "deleted"
    assert payload["delete_reason"] == "user_confirmed"
    assert [event["action"] for event in payload["events"]] == ["quarantine_move", "delete"]


def test_delete_rejects_unknown_legacy_record(tmp_path: Path) -> None:
    audit_path = write_legacy_audit(tmp_path / "quarantine" / "legacy.bin.audit.json", payload_exists=False)
    response = QuarantineService(make_config(tmp_path)).delete("legacy123", confirmed=True)

    assert audit_path.exists()
    assert response.ok is False
    assert response.state_before == QuarantineRecordState.UNKNOWN
    assert any(issue.code == "legacy_state_missing" for issue in response.issues)
    assert any(issue.code == "state_not_quarantined" for issue in response.issues)


def test_events_history_is_append_only_across_restore_and_requarantine(tmp_path: Path) -> None:
    config, service, report, audit_path = create_quarantined_record(tmp_path)
    restore_target = tmp_path / "restored.bin"

    assert service.restore(report.scan_id, output_path=restore_target).ok is True
    restored_payload = read_audit_payload(audit_path)
    assert [event["action"] for event in restored_payload["events"]] == ["quarantine_move", "restore"]

    second_report = make_report()
    second_action = service.maybe_apply(
        report=second_report,
        target=FileTarget.from_path(restore_target),
        requested_mode=QuarantineMode.MOVE,
        dry_run=False,
    )
    second_audit_path = Path(second_action.audit_path)
    second_payload = read_audit_payload(second_audit_path)
    assert [event["action"] for event in second_payload["events"]] == ["quarantine_move"]

    delete_response = service.delete(second_report.scan_id, confirmed=True)
    assert delete_response.ok is True
    deleted_payload = read_audit_payload(second_audit_path)
    assert [event["action"] for event in deleted_payload["events"]] == ["quarantine_move", "delete"]
    assert config.quarantine.directory.exists()
