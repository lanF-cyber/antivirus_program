from __future__ import annotations

from io import BytesIO
import tarfile
import zipfile
from pathlib import Path

from scanbox.config.models import AppConfig, DirectoryScanSettings, QuarantineSettings
from scanbox.core.enums import EngineState, VerdictStatus
from scanbox.core.models import Detection, EngineScanResult, QuarantineMode, ScanReport
from scanbox.pipeline.orchestrator import ScanOrchestrator
from scanbox.quarantine.audit import read_audit_payload


class FakeArchiveAdapter:
    name = "yara"

    def is_enabled(self, settings: AppConfig) -> bool:
        return True

    def discover(self, settings: AppConfig):
        return None

    def supports(self, target, report: ScanReport) -> bool:
        return True

    def scan(
        self,
        target,
        report: ScanReport,
        settings: AppConfig,
        timeout_seconds: int,
    ) -> EngineScanResult:
        detections: list[Detection] = []
        data = target.path.read_bytes()
        if b"EICAR" in data or target.path.name == "eicar.com":
            detections.append(
                Detection(
                    source="fake",
                    rule_id="fake-eicar",
                    severity="high",
                    confidence="high",
                    category="malicious",
                )
            )
        return EngineScanResult(
            engine=self.name,
            enabled=True,
            applicable=True,
            state=EngineState.OK,
            detections=detections,
        )


def _build_config(tmp_path: Path, *, directory_scan: DirectoryScanSettings | None = None) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "scanbox.toml",
        directory_scan=directory_scan or DirectoryScanSettings(),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


def _write_zip(zip_path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _tar_write_mode(archive_path: Path) -> str:
    lower_name = archive_path.name.lower()
    if lower_name.endswith((".tar.gz", ".tgz")):
        return "w:gz"
    if lower_name.endswith((".tar.bz2", ".tbz2")):
        return "w:bz2"
    if lower_name.endswith((".tar.xz", ".txz")):
        return "w:xz"
    return "w"


def _write_tar(archive_path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(archive_path, _tar_write_mode(archive_path)) as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))


def _build_zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()
def _mark_zip_entry_encrypted(zip_path: Path, entry_name: str) -> None:
    data = bytearray(zip_path.read_bytes())
    with zipfile.ZipFile(zip_path) as archive:
        info = archive.getinfo(entry_name)

    local_flags_offset = info.header_offset + 6
    local_flags = int.from_bytes(data[local_flags_offset : local_flags_offset + 2], "little")
    data[local_flags_offset : local_flags_offset + 2] = (local_flags | 0x1).to_bytes(2, "little")

    offset = 0
    while offset < len(data):
        signature_index = data.find(b"PK\x01\x02", offset)
        if signature_index == -1:
            break
        name_length = int.from_bytes(data[signature_index + 28 : signature_index + 30], "little")
        extra_length = int.from_bytes(data[signature_index + 30 : signature_index + 32], "little")
        comment_length = int.from_bytes(data[signature_index + 32 : signature_index + 34], "little")
        local_header_offset = int.from_bytes(data[signature_index + 42 : signature_index + 46], "little")
        name_bytes = bytes(data[signature_index + 46 : signature_index + 46 + name_length])
        if local_header_offset == info.header_offset and name_bytes.decode("utf-8") == entry_name:
            central_flags_offset = signature_index + 8
            central_flags = int.from_bytes(data[central_flags_offset : central_flags_offset + 2], "little")
            data[central_flags_offset : central_flags_offset + 2] = (central_flags | 0x1).to_bytes(2, "little")
            break
        offset = signature_index + 46 + name_length + extra_length + comment_length

    zip_path.write_bytes(bytes(data))


def test_direct_zip_input_with_one_clean_member(tmp_path: Path) -> None:
    zip_path = tmp_path / "clean.zip"
    _write_zip(zip_path, {"hello.txt": b"hello world"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.CLEAN_BY_KNOWN_CHECKS
    assert report.archive_expansion is not None
    assert report.archive_expansion.member_count == 1
    assert report.archive_expansion.scanned_member_count == 1
    child = report.archive_expansion.results[0].report
    assert child.target.archive_path == str(zip_path.resolve())
    assert child.target.archive_member_path == "hello.txt"
    assert child.target.archive_depth == 1
    assert report.summary["archive_member_count"] == 1
    assert report.summary["archive_scanned_member_count"] == 1


def test_direct_tar_input_with_one_clean_member(tmp_path: Path) -> None:
    tar_path = tmp_path / "clean.tar"
    _write_tar(tar_path, {"hello.txt": b"hello world"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(tar_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.CLEAN_BY_KNOWN_CHECKS
    assert report.archive_expansion is not None
    assert report.archive_expansion.archive_kind == "tar"
    assert report.archive_expansion.member_count == 1
    assert report.archive_expansion.scanned_member_count == 1
    child = report.archive_expansion.results[0].report
    assert child.target.archive_path == str(tar_path.resolve())
    assert child.target.archive_member_path == "hello.txt"
    assert child.target.archive_depth == 1


def test_direct_zip_input_with_one_detectable_member(tmp_path: Path) -> None:
    zip_path = tmp_path / "detectable.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.archive_expansion is not None
    child = report.archive_expansion.results[0].report
    assert child.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert child.target.archive_member_path == "nested/eicar.com"
    assert report.summary["known_malicious_hits"] == 1
    assert report.quarantine.performed is False


def test_direct_tar_gz_input_with_one_detectable_member(tmp_path: Path) -> None:
    tar_path = tmp_path / "detectable.tar.gz"
    _write_tar(tar_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(tar_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.archive_expansion is not None
    assert report.archive_expansion.archive_kind == "tar"
    child = report.archive_expansion.results[0].report
    assert child.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert child.target.archive_member_path == "nested/eicar.com"
    assert report.quarantine.performed is False


def test_direct_zip_with_malicious_member_triggers_container_quarantine(tmp_path: Path) -> None:
    zip_path = tmp_path / "quarantine-me.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.quarantine.performed is True
    assert report.quarantine.reason == "archive_member_known_malicious"
    assert report.quarantine.archive_triggered is True
    assert report.quarantine.archive_member_paths == ["nested/eicar.com"]
    assert report.quarantine.original_path == str(zip_path.resolve())
    assert report.quarantine.quarantine_path is not None
    assert not zip_path.exists()
    assert Path(report.quarantine.quarantine_path).exists()

    child = report.archive_expansion.results[0].report
    assert child.quarantine.performed is False
    assert child.quarantine.audit_path is None
    assert child.quarantine.quarantine_path is None


def test_direct_zip_with_clean_members_does_not_escalate_quarantine(tmp_path: Path) -> None:
    zip_path = tmp_path / "clean.zip"
    _write_zip(zip_path, {"nested/hello.txt": b"hello world"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.CLEAN_BY_KNOWN_CHECKS
    assert report.quarantine.performed is False
    assert report.quarantine.reason == "verdict_not_eligible_for_quarantine"
    assert report.quarantine.archive_triggered is False
    assert report.quarantine.archive_member_paths == []
    assert zip_path.exists()


def test_directory_scan_finds_zip_and_reports_member_finding(tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    root.mkdir()
    zip_path = root / "sample.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_directory(root, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.target_count == 1
    assert report.scanned_count == 1
    assert report.results[0].relative_path == "sample.zip"
    assert report.results[0].report.archive_expansion is not None
    child = report.results[0].report.archive_expansion.results[0].report
    assert child.target.archive_path == str(zip_path.resolve())
    assert child.target.archive_member_path == "nested/eicar.com"
    assert child.overall_status == VerdictStatus.KNOWN_MALICIOUS


def test_directory_scan_finds_tar_family_archive_and_reports_member_finding(tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    root.mkdir()
    tar_path = root / "sample.tgz"
    _write_tar(tar_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_directory(root, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.target_count == 1
    assert report.scanned_count == 1
    assert report.results[0].relative_path == "sample.tgz"
    assert report.results[0].report.archive_expansion is not None
    assert report.results[0].report.archive_expansion.archive_kind == "tar"
    child = report.results[0].report.archive_expansion.results[0].report
    assert child.target.archive_path == str(tar_path.resolve())
    assert child.target.archive_member_path == "nested/eicar.com"
    assert child.overall_status == VerdictStatus.KNOWN_MALICIOUS


def test_directory_scan_zip_with_malicious_member_triggers_container_quarantine(tmp_path: Path) -> None:
    root = tmp_path / "scan-root"
    root.mkdir()
    zip_path = root / "sample.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_directory(root, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    entry_report = report.results[0].report
    assert entry_report.quarantine.performed is True
    assert entry_report.quarantine.reason == "archive_member_known_malicious"
    assert entry_report.quarantine.archive_triggered is True
    assert entry_report.quarantine.archive_member_paths == ["nested/eicar.com"]
    assert entry_report.quarantine.original_path == str(zip_path.resolve())
    assert not zip_path.exists()
    assert Path(entry_report.quarantine.quarantine_path).exists()


def test_corrupt_zip_returns_structured_issue(tmp_path: Path) -> None:
    zip_path = tmp_path / "corrupt.zip"
    zip_path.write_bytes(b"PK\x03\x04not-a-valid-zip")
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.SCAN_ERROR
    assert any(issue.code == "archive_corrupt" for issue in report.issues)


def test_corrupt_tar_family_archive_returns_structured_issue(tmp_path: Path) -> None:
    tar_path = tmp_path / "corrupt.tar.gz"
    tar_path.write_bytes(b"not-a-valid-tar")
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(tar_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.SCAN_ERROR
    assert any(issue.code == "archive_corrupt" for issue in report.issues)


def test_password_protected_zip_returns_structured_issue(tmp_path: Path) -> None:
    zip_path = tmp_path / "encrypted-flag.zip"
    _write_zip(zip_path, {"secret.txt": b"hidden"})
    _mark_zip_entry_encrypted(zip_path, "secret.txt")
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.PARTIAL_SCAN
    assert any(issue.code == "archive_password_protected" for issue in report.issues)
    assert report.archive_expansion is not None
    assert report.archive_expansion.scanned_member_count == 0


def test_archive_expansion_limit_hit_returns_structured_issue(tmp_path: Path) -> None:
    zip_path = tmp_path / "limit.zip"
    _write_zip(
        zip_path,
        {
            "one.txt": b"one",
            "two.txt": b"two",
        },
    )
    settings = DirectoryScanSettings(max_archive_member_count=1)
    orchestrator = ScanOrchestrator(_build_config(tmp_path, directory_scan=settings), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.PARTIAL_SCAN
    assert any(issue.code == "archive_member_limit_exceeded" for issue in report.issues)
    assert report.archive_expansion is not None
    assert report.archive_expansion.member_count == 2
    assert report.archive_expansion.scanned_member_count == 1


def test_tar_archive_member_limit_hit_returns_structured_issue(tmp_path: Path) -> None:
    tar_path = tmp_path / "limit.tar"
    _write_tar(
        tar_path,
        {
            "one.txt": b"one",
            "two.txt": b"two",
        },
    )
    settings = DirectoryScanSettings(max_archive_member_count=1)
    orchestrator = ScanOrchestrator(_build_config(tmp_path, directory_scan=settings), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(tar_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.PARTIAL_SCAN
    assert any(issue.code == "archive_member_limit_exceeded" for issue in report.issues)
    assert report.archive_expansion is not None
    assert report.archive_expansion.archive_kind == "tar"
    assert report.archive_expansion.member_count == 2
    assert report.archive_expansion.scanned_member_count == 1


def test_nested_zip_depth_limit_returns_structured_issue(tmp_path: Path) -> None:
    inner_zip_bytes = _build_zip_bytes({"eicar.com": b"EICAR test signature"})
    outer_zip = tmp_path / "outer.zip"
    _write_zip(outer_zip, {"nested.zip": inner_zip_bytes})
    settings = DirectoryScanSettings(max_archive_expansion_depth=1)
    orchestrator = ScanOrchestrator(_build_config(tmp_path, directory_scan=settings), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(outer_zip, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.PARTIAL_SCAN
    assert report.archive_expansion is not None
    nested_report = report.archive_expansion.results[0].report
    assert nested_report.target.archive_member_path == "nested.zip"
    assert nested_report.archive_expansion is None
    assert any(issue.code == "archive_depth_limit_exceeded" for issue in nested_report.issues)


def test_nested_tar_zip_depth_limit_returns_structured_issue(tmp_path: Path) -> None:
    inner_zip_bytes = _build_zip_bytes({"eicar.com": b"EICAR test signature"})
    outer_tar = tmp_path / "outer.tar"
    _write_tar(outer_tar, {"nested.zip": inner_zip_bytes})
    settings = DirectoryScanSettings(max_archive_expansion_depth=1)
    orchestrator = ScanOrchestrator(_build_config(tmp_path, directory_scan=settings), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(outer_tar, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.PARTIAL_SCAN
    assert report.archive_expansion is not None
    nested_report = report.archive_expansion.results[0].report
    assert nested_report.target.archive_member_path == "nested.zip"
    assert nested_report.archive_expansion is None
    assert any(issue.code == "archive_depth_limit_exceeded" for issue in nested_report.issues)


def test_extracted_member_is_not_quarantined(tmp_path: Path) -> None:
    zip_path = tmp_path / "container.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    quarantine_dir = tmp_path / "quarantine"
    payload_names = sorted(path.name for path in quarantine_dir.iterdir() if path.is_file() and not path.name.endswith(".audit.json"))
    assert len(payload_names) == 1
    assert payload_names[0].endswith("_container.zip")
    child = report.archive_expansion.results[0].report
    assert child.quarantine.performed is False
    assert child.quarantine.reason is None


def test_extracted_tar_member_is_not_quarantined_directly(tmp_path: Path) -> None:
    tar_path = tmp_path / "container.tar.gz"
    _write_tar(tar_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(tar_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.quarantine.performed is False
    assert report.quarantine.reason == "verdict_not_eligible_for_quarantine"
    quarantine_dir = tmp_path / "quarantine"
    assert not quarantine_dir.exists()
    child = report.archive_expansion.results[0].report
    assert child.quarantine.performed is False
    assert child.quarantine.reason is None


def test_archive_member_quarantine_escalation_dry_run_sets_reason_without_move(tmp_path: Path) -> None:
    zip_path = tmp_path / "dry-run.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=True)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.quarantine.performed is False
    assert report.quarantine.reason == "dry_run_requested_archive_member_known_malicious"
    assert report.quarantine.archive_triggered is True
    assert report.quarantine.archive_member_paths == ["nested/eicar.com"]
    assert report.quarantine.audit_path is None
    assert zip_path.exists()


def test_archive_member_quarantine_escalation_ask_sets_reason_without_move(tmp_path: Path) -> None:
    zip_path = tmp_path / "ask.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.ASK, dry_run_quarantine=False)

    assert report.overall_status == VerdictStatus.KNOWN_MALICIOUS
    assert report.quarantine.performed is False
    assert report.quarantine.reason == "user_confirmation_required_archive_member_known_malicious"
    assert report.quarantine.archive_triggered is True
    assert report.quarantine.archive_member_paths == ["nested/eicar.com"]
    assert report.quarantine.audit_path is None
    assert zip_path.exists()


def test_archive_triggered_quarantine_audit_records_trigger_context(tmp_path: Path) -> None:
    zip_path = tmp_path / "audit.zip"
    _write_zip(zip_path, {"nested/eicar.com": b"EICAR test signature"})
    orchestrator = ScanOrchestrator(_build_config(tmp_path), adapters=[FakeArchiveAdapter()])

    report = orchestrator.scan_file(zip_path, quarantine_mode=QuarantineMode.MOVE, dry_run_quarantine=False)

    audit_payload = read_audit_payload(Path(report.quarantine.audit_path))
    assert audit_payload["reason"] == "archive_member_known_malicious"
    assert audit_payload["archive_triggered"] is True
    assert audit_payload["archive_member_paths"] == ["nested/eicar.com"]
    assert audit_payload["original_path"] == str(zip_path.resolve())
    assert audit_payload["events"][0]["details"]["archive_triggered"] is True
    assert audit_payload["events"][0]["details"]["archive_member_paths"] == ["nested/eicar.com"]
