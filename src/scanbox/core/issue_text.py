from __future__ import annotations

import re


_ENGINE_LABELS = {
    "capa": "capa",
    "clamav": "ClamAV",
    "scanbox": "ScanBox",
    "yara": "YARA",
}


def engine_label(engine: str) -> str:
    return _ENGINE_LABELS.get(engine, engine)


def shorten_clue(text: str | None, *, max_length: int = 140) -> str | None:
    if not text:
        return None

    first_non_empty_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_non_empty_line:
        return None

    compact = re.sub(r"\s+", " ", first_non_empty_line).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def _append_clue(base_message: str, clue: str | None) -> str:
    short_clue = shorten_clue(clue)
    if not short_clue:
        return base_message
    return f"{base_message.rstrip('.')}." + f" {short_clue}"


def executable_not_configured(engine: str) -> str:
    return f"{engine_label(engine)} executable is not configured."


def executable_not_found(engine: str) -> str:
    return f"{engine_label(engine)} executable was not found."


def configured_path_invalid(engine: str, subject: str, expected: str) -> str:
    return f"{engine_label(engine)} {subject} path is not a {expected}."


def database_missing(engine: str) -> str:
    return f"{engine_label(engine)} database directory was not found."


def database_empty(engine: str) -> str:
    return f"{engine_label(engine)} database directory has no database files."


def rules_missing(engine: str) -> str:
    return f"{engine_label(engine)} rules directory was not found."


def rules_empty(engine: str, *, usable: bool = False) -> str:
    noun = "usable rule files" if usable else "rule files"
    return f"{engine_label(engine)} rules directory has no {noun}."


def manifest_missing(engine: str) -> str:
    return f"{engine_label(engine)} rules manifest was not found."


def manifest_mismatch(engine: str) -> str:
    return f"{engine_label(engine)} rules manifest does not match the bundled rules."


def rules_placeholder(engine: str) -> str:
    return f"{engine_label(engine)} rules are still placeholder content."


def python_module_missing(module_name: str) -> str:
    return f"{module_name} is not installed."


def timed_out(engine: str, *, clue: str | None = None) -> str:
    return _append_clue(f"{engine_label(engine)} timed out.", clue)


def execution_failed(engine: str, *, clue: str | None = None) -> str:
    return _append_clue(f"{engine_label(engine)} could not start.", clue)


def scan_failed(engine: str, *, clue: str | None = None) -> str:
    return _append_clue(f"{engine_label(engine)} scan failed.", clue)


def runtime_error(engine: str, *, clue: str | None = None) -> str:
    return _append_clue(f"{engine_label(engine)} returned a runtime error.", clue)


def invalid_json(engine: str, *, clue: str | None = None) -> str:
    return _append_clue(f"{engine_label(engine)} returned invalid JSON.", clue)


def scanbox_issue(code: str, *, clue: str | None = None) -> str:
    if code == "config_error":
        return _append_clue("Configuration is invalid.", clue)
    if code == "directory_access_error":
        return _append_clue("Could not access directory.", clue)
    if code == "file_access_error":
        return _append_clue("Could not access file.", clue)
    if code == "input_error":
        return _append_clue("Input was rejected.", clue)
    if code == "no_files_found":
        return "No files found after applying ignore rules."
    if code == "scan_error":
        return _append_clue("Scan failed.", clue)
    return _append_clue("ScanBox reported an issue.", clue)
