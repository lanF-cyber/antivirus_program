from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile
import zipfile

import pytest

from scanbox.core.enums import ScanProfile, VerdictStatus
from scanbox.core.models import QuarantineAction, ScanReport, TargetInfo
from scanbox.pipeline import archive_expansion
from scanbox.pipeline.archive_expansion import ArchiveExpansionBudget, expand_tar_archive, expand_zip_archive


def _make_report(path: Path) -> ScanReport:
    return ScanReport(
        profile=ScanProfile.BALANCED,
        overall_status=VerdictStatus.CLEAN_BY_KNOWN_CHECKS,
        target=TargetInfo(
            original_path=str(path),
            normalized_path=str(path),
            size=path.stat().st_size if path.exists() else 0,
            detected_type="generic_file",
        ),
        quarantine=QuarantineAction(requested_mode="ask"),
        summary={
            "engine_count": 0,
            "detections": 0,
            "known_malicious_hits": 0,
            "suspicious_hits": 0,
            "archive_member_count": 0,
            "archive_scanned_member_count": 0,
            "archive_total_extracted_bytes": 0,
            "status": VerdictStatus.CLEAN_BY_KNOWN_CHECKS.value,
        },
    )


def _write_zip(zip_path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _write_tar(
    tar_path: Path,
    members: dict[str, bytes],
    *,
    symlinks: dict[str, str] | None = None,
    hardlinks: dict[str, str] | None = None,
) -> None:
    with tarfile.open(tar_path, "w") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
        for name, target in (symlinks or {}).items():
            info = tarfile.TarInfo(name=name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            archive.addfile(info)
        for name, target in (hardlinks or {}).items():
            info = tarfile.TarInfo(name=name)
            info.type = tarfile.LNKTYPE
            info.linkname = target
            archive.addfile(info)


def test_expand_zip_archive_skips_unsupported_member_paths(tmp_path: Path) -> None:
    zip_path = tmp_path / "unsupported.zip"
    _write_zip(
        zip_path,
        {
            "../escape.txt": b"bad",
            "safe.txt": b"good",
        },
    )
    budget = ArchiveExpansionBudget(max_member_count=10, max_total_bytes=1024)

    report, issues = expand_zip_archive(
        zip_path,
        expansion_depth=0,
        max_expansion_depth=1,
        budget=budget,
        scan_member=lambda extracted_path, member_path: _make_report(extracted_path),
    )

    assert report.member_count == 2
    assert report.scanned_member_count == 1
    assert [result.member_path for result in report.results] == ["safe.txt"]
    assert any(issue.code == "archive_member_unsupported" for issue in issues)


def test_expand_zip_archive_reports_byte_budget_exceeded(tmp_path: Path) -> None:
    zip_path = tmp_path / "byte-budget.zip"
    _write_zip(zip_path, {"big.bin": b"12345", "other.bin": b"67890"})
    budget = ArchiveExpansionBudget(max_member_count=10, max_total_bytes=5)

    report, issues = expand_zip_archive(
        zip_path,
        expansion_depth=0,
        max_expansion_depth=1,
        budget=budget,
        scan_member=lambda extracted_path, member_path: _make_report(extracted_path),
    )

    assert report.scanned_member_count == 1
    assert any(issue.code == "archive_byte_budget_exceeded" for issue in issues)


def test_expand_zip_archive_cleans_up_temp_extraction_directory(tmp_path: Path, monkeypatch) -> None:
    zip_path = tmp_path / "cleanup.zip"
    _write_zip(zip_path, {"hello.txt": b"hello"})
    budget = ArchiveExpansionBudget(max_member_count=10, max_total_bytes=1024)
    created_paths: list[Path] = []

    original_factory = archive_expansion.tempfile.TemporaryDirectory

    class TrackingTemporaryDirectory:
        def __init__(self, *args, **kwargs) -> None:
            self._inner = original_factory(*args, **kwargs)

        def __enter__(self) -> str:
            path = Path(self._inner.__enter__())
            created_paths.append(path)
            return str(path)

        def __exit__(self, exc_type, exc, tb) -> bool | None:
            return self._inner.__exit__(exc_type, exc, tb)

    monkeypatch.setattr(archive_expansion.tempfile, "TemporaryDirectory", TrackingTemporaryDirectory)

    with pytest.raises(RuntimeError, match="boom"):
        expand_zip_archive(
            zip_path,
            expansion_depth=0,
            max_expansion_depth=1,
            budget=budget,
            scan_member=lambda extracted_path, member_path: (_ for _ in ()).throw(RuntimeError("boom")),
        )

    assert created_paths
    assert all(not path.exists() for path in created_paths)


def test_expand_tar_archive_skips_unsupported_member_forms(tmp_path: Path) -> None:
    tar_path = tmp_path / "unsupported.tar"
    _write_tar(
        tar_path,
        {"safe.txt": b"good"},
        symlinks={"symlink.txt": "safe.txt"},
        hardlinks={"hardlink.txt": "safe.txt"},
    )
    budget = ArchiveExpansionBudget(max_member_count=10, max_total_bytes=1024)

    report, issues = expand_tar_archive(
        tar_path,
        expansion_depth=0,
        max_expansion_depth=1,
        budget=budget,
        scan_member=lambda extracted_path, member_path: _make_report(extracted_path),
    )

    assert report.archive_kind == "tar"
    assert report.member_count == 3
    assert report.scanned_member_count == 1
    assert [result.member_path for result in report.results] == ["safe.txt"]
    unsupported_issues = [issue for issue in issues if issue.code == "archive_member_unsupported"]
    assert len(unsupported_issues) == 2


def test_expand_tar_archive_cleans_up_temp_extraction_directory(tmp_path: Path, monkeypatch) -> None:
    tar_path = tmp_path / "cleanup.tar"
    _write_tar(tar_path, {"hello.txt": b"hello"})
    budget = ArchiveExpansionBudget(max_member_count=10, max_total_bytes=1024)
    created_paths: list[Path] = []

    original_factory = archive_expansion.tempfile.TemporaryDirectory

    class TrackingTemporaryDirectory:
        def __init__(self, *args, **kwargs) -> None:
            self._inner = original_factory(*args, **kwargs)

        def __enter__(self) -> str:
            path = Path(self._inner.__enter__())
            created_paths.append(path)
            return str(path)

        def __exit__(self, exc_type, exc, tb) -> bool | None:
            return self._inner.__exit__(exc_type, exc, tb)

    monkeypatch.setattr(archive_expansion.tempfile, "TemporaryDirectory", TrackingTemporaryDirectory)

    with pytest.raises(RuntimeError, match="boom"):
        expand_tar_archive(
            tar_path,
            expansion_depth=0,
            max_expansion_depth=1,
            budget=budget,
            scan_member=lambda extracted_path, member_path: (_ for _ in ()).throw(RuntimeError("boom")),
        )

    assert created_paths
    assert all(not path.exists() for path in created_paths)
