from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


SCRIPT_EXTENSIONS = {
    ".ps1": "powershell_script",
    ".js": "javascript",
    ".vbs": "vbscript",
    ".py": "python_script",
    ".bat": "batch_script",
    ".cmd": "batch_script",
    ".sh": "shell_script",
}

MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
}


class FileTypeInfo(BaseModel):
    kind: str
    mime_guess: str | None = None
    is_executable: bool = False
    is_script: bool = False
    capa_supported: bool = False
    notes: list[str] = Field(default_factory=list)


def detect_file_type(file_path: Path) -> FileTypeInfo:
    suffix = file_path.suffix.lower()
    head = file_path.read_bytes()[:4096]

    if head.startswith(b"MZ"):
        return FileTypeInfo(kind="pe", mime_guess="application/vnd.microsoft.portable-executable", is_executable=True, capa_supported=True)
    if head.startswith(b"\x7fELF"):
        return FileTypeInfo(kind="elf", mime_guess="application/x-elf", is_executable=True, capa_supported=True)
    if head[:4] in MACHO_MAGICS:
        return FileTypeInfo(kind="macho", mime_guess="application/x-mach-binary", is_executable=True, capa_supported=True)
    if suffix in SCRIPT_EXTENSIONS:
        return FileTypeInfo(kind=SCRIPT_EXTENSIONS[suffix], mime_guess="text/plain", is_script=True, capa_supported=False)
    if head.startswith(b"#!"):
        return FileTypeInfo(kind="script", mime_guess="text/plain", is_script=True, capa_supported=False)
    if head.startswith(b"PK\x03\x04"):
        return FileTypeInfo(kind="zip_archive", mime_guess="application/zip", capa_supported=False)
    return FileTypeInfo(kind="generic_file", mime_guess="application/octet-stream", capa_supported=False)
