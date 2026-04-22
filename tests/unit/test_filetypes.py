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


def test_detect_tar_archive_by_suffix(tmp_path: Path) -> None:
    tar_path = tmp_path / "sample.tar"
    tar_path.write_bytes(b"not-a-real-tar-needed-for-suffix-detection")

    info = detect_file_type(tar_path)

    assert info.kind == "tar_archive"
    assert info.mime_guess == "application/x-tar"


def test_detect_tgz_archive_by_suffix(tmp_path: Path) -> None:
    tar_path = tmp_path / "sample.tgz"
    tar_path.write_bytes(b"not-a-real-tar-needed-for-suffix-detection")

    info = detect_file_type(tar_path)

    assert info.kind == "tar_archive"
    assert info.mime_guess == "application/x-tar"
