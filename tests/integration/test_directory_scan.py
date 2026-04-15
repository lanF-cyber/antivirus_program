from __future__ import annotations

import json
import shutil
from pathlib import Path

from scanbox.cli.main import main


FIXTURE_ROOT = Path("tests/fixtures/directory_mvp").resolve()


def _prepare_directory_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "directory_mvp"
    shutil.copytree(FIXTURE_ROOT, target)

    ignored_git = target / ".git"
    ignored_git.mkdir()
    (ignored_git / "ignored.txt").write_text("ignored git file", encoding="utf-8")

    ignored_venv = target / ".venv"
    ignored_venv.mkdir()
    (ignored_venv / "ignored.bin").write_bytes(b"ignored venv file")

    ignored_cache = target / "__pycache__"
    ignored_cache.mkdir()
    (ignored_cache / "ignored.pyc").write_bytes(b"ignored cache file")

    return target


def test_cli_directory_scan_returns_sorted_directory_report(capsys, tmp_path: Path) -> None:
    target = _prepare_directory_fixture(tmp_path)

    exit_code = main(["scan", str(target), "--config", "config/scanbox.toml"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["mode"] == "directory"
    assert payload["target_count"] == 3
    assert payload["scanned_count"] == 3
    assert payload["overall_status"] == "known_malicious"
    assert payload["summary"]["known_malicious"] == 1
    assert payload["summary"]["clean_by_known_checks"] == 2
    assert payload["accounting"] == {
        "ignored_directory_count": 3,
        "top_level_issue_count": 0,
        "directory_access_error_count": 0,
    }
    assert [entry["relative_path"] for entry in payload["results"]] == [
        "hello.txt",
        "nested/eicar.com",
        "script.ps1",
    ]

    script_entry = next(entry for entry in payload["results"] if entry["relative_path"] == "script.ps1")
    assert script_entry["report"]["engines"]["capa"]["state"] == "skipped_not_applicable"
    assert script_entry["report"]["engines"]["capa"]["raw_summary"]["skip_reason"] == "script_file_not_supported_in_v1_policy"


def test_cli_directory_scan_rejects_quarantine_move(capsys, tmp_path: Path) -> None:
    target = _prepare_directory_fixture(tmp_path)

    exit_code = main(
        [
            "scan",
            str(target),
            "--config",
            "config/scanbox.toml",
            "--quarantine",
            "move",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 8
    assert payload["overall_status"] == "scan_error"
    assert payload["issues"][0]["code"] == "input_error"


def test_cli_directory_scan_empty_directory_returns_scan_error(capsys, tmp_path: Path) -> None:
    target = tmp_path / "empty-directory"
    target.mkdir()

    exit_code = main(["scan", str(target), "--config", "config/scanbox.toml"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 6
    assert payload["mode"] == "directory"
    assert payload["target_count"] == 0
    assert payload["scanned_count"] == 0
    assert payload["overall_status"] == "scan_error"
    assert payload["accounting"] == {
        "ignored_directory_count": 0,
        "top_level_issue_count": 1,
        "directory_access_error_count": 0,
    }
    assert any(issue["code"] == "no_files_found" for issue in payload["issues"])
