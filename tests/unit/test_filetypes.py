from pathlib import Path

from scanbox.core.filetypes import detect_file_type


def test_detect_script_file_type() -> None:
    info = detect_file_type(Path("tests/fixtures/benign/script.ps1"))
    assert info.is_script is True
    assert info.capa_supported is False
    assert info.kind == "powershell_script"


def test_detect_generic_file_type() -> None:
    info = detect_file_type(Path("tests/fixtures/benign/hello.txt"))
    assert info.kind == "generic_file"
