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


def timeout_result_summary() -> str:
    return "timed out"


def execution_failed_result_summary() -> str:
    return "execution failed"


def runtime_error_result_summary() -> str:
    return "runtime error"


def invalid_json_result_summary() -> str:
    return "invalid JSON output"


def scan_skipped_result_summary() -> str:
    return "scan skipped"


def yara_result_summary(match_count: int) -> str:
    if match_count > 0:
        return f"{match_count} rule match(es)"
    return "no rules matched"


def capa_result_summary(rule_count: int | None) -> str:
    if (rule_count or 0) > 0:
        return f"{rule_count} capability rule(s) matched"
    return "no capability rules matched"


def failure_summary(*candidates: str | None) -> str | None:
    for candidate in candidates:
        summary = shorten_clue(candidate)
        if summary:
            return summary
    return None


def scanbox_issue(code: str, *, clue: str | None = None) -> str:
    if code == "config_error":
        return _append_clue("Configuration is invalid.", clue)
    if code == "archive_byte_budget_exceeded":
        return _append_clue("Archive expansion stopped after the extracted byte budget was reached.", clue)
    if code == "archive_corrupt":
        return _append_clue("Archive could not be expanded because it is corrupt or unreadable.", clue)
    if code == "archive_depth_limit_exceeded":
        return _append_clue("Archive expansion stopped after the configured depth limit was reached.", clue)
    if code == "archive_member_limit_exceeded":
        return _append_clue("Archive expansion stopped after the configured member limit was reached.", clue)
    if code == "archive_member_unsupported":
        return _append_clue("Archive member was skipped because its form is unsupported.", clue)
    if code == "archive_password_protected":
        return _append_clue("Archive member was skipped because it is password protected.", clue)
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
