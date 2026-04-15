from pathlib import Path

from scanbox.cli.main import main


def test_cli_returns_supported_exit_code_for_default_setup(monkeypatch) -> None:
    target = Path("tests/fixtures/benign/hello.txt").resolve()
    exit_code = main(["scan", str(target), "--config", "config/scanbox.toml"])
    assert exit_code in {0, 4, 5, 6}
