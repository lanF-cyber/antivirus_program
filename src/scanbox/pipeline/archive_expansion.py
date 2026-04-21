from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Callable
import zipfile

from scanbox.core import issue_text
from scanbox.core.models import ArchiveExpansionReport, ArchiveMemberResult, EngineIssue, ScanReport


@dataclass(slots=True)
class ArchiveExpansionBudget:
    max_member_count: int
    max_total_bytes: int
    extracted_member_count: int = 0
    extracted_total_bytes: int = 0


def expand_zip_archive(
    archive_path: Path,
    *,
    expansion_depth: int,
    max_expansion_depth: int,
    budget: ArchiveExpansionBudget,
    scan_member: Callable[[Path, str], ScanReport],
) -> tuple[ArchiveExpansionReport, list[EngineIssue]]:
    report = ArchiveExpansionReport(
        expansion_depth=expansion_depth,
        max_expansion_depth=max_expansion_depth,
    )
    issues: list[EngineIssue] = []

    try:
        with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory(prefix="scanbox-archive-") as temp_root:
            member_infos = sorted(
                (info for info in archive.infolist() if not info.is_dir()),
                key=lambda info: _normalize_member_name_for_sort(info.filename),
            )
            report.member_count = len(member_infos)
            temp_root_path = Path(temp_root)
            member_limit_hit = False
            byte_limit_hit = False

            for info in member_infos:
                member_path = _normalize_member_path(info.filename)
                if member_path is None or _is_unsupported_member_form(info):
                    issues.append(
                        _build_archive_issue(
                            code="archive_member_unsupported",
                            archive_path=archive_path,
                            member_path=info.filename,
                        )
                    )
                    continue

                if info.flag_bits & 0x1:
                    issues.append(
                        _build_archive_issue(
                            code="archive_password_protected",
                            archive_path=archive_path,
                            member_path=member_path,
                        )
                    )
                    continue

                if budget.extracted_member_count >= budget.max_member_count:
                    member_limit_hit = True
                    break

                if budget.extracted_total_bytes + info.file_size > budget.max_total_bytes:
                    byte_limit_hit = True
                    break

                extracted_path = temp_root_path / member_path
                extracted_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    with archive.open(info, "r") as source, extracted_path.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                except RuntimeError as exc:
                    if info.flag_bits & 0x1:
                        issues.append(
                            _build_archive_issue(
                                code="archive_password_protected",
                                archive_path=archive_path,
                                member_path=member_path,
                                clue=str(exc),
                            )
                        )
                        continue
                    issues.append(
                        _build_archive_issue(
                            code="archive_corrupt",
                            archive_path=archive_path,
                            member_path=member_path,
                            clue=str(exc),
                        )
                    )
                    break
                except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
                    issues.append(
                        _build_archive_issue(
                            code="archive_corrupt",
                            archive_path=archive_path,
                            member_path=member_path,
                            clue=str(exc),
                        )
                    )
                    break

                budget.extracted_member_count += 1
                budget.extracted_total_bytes += info.file_size
                report.total_extracted_bytes += info.file_size

                member_report = scan_member(extracted_path, member_path)
                report.results.append(
                    ArchiveMemberResult(
                        member_path=member_path,
                        report=member_report,
                    )
                )
                report.scanned_member_count += 1

            if member_limit_hit:
                issues.append(
                    _build_archive_issue(
                        code="archive_member_limit_exceeded",
                        archive_path=archive_path,
                        details={"max_archive_member_count": budget.max_member_count},
                    )
                )
            if byte_limit_hit:
                issues.append(
                    _build_archive_issue(
                        code="archive_byte_budget_exceeded",
                        archive_path=archive_path,
                        details={"max_archive_total_bytes": budget.max_total_bytes},
                    )
                )
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        issues.append(
            _build_archive_issue(
                code="archive_corrupt",
                archive_path=archive_path,
                clue=str(exc),
            )
        )

    return report, issues


def _normalize_member_name_for_sort(filename: str) -> str:
    return filename.replace("\\", "/")


def _normalize_member_path(filename: str) -> str | None:
    candidate = filename.replace("\\", "/")
    if not candidate:
        return None

    path = PurePosixPath(candidate)
    if path.is_absolute():
        return None
    if path.parts and path.parts[0].endswith(":"):
        return None

    if any(part in {"", ".", ".."} for part in path.parts):
        return None

    normalized = path.as_posix()
    if normalized.startswith("../") or "/../" in normalized:
        return None

    return normalized


def _is_unsupported_member_form(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    if mode == 0:
        return False
    file_type_bits = stat.S_IFMT(mode)
    if file_type_bits == 0:
        return False
    if stat.S_ISLNK(mode):
        return True
    return not stat.S_ISREG(mode)


def _build_archive_issue(
    *,
    code: str,
    archive_path: Path,
    member_path: str | None = None,
    clue: str | None = None,
    details: dict[str, object] | None = None,
) -> EngineIssue:
    issue_details: dict[str, object] = {"archive_path": str(archive_path)}
    if member_path is not None:
        issue_details["member_path"] = member_path
    if details:
        issue_details.update(details)

    return EngineIssue(
        engine="scanbox",
        code=code,
        message=issue_text.scanbox_issue(code, clue=clue),
        details=issue_details,
    )
