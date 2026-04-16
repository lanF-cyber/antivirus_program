from pathlib import Path

from scanbox.config.models import AppConfig, DirectoryScanSettings
from scanbox.core.enums import VerdictStatus
from scanbox.core.models import QuarantineMode
from scanbox.pipeline.directory_scan_policy import DirectoryScanPolicy
from scanbox.pipeline.orchestrator import ScanOrchestrator
import scanbox.pipeline.orchestrator as orchestrator_module


def test_directory_scan_policy_default_ignores_v22a_names() -> None:
    policy = DirectoryScanPolicy.default()

    kept, ignored_count = policy.filter_directory_names([".git", ".venv", "__pycache__", "nested"])

    assert kept == ["nested"]
    assert ignored_count == 3


def test_directory_scan_policy_can_be_constructed_for_future_customization() -> None:
    policy = DirectoryScanPolicy(ignored_directory_names=frozenset({"skip-me"}))

    kept, ignored_count = policy.filter_directory_names(["skip-me", "keep-me"])

    assert kept == ["keep-me"]
    assert ignored_count == 1


def test_directory_scan_policy_can_be_built_from_directory_scan_settings() -> None:
    settings = DirectoryScanSettings(
        ignored_directory_names=["skip-me"],
        ignored_file_names=["ignore.txt"],
        ignored_suffixes=[".tmp"],
        ignored_patterns=["nested/*"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.ignored_directory_names == frozenset({"skip-me"})
    assert policy.ignored_file_names == ("ignore.txt",)
    assert policy.ignored_suffixes == (".tmp",)
    assert policy.ignored_patterns == ("nested/*",)


def test_directory_scan_policy_matches_file_names_and_suffixes_on_basename_only() -> None:
    settings = DirectoryScanSettings(
        ignored_file_names=["hello.txt"],
        ignored_suffixes=[".ps1"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.should_ignore_file_name("hello.txt") is True
    assert policy.should_ignore_file_name("nested/hello.txt") is False
    assert policy.should_ignore_suffix("script.ps1") is True
    assert policy.should_ignore_suffix("script.ps1.bak") is False
    assert policy.should_ignore_file(relative_path="hello.txt", file_name="hello.txt") is True
    assert policy.should_ignore_file(relative_path="nested/script.ps1", file_name="script.ps1") is True


def test_directory_scan_policy_matches_patterns_on_posix_relative_paths() -> None:
    settings = DirectoryScanSettings(
        ignored_patterns=["nested/*"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.should_ignore_pattern("nested/eicar.com") is True
    assert policy.should_ignore_pattern("nested/deeper/eicar.com") is False
    assert policy.should_ignore_pattern("foo/nested/eicar.com") is False


def test_directory_scan_policy_pattern_matching_uses_root_anchored_relative_paths() -> None:
    settings = DirectoryScanSettings(
        ignored_patterns=["*.ps1"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.should_ignore_pattern("script.ps1") is True
    assert policy.should_ignore_pattern("nested/script.ps1") is False


def test_directory_scan_policy_patterns_are_not_regex_or_case_expanded() -> None:
    settings = DirectoryScanSettings(
        ignored_patterns=["nested/.*", "NESTED/*"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.should_ignore_pattern("nested/eicar.com") is False


def test_directory_scan_policy_file_filters_count_a_double_match_once() -> None:
    settings = DirectoryScanSettings(
        ignored_file_names=["script.ps1"],
        ignored_suffixes=[".ps1"],
        ignored_patterns=["script.ps1"],
    )

    policy = DirectoryScanPolicy.from_settings(settings)

    assert policy.should_ignore_file(relative_path="script.ps1", file_name="script.ps1") is True
    assert policy.should_ignore_file(relative_path="nested/eicar.com", file_name="eicar.com") is False


def test_scan_directory_accounting_tracks_directory_access_errors(monkeypatch, tmp_path: Path) -> None:
    root_path = tmp_path / "directory-root"
    root_path.mkdir()
    config = AppConfig(root_dir=tmp_path, config_path=tmp_path / "scanbox.toml")
    orchestrator = ScanOrchestrator(config=config, adapters=[], directory_policy=DirectoryScanPolicy.default())

    def fake_walk(root, topdown=True, onerror=None, followlinks=False):
        assert onerror is not None
        onerror(PermissionError(13, "Access is denied", str(root_path / "blocked")))
        yield (str(root_path), [], [])

    monkeypatch.setattr(orchestrator_module.os, "walk", fake_walk)

    report = orchestrator.scan_directory(
        directory_path=root_path,
        quarantine_mode=QuarantineMode.ASK,
        dry_run_quarantine=False,
    )

    assert report.overall_status == VerdictStatus.SCAN_ERROR
    assert report.accounting.ignored_directory_count == 0
    assert report.accounting.directory_access_error_count == 1
    assert report.accounting.top_level_issue_count == 2
    assert report.error_count == 2
    assert [issue.code for issue in report.issues] == ["directory_access_error", "no_files_found"]
