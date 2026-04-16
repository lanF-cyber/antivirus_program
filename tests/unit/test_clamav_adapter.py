from pathlib import Path

from scanbox.adapters.clamav import ClamAvAdapter
from scanbox.config.models import AppConfig, AppSettings, EngineBinarySettings, EngineSettings, QuarantineSettings, TimeoutSettings


def make_config(tmp_path: Path, executable: Path | None, database_dir: Path | None) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        config_path=tmp_path / "config.toml",
        app=AppSettings(),
        timeouts=TimeoutSettings(),
        engines=EngineSettings(
            clamav=EngineBinarySettings(
                enabled=True,
                executable=executable,
                database_dir=database_dir,
            )
        ),
        quarantine=QuarantineSettings(directory=tmp_path / "quarantine"),
    )


def test_clamav_discover_reports_missing_executable(tmp_path: Path) -> None:
    config = make_config(tmp_path, tmp_path / "missing-clamscan.exe", tmp_path / "db")
    issue = ClamAvAdapter().discover(config)

    assert issue is not None
    assert issue.code == "executable_missing"
    assert issue.message == "ClamAV executable was not found."


def test_clamav_discover_reports_missing_database_dir(tmp_path: Path) -> None:
    executable = tmp_path / "clamscan.exe"
    executable.write_text("stub", encoding="utf-8")
    config = make_config(tmp_path, executable, tmp_path / "db")
    issue = ClamAvAdapter().discover(config)

    assert issue is not None
    assert issue.code == "database_missing"
    assert issue.message == "ClamAV database directory was not found."


def test_clamav_discover_reports_empty_database_dir(tmp_path: Path) -> None:
    executable = tmp_path / "clamscan.exe"
    executable.write_text("stub", encoding="utf-8")
    database_dir = tmp_path / "db"
    database_dir.mkdir()
    config = make_config(tmp_path, executable, database_dir)
    issue = ClamAvAdapter().discover(config)

    assert issue is not None
    assert issue.code == "database_empty"


def test_clamav_discover_reports_invalid_executable_path(tmp_path: Path) -> None:
    executable = tmp_path / "clamav-bin"
    executable.mkdir()
    database_dir = tmp_path / "db"
    database_dir.mkdir()
    (database_dir / "main.cvd").write_text("stub", encoding="utf-8")
    config = make_config(tmp_path, executable, database_dir)
    issue = ClamAvAdapter().discover(config)

    assert issue is not None
    assert issue.code == "configured_path_invalid"
    assert issue.details["field"] == "executable"


def test_clamav_discover_reports_invalid_database_path(tmp_path: Path) -> None:
    executable = tmp_path / "clamscan.exe"
    executable.write_text("stub", encoding="utf-8")
    database_dir = tmp_path / "db.txt"
    database_dir.write_text("not a directory", encoding="utf-8")
    config = make_config(tmp_path, executable, database_dir)
    issue = ClamAvAdapter().discover(config)

    assert issue is not None
    assert issue.code == "configured_path_invalid"
    assert issue.details["field"] == "database_dir"
