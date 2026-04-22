from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
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


@dataclass(slots=True)
class _ArchiveMemberSpec:
    raw_name: str
    size: int
    member_path: str | None
    unsupported: bool = False
    password_protected: bool = False


def expand_zip_archive(
    archive_path: Path,
    *,
    expansion_depth: int,
    max_expansion_depth: int,
    budget: ArchiveExpansionBudget,
    scan_member: Callable[[Path, str], ScanReport],
) -> tuple[ArchiveExpansionReport, list[EngineIssue]]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            member_specs = [
                _ArchiveMemberSpec(
                    raw_name=info.filename,
                    size=info.file_size,
                    member_path=_normalize_member_path(info.filename),
                    unsupported=_is_unsupported_zip_member_form(info),
                    password_protected=bool(info.flag_bits & 0x1),
                )
                for info in archive.infolist()
                if not info.is_dir()
            ]
            return _expand_archive_members(
                archive_kind="zip",
                archive_path=archive_path,
                expansion_depth=expansion_depth,
                max_expansion_depth=max_expansion_depth,
                budget=budget,
                member_specs=member_specs,
                scan_member=scan_member,
                extract_member=lambda member_spec, extracted_path: _extract_zip_member(archive, member_spec, extracted_path),
                corrupt_exceptions=(zipfile.BadZipFile, zipfile.LargeZipFile),
            )
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        return _build_archive_corrupt_result(
            archive_kind="zip",
            archive_path=archive_path,
            expansion_depth=expansion_depth,
            max_expansion_depth=max_expansion_depth,
            clue=str(exc),
        )


def expand_tar_archive(
    archive_path: Path,
    *,
    expansion_depth: int,
    max_expansion_depth: int,
    budget: ArchiveExpansionBudget,
    scan_member: Callable[[Path, str], ScanReport],
) -> tuple[ArchiveExpansionReport, list[EngineIssue]]:
    try:
        with tarfile.open(archive_path, mode="r:*") as archive:
            member_specs = [
                _ArchiveMemberSpec(
                    raw_name=member.name,
                    size=max(member.size, 0),
                    member_path=_normalize_member_path(member.name),
                    unsupported=_is_unsupported_tar_member_form(member),
                )
                for member in archive.getmembers()
                if not member.isdir()
            ]
            return _expand_archive_members(
                archive_kind="tar",
                archive_path=archive_path,
                expansion_depth=expansion_depth,
                max_expansion_depth=max_expansion_depth,
                budget=budget,
                member_specs=member_specs,
                scan_member=scan_member,
                extract_member=lambda member_spec, extracted_path: _extract_tar_member(archive, member_spec, extracted_path),
                corrupt_exceptions=(tarfile.TarError,),
            )
    except (OSError, tarfile.TarError) as exc:
        return _build_archive_corrupt_result(
            archive_kind="tar",
            archive_path=archive_path,
            expansion_depth=expansion_depth,
            max_expansion_depth=max_expansion_depth,
            clue=str(exc),
        )


def _expand_archive_members(
    *,
    archive_kind: str,
    archive_path: Path,
    expansion_depth: int,
    max_expansion_depth: int,
    budget: ArchiveExpansionBudget,
    member_specs: list[_ArchiveMemberSpec],
    scan_member: Callable[[Path, str], ScanReport],
    extract_member: Callable[[_ArchiveMemberSpec, Path], None],
    corrupt_exceptions: tuple[type[BaseException], ...],
) -> tuple[ArchiveExpansionReport, list[EngineIssue]]:
    report = ArchiveExpansionReport(
        archive_kind=archive_kind,
        expansion_depth=expansion_depth,
        max_expansion_depth=max_expansion_depth,
    )
    issues: list[EngineIssue] = []

    with tempfile.TemporaryDirectory(prefix="scanbox-archive-") as temp_root:
        sorted_member_specs = sorted(member_specs, key=lambda info: _normalize_member_name_for_sort(info.raw_name))
        report.member_count = len(sorted_member_specs)
        temp_root_path = Path(temp_root)
        member_limit_hit = False
        byte_limit_hit = False

        for member_spec in sorted_member_specs:
            if member_spec.member_path is None or member_spec.unsupported:
                issues.append(
                    _build_archive_issue(
                        code="archive_member_unsupported",
                        archive_path=archive_path,
                        member_path=member_spec.raw_name,
                    )
                )
                continue

            if member_spec.password_protected:
                issues.append(
                    _build_archive_issue(
                        code="archive_password_protected",
                        archive_path=archive_path,
                        member_path=member_spec.member_path,
                    )
                )
                continue

            if budget.extracted_member_count >= budget.max_member_count:
                member_limit_hit = True
                break

            if budget.extracted_total_bytes + member_spec.size > budget.max_total_bytes:
                byte_limit_hit = True
                break

            extracted_path = temp_root_path / member_spec.member_path
            extracted_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                extract_member(member_spec, extracted_path)
            except RuntimeError as exc:
                if member_spec.password_protected:
                    issues.append(
                        _build_archive_issue(
                            code="archive_password_protected",
                            archive_path=archive_path,
                            member_path=member_spec.member_path,
                            clue=str(exc),
                        )
                    )
                    continue
                issues.append(
                    _build_archive_issue(
                        code="archive_corrupt",
                        archive_path=archive_path,
                        member_path=member_spec.member_path,
                        clue=str(exc),
                    )
                )
                break
            except OSError as exc:
                issues.append(
                    _build_archive_issue(
                        code="archive_corrupt",
                        archive_path=archive_path,
                        member_path=member_spec.member_path,
                        clue=str(exc),
                    )
                )
                break
            except corrupt_exceptions as exc:
                issues.append(
                    _build_archive_issue(
                        code="archive_corrupt",
                        archive_path=archive_path,
                        member_path=member_spec.member_path,
                        clue=str(exc),
                    )
                )
                break

            budget.extracted_member_count += 1
            budget.extracted_total_bytes += member_spec.size
            report.total_extracted_bytes += member_spec.size

            member_report = scan_member(extracted_path, member_spec.member_path)
            report.results.append(
                ArchiveMemberResult(
                    member_path=member_spec.member_path,
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

    return report, issues


def _build_archive_corrupt_result(
    *,
    archive_kind: str,
    archive_path: Path,
    expansion_depth: int,
    max_expansion_depth: int,
    clue: str,
) -> tuple[ArchiveExpansionReport, list[EngineIssue]]:
    return (
        ArchiveExpansionReport(
            archive_kind=archive_kind,
            expansion_depth=expansion_depth,
            max_expansion_depth=max_expansion_depth,
        ),
        [
            _build_archive_issue(
                code="archive_corrupt",
                archive_path=archive_path,
                clue=clue,
            )
        ],
    )


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


def _is_unsupported_zip_member_form(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    if mode == 0:
        return False
    file_type_bits = stat.S_IFMT(mode)
    if file_type_bits == 0:
        return False
    if stat.S_ISLNK(mode):
        return True
    return not stat.S_ISREG(mode)


def _is_unsupported_tar_member_form(info: tarfile.TarInfo) -> bool:
    if info.issym() or info.islnk():
        return True
    if info.isdev() or info.isfifo():
        return True
    return not info.isfile()


def _extract_zip_member(archive: zipfile.ZipFile, member_spec: _ArchiveMemberSpec, extracted_path: Path) -> None:
    with archive.open(member_spec.raw_name, "r") as source, extracted_path.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def _extract_tar_member(archive: tarfile.TarFile, member_spec: _ArchiveMemberSpec, extracted_path: Path) -> None:
    extracted = archive.extractfile(member_spec.raw_name)
    if extracted is None:
        raise tarfile.ExtractError(f"Could not extract archive member: {member_spec.raw_name}")
    with extracted, extracted_path.open("wb") as destination:
        shutil.copyfileobj(extracted, destination)


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
