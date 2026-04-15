from pathlib import Path

from scanbox.config.loader import load_app_config


def test_load_app_config_with_cli_override() -> None:
    config = load_app_config(Path("config/scanbox.toml"), profile_override="aggressive", verbose_override=True)
    assert config.app.default_profile.value == "aggressive"
    assert config.app.verbose is True
    assert config.engines.yara.rules_dir.name == "bundled"


def test_load_app_config_uses_local_override(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "scanbox.toml").write_text(
        """
[app]
default_profile = "balanced"
report_output_dir = "reports"
verbose = false

[timeouts]
hash_seconds = 10
clamav_seconds = 60
yara_seconds = 30
capa_seconds = 90

[engines.clamav]
enabled = true
executable = "C:\\\\Tools\\\\ClamAV\\\\clamscan.exe"
database_dir = ".local-tools\\\\clamav\\\\db"

[engines.yara]
enabled = true
rules_dir = "rules\\\\yara\\\\bundled"
manifest = "rules\\\\yara\\\\manifest.json"

[engines.capa]
enabled = true
executable = "C:\\\\Tools\\\\capa\\\\capa.exe"
rules_dir = "rules\\\\capa\\\\bundled"
manifest = "rules\\\\capa\\\\manifest.json"

[quarantine]
directory = "quarantine"
""".strip(),
        encoding="utf-8",
    )

    (config_dir / "scanbox.local.toml").write_text(
        """
[engines.clamav]
executable = "D:\\\\Local\\\\ClamAV\\\\clamscan.exe"
""".strip(),
        encoding="utf-8",
    )

    config = load_app_config(Path("config/scanbox.toml"))

    assert config.engines.clamav.executable == Path(r"D:\Local\ClamAV\clamscan.exe").resolve()
    assert config.engines.clamav.database_dir == (tmp_path / ".local-tools/clamav/db").resolve()
