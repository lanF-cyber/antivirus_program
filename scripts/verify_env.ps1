param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$ConfigPath = ".\config\scanbox.toml"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoPackageRoot = Join-Path $root "src\scanbox"
$artifactPackageRoot = Join-Path $root "runtime\scanbox"

function Resolve-RepoPath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $root $Value))
}

function Write-Check {
    param(
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    $prefix = "[$Level]"
    switch ($Level) {
        "PASS" { Write-Host "$prefix $Label - $Message" -ForegroundColor Green }
        "WARN" { Write-Host "$prefix $Label - $Message" -ForegroundColor Yellow }
        "FAIL" { Write-Host "$prefix $Label - $Message" -ForegroundColor Red }
    }
}

$hasRepoPackageRoot = Test-Path -LiteralPath $repoPackageRoot -PathType Container
$hasArtifactPackageRoot = Test-Path -LiteralPath $artifactPackageRoot -PathType Container

if ($hasRepoPackageRoot -and -not $hasArtifactPackageRoot) {
    $context = "repo"
} elseif ($hasArtifactPackageRoot -and -not $hasRepoPackageRoot) {
    $context = "artifact"
} else {
    Write-Check "FAIL" "Context" "verify_env.ps1 requires exactly one context. repo mode expects src/scanbox only. artifact mode expects runtime/scanbox only."
    exit 1
}

$pythonResolved = Resolve-RepoPath $PythonExe
if (-not $pythonResolved -or -not (Test-Path -LiteralPath $pythonResolved -PathType Leaf)) {
    Write-Check "FAIL" "Python" "Python executable was not found. Use .\.venv\Scripts\python.exe or pass -PythonExe with a valid path."
    exit 1
}

$configResolved = Resolve-RepoPath $ConfigPath
if (-not $configResolved -or -not (Test-Path -LiteralPath $configResolved -PathType Leaf)) {
    Write-Check "FAIL" "Config" "Configuration file was not found. Check the -ConfigPath argument and verify config/scanbox.toml exists."
    exit 1
}

$pythonScript = @'
import importlib.metadata as metadata
import json
import os
import pathlib
import stat as statmod
import sys
import tomllib


CAPA_RULE_EXTENSIONS = {".yml", ".yaml"}
YARA_RULE_EXTENSIONS = {".yar", ".yara"}
VALID_VENDOR_STATUSES = {"placeholder", "vendored"}
ENV_MAP = {
    "SCANBOX_DEFAULT_PROFILE": ("app", "default_profile"),
    "SCANBOX_VERBOSE": ("app", "verbose"),
    "SCANBOX_REPORT_OUTPUT_DIR": ("app", "report_output_dir"),
    "SCANBOX_CLAMAV_EXECUTABLE": ("engines", "clamav", "executable"),
    "SCANBOX_CLAMAV_DATABASE_DIR": ("engines", "clamav", "database_dir"),
    "SCANBOX_YARA_RULES_DIR": ("engines", "yara", "rules_dir"),
    "SCANBOX_YARA_MANIFEST": ("engines", "yara", "manifest"),
    "SCANBOX_CAPA_EXECUTABLE": ("engines", "capa", "executable"),
    "SCANBOX_CAPA_RULES_DIR": ("engines", "capa", "rules_dir"),
    "SCANBOX_CAPA_MANIFEST": ("engines", "capa", "manifest"),
    "SCANBOX_QUARANTINE_DIRECTORY": ("quarantine", "directory"),
}


def is_hidden(path: pathlib.Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        return bool(attrs & getattr(statmod, "FILE_ATTRIBUTE_HIDDEN", 0))
    except OSError:
        return False


def has_hidden_part(path: pathlib.Path, relative_to: pathlib.Path | None = None) -> bool:
    try:
        parts = path.relative_to(relative_to).parts if relative_to is not None else path.parts
    except ValueError:
        parts = path.parts
    return any(part.startswith(".") for part in parts)


def count_files(directory: pathlib.Path | None, extensions: set[str] | None = None) -> int:
    if directory is None or not directory.exists() or not directory.is_dir():
        return 0
    count = 0
    for candidate in directory.rglob("*"):
        if not candidate.is_file() or is_hidden(candidate) or has_hidden_part(candidate, directory):
            continue
        if extensions and candidate.suffix.lower() not in extensions:
            continue
        count += 1
    return count


def deep_merge(left: dict, right: dict) -> dict:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def set_nested(mapping: dict, keys: tuple[str, ...], value):
    current = mapping
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value


def parse_env_value(value: str):
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def derive_local_override_path(path: pathlib.Path) -> pathlib.Path | None:
    if path.stem.endswith(".local"):
        return None
    return path.with_name(f"{path.stem}.local{path.suffix}")


def load_json(path: pathlib.Path | None):
    if path is None or not path.exists() or not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def read_env_overrides() -> dict:
    overrides = {}
    for env_name, keys in ENV_MAP.items():
        if env_name in os.environ:
            set_nested(overrides, keys, parse_env_value(os.environ[env_name]))
    return overrides


root = pathlib.Path(sys.argv[1]).resolve()
config_path = pathlib.Path(sys.argv[2]).resolve()
context = sys.argv[3]
local_config_path = derive_local_override_path(config_path)
venv_python = (root / ".venv" / "Scripts" / "python.exe").resolve()
current_python = pathlib.Path(sys.executable).resolve()
repo_package_root = (root / "src" / "scanbox").resolve()
artifact_runtime_root = (root / "runtime").resolve()
artifact_package_root = (artifact_runtime_root / "scanbox").resolve()

if context == "repo":
    if artifact_package_root.exists() or not repo_package_root.exists():
        raise SystemExit(json.dumps({"context_error": "repo mode requires src/scanbox only"}))
elif context == "artifact":
    if repo_package_root.exists() or not artifact_package_root.exists():
        raise SystemExit(json.dumps({"context_error": "artifact mode requires runtime/scanbox only"}))
    sys.path.insert(0, str(artifact_runtime_root))
else:
    raise SystemExit(json.dumps({"context_error": f"unsupported context: {context}"}))

with config_path.open("rb") as handle:
    config = tomllib.load(handle)

local_config_exists = bool(local_config_path and local_config_path.exists())
if local_config_exists and local_config_path is not None:
    with local_config_path.open("rb") as handle:
        config = deep_merge(config, tomllib.load(handle))

config = deep_merge(config, read_env_overrides())


def resolve_config_path(value: str | None) -> pathlib.Path | None:
    if value is None:
        return None
    path = pathlib.Path(value)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def inspect_ruleset(rules_dir: pathlib.Path | None, manifest_path: pathlib.Path | None, extensions: set[str], require_vendor_status: bool):
    manifest_data, manifest_error = load_json(manifest_path)
    rule_count = count_files(rules_dir, extensions)
    vendor_status = None
    declared_rule_count = None
    mismatch_reasons: list[str] = []

    if isinstance(manifest_data, dict):
        vendor_status = manifest_data.get("vendor_status")
        declared_rule_count = manifest_data.get("rule_count", manifest_data.get("enabled_rule_count"))
        if require_vendor_status:
            if vendor_status is None:
                mismatch_reasons.append("vendor_status_missing")
            elif vendor_status not in VALID_VENDOR_STATUSES:
                mismatch_reasons.append("invalid_vendor_status")
        if isinstance(declared_rule_count, int) and declared_rule_count != rule_count:
            mismatch_reasons.append("rule_count_mismatch")
        if vendor_status == "placeholder" and rule_count > 0:
            mismatch_reasons.append("placeholder_with_rules")
        if vendor_status == "vendored" and rule_count == 0:
            mismatch_reasons.append("vendored_without_rules")
    elif manifest_path is not None and manifest_path.exists():
        mismatch_reasons.append("manifest_unreadable")

    return {
        "rules_dir": str(rules_dir) if rules_dir else None,
        "rules_dir_exists": bool(rules_dir and rules_dir.exists() and rules_dir.is_dir()),
        "manifest": str(manifest_path) if manifest_path else None,
        "manifest_exists": bool(manifest_path and manifest_path.exists() and manifest_path.is_file()),
        "manifest_error": manifest_error,
        "rule_count": rule_count,
        "vendor_status": vendor_status,
        "declared_rule_count": declared_rule_count,
        "mismatch_reasons": mismatch_reasons,
    }


scanbox_module_path = None
scanbox_import_error = None
scanbox_direct_url = None

expected_module_root = repo_package_root / "__init__.py" if context == "repo" else artifact_package_root / "__init__.py"
source_matches_context = False

try:
    import scanbox

    scanbox_module_path = pathlib.Path(scanbox.__file__).resolve()
    source_matches_context = scanbox_module_path == expected_module_root.resolve()
except Exception as exc:  # noqa: BLE001
    scanbox_import_error = str(exc)

try:
    distribution = metadata.distribution("scanbox")
    scanbox_direct_url = distribution.read_text("direct_url.json")
except Exception:  # noqa: BLE001
    scanbox_direct_url = None

clamav = config["engines"]["clamav"]
yara = config["engines"]["yara"]
capa = config["engines"]["capa"]

clamav_executable = resolve_config_path(clamav.get("executable"))
clamav_database_dir = resolve_config_path(clamav.get("database_dir"))
yara_rules_dir = resolve_config_path(yara.get("rules_dir"))
yara_manifest = resolve_config_path(yara.get("manifest"))
capa_executable = resolve_config_path(capa.get("executable"))
capa_rules_dir = resolve_config_path(capa.get("rules_dir"))
capa_manifest = resolve_config_path(capa.get("manifest"))

result = {
    "context": context,
    "root": str(root),
    "config_path": str(config_path),
    "local_config_path": str(local_config_path) if local_config_path else None,
    "local_config_exists": local_config_exists,
    "python": {
        "current": str(current_python),
        "venv_expected": str(venv_python),
        "is_root_venv": current_python == venv_python,
    },
    "scanbox": {
        "expected_module_path": str(expected_module_root.resolve()),
        "module_path": str(scanbox_module_path) if scanbox_module_path else None,
        "source_matches_context": source_matches_context,
        "import_error": scanbox_import_error,
        "direct_url": scanbox_direct_url,
    },
    "clamav": {
        "enabled": bool(clamav.get("enabled", True)),
        "executable": str(clamav_executable) if clamav_executable else None,
        "executable_exists": bool(clamav_executable and clamav_executable.exists()),
        "executable_is_file": bool(clamav_executable and clamav_executable.exists() and clamav_executable.is_file()),
        "freshclam": (
            str((clamav_executable.parent / "freshclam.exe").resolve())
            if clamav_executable and clamav_executable.parent.exists()
            else None
        ),
        "freshclam_exists": bool(
            clamav_executable
            and clamav_executable.parent.exists()
            and (clamav_executable.parent / "freshclam.exe").exists()
            and (clamav_executable.parent / "freshclam.exe").is_file()
        ),
        "database_dir": str(clamav_database_dir) if clamav_database_dir else None,
        "database_path_exists": bool(clamav_database_dir and clamav_database_dir.exists()),
        "database_dir_exists": bool(clamav_database_dir and clamav_database_dir.exists() and clamav_database_dir.is_dir()),
        "database_file_count": count_files(clamav_database_dir),
    },
    "yara": {
        "enabled": bool(yara.get("enabled", True)),
        **inspect_ruleset(yara_rules_dir, yara_manifest, YARA_RULE_EXTENSIONS, False),
    },
    "capa": {
        "enabled": bool(capa.get("enabled", True)),
        "executable": str(capa_executable) if capa_executable else None,
        "executable_exists": bool(capa_executable and capa_executable.exists()),
        **inspect_ruleset(capa_rules_dir, capa_manifest, CAPA_RULE_EXTENSIONS, True),
    },
    "artifact_profile": (
        "yara_only_first_run"
        if context == "artifact" and not bool(clamav.get("enabled", True)) and not bool(capa.get("enabled", True))
        else (
            "full_external_dependency_path"
            if context == "artifact"
            else None
        )
    ),
    "dependency_expectations": {
        "runtime_python": "required",
        "bundled_yara": "required",
        "clamav": "optional_for_yara_only_first_run",
        "capa": "optional_for_yara_only_first_run",
        "full_external_dependencies": "required_for_full_external_dependency_path",
    },
}

print(json.dumps(result))
'@

try {
    $rawSummary = $pythonScript | & $pythonResolved - $root $configResolved $context
} catch {
    Write-Check "FAIL" "Python" "Failed to run the Python inspection logic. Verify Python, dependencies, and config readability."
    Write-Host $_.Exception.Message
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Check "FAIL" "Python" "The Python inspection logic exited with an error. Verify Python, dependencies, and config readability."
    if ($rawSummary) {
        Write-Host $rawSummary
    }
    exit 1
}

try {
    $summary = $rawSummary | ConvertFrom-Json
} catch {
    Write-Check "FAIL" "Python" "The Python inspection output was not valid JSON."
    if ($rawSummary) {
        Write-Host $rawSummary
    }
    exit 1
}

$warnCount = 0
$failCount = 0
$passCount = 0

function Register-Result {
    param(
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Level,
        [string]$Label,
        [string]$Message
    )

    switch ($Level) {
        "PASS" { $script:passCount += 1 }
        "WARN" { $script:warnCount += 1 }
        "FAIL" { $script:failCount += 1 }
    }

    Write-Check $Level $Label $Message
}

Write-Host "ScanBox environment verification"
Write-Host "Context: $($summary.context)"
Write-Host "Root: $($summary.root)"
Write-Host "Config: $($summary.config_path)"
if ($summary.local_config_path) {
    if ($summary.local_config_exists) {
        Write-Host "Local override: $($summary.local_config_path) (loaded)"
    } else {
        Write-Host "Local override: $($summary.local_config_path) (not found)"
    }
}
Write-Host "Python: $($summary.python.current)"
if ($summary.context -eq "artifact") {
    Write-Host "Profile: $($summary.artifact_profile)"
    Write-Host ("Dependency expectations: runtime_python={0}; bundled_yara={1}; clamav={2}; capa={3}; full_external_dependencies={4}" -f `
        $summary.dependency_expectations.runtime_python, `
        $summary.dependency_expectations.bundled_yara, `
        $summary.dependency_expectations.clamav, `
        $summary.dependency_expectations.capa, `
        $summary.dependency_expectations.full_external_dependencies)
}
Write-Host ""

if ($summary.python.is_root_venv) {
    Register-Result "PASS" "Python/venv" "The current Python executable is the local .venv interpreter under the active root."
} else {
    Register-Result "WARN" "Python/venv" "The current Python executable is not the local .venv interpreter under the active root. Prefer .\.venv\Scripts\python.exe."
}

if ($summary.context -eq "repo") {
    if ($summary.scanbox.source_matches_context) {
        Register-Result "PASS" "Editable install" "scanbox resolves to this repository via editable install."
    } elseif ($summary.scanbox.import_error) {
        Register-Result "FAIL" "Editable install" "scanbox could not be imported. Run .\.venv\Scripts\python.exe -m pip install -e ."
    } else {
        Register-Result "FAIL" "Editable install" "scanbox is importable, but not from this repository. Re-run .\.venv\Scripts\python.exe -m pip install -e ."
    }
} elseif ($summary.context -eq "artifact") {
    if ($summary.scanbox.source_matches_context) {
        Register-Result "PASS" "Artifact runtime import" "scanbox resolves from the unpacked artifact runtime directory."
    } elseif ($summary.scanbox.import_error) {
        Register-Result "FAIL" "Artifact runtime import" "scanbox could not be imported from the unpacked artifact runtime."
    } else {
        Register-Result "FAIL" "Artifact runtime import" "scanbox imported, but not from the unpacked artifact runtime directory."
    }
} else {
    Register-Result "FAIL" "Context" "Unsupported verify_env context."
}

if ($summary.clamav.enabled) {
    if ($summary.clamav.executable_exists -and $summary.clamav.executable_is_file) {
        Register-Result "PASS" "ClamAV executable" "Found $($summary.clamav.executable)."
    } elseif ($summary.clamav.executable_exists) {
        Register-Result "FAIL" "ClamAV executable" "[configured_path_invalid] The configured ClamAV executable path exists but is not a file: $($summary.clamav.executable)."
    } else {
        Register-Result "FAIL" "ClamAV executable" "[executable_missing] Configured clamscan.exe was not found. Check config/scanbox.local.toml first, then config/scanbox.toml -> engines.clamav.executable."
    }

    if (-not $summary.clamav.database_path_exists) {
        $message = "[database_missing] Configured ClamAV database directory was not found. Check engines.clamav.database_dir."
        if ($summary.clamav.freshclam_exists) {
            $message += " After placing the official ClamAV package, initialize the database with: $($summary.clamav.freshclam) --datadir `"$($summary.clamav.database_dir)`""
        }
        Register-Result "FAIL" "ClamAV database" $message
    } elseif (-not $summary.clamav.database_dir_exists) {
        Register-Result "FAIL" "ClamAV database" "[configured_path_invalid] The configured ClamAV database path exists but is not a directory: $($summary.clamav.database_dir)."
    } elseif ([int]$summary.clamav.database_file_count -le 0) {
        $message = "[database_empty] ClamAV database directory exists but is empty."
        if ($summary.clamav.freshclam_exists) {
            $message += " Initialize it with: $($summary.clamav.freshclam) --datadir `"$($summary.clamav.database_dir)`""
        } else {
            $message += " Initialize the official ClamAV signature database after placing the official package."
        }
        Register-Result "FAIL" "ClamAV database" $message
    } else {
        Register-Result "PASS" "ClamAV database" "Found $($summary.clamav.database_file_count) files in the configured database directory."
    }

    if ($summary.clamav.freshclam_exists) {
        Register-Result "PASS" "freshclam" "Found $($summary.clamav.freshclam)."
    } elseif ($summary.clamav.executable_exists -and $summary.clamav.executable_is_file) {
        Register-Result "WARN" "freshclam" "freshclam.exe was not found next to clamscan.exe. Database initialization may need a different official package layout."
    }
}

if ($summary.yara.enabled) {
    if ($summary.yara.rules_dir_exists) {
        Register-Result "PASS" "YARA rules dir" "Bundled YARA rules directory exists."
    } else {
        Register-Result "FAIL" "YARA rules dir" "Bundled YARA rules directory was not found. Check engines.yara.rules_dir."
    }

    if ($summary.yara.manifest_exists -and -not $summary.yara.manifest_error) {
        Register-Result "PASS" "YARA manifest" "YARA manifest exists and was parsed successfully."
    } else {
        Register-Result "FAIL" "YARA manifest" "YARA manifest is missing or unreadable. Check rules/yara/manifest.json."
    }

    if ([int]$summary.yara.rule_count -gt 0) {
        Register-Result "PASS" "YARA rule count" "Found $($summary.yara.rule_count) YARA rule files."
    } else {
        Register-Result "FAIL" "YARA rule count" "No .yar or .yara files were found in the bundled YARA rules directory."
    }

    if ($summary.yara.mismatch_reasons.Count -gt 0) {
        $reasons = [string]::Join(", ", $summary.yara.mismatch_reasons)
        Register-Result "FAIL" "YARA manifest consistency" "Manifest does not match the bundled YARA rules directory: $reasons."
    } else {
        Register-Result "PASS" "YARA manifest consistency" "Manifest and bundled YARA rules directory are consistent."
    }
}

if ($summary.capa.enabled) {
    if ($summary.capa.executable_exists) {
        Register-Result "PASS" "capa executable" "Found $($summary.capa.executable)."
    } else {
        Register-Result "FAIL" "capa executable" "Configured capa executable was not found. Check config/scanbox.local.toml first, then config/scanbox.toml -> engines.capa.executable."
    }

    if ($summary.capa.rules_dir_exists) {
        Register-Result "PASS" "capa rules dir" "Bundled capa rules directory exists."
    } else {
        Register-Result "FAIL" "capa rules dir" "Bundled capa rules directory was not found. Check engines.capa.rules_dir."
    }

    if ($summary.capa.manifest_exists -and -not $summary.capa.manifest_error) {
        Register-Result "PASS" "capa manifest" "capa manifest exists and was parsed successfully."
    } else {
        Register-Result "FAIL" "capa manifest" "capa manifest is missing or unreadable. Check rules/capa/manifest.json."
    }

    $capaVendorStatus = [string]$summary.capa.vendor_status
    $capaRuleCount = [int]$summary.capa.rule_count
    $capaDeclaredRuleCount = if ($null -ne $summary.capa.declared_rule_count) { [int]$summary.capa.declared_rule_count } else { $null }

    if ($capaVendorStatus -eq "placeholder") {
        Register-Result "WARN" "capa vendor status" "capa-rules are still a placeholder. Vendor the official snapshot before treating capa as ready."
    } elseif ($capaVendorStatus -eq "vendored") {
        Register-Result "PASS" "capa vendor status" "Manifest marks the bundled capa rules as vendored."
    } else {
        Register-Result "FAIL" "capa vendor status" "Manifest vendor_status is missing or invalid. Allowed values are placeholder or vendored."
    }

    if ($capaRuleCount -gt 0) {
        Register-Result "PASS" "capa rule count" "Found $capaRuleCount capa rule files (.yml/.yaml only)."
    } else {
        Register-Result "WARN" "capa rule count" "No .yml or .yaml capa rule files were found. This is expected for a placeholder ruleset, but not for a vendored snapshot."
    }

    if ($null -eq $capaDeclaredRuleCount) {
        Register-Result "FAIL" "capa manifest count" "Manifest is missing rule_count. Keep it synchronized with the bundled capa rules directory."
    } elseif ($capaDeclaredRuleCount -eq $capaRuleCount) {
        Register-Result "PASS" "capa manifest count" "Manifest rule_count matches the bundled capa rules directory."
    } else {
        Register-Result "FAIL" "capa manifest count" "Manifest rule_count=$capaDeclaredRuleCount but the bundled capa rules directory contains $capaRuleCount rule files."
    }

    if ($summary.capa.mismatch_reasons.Count -gt 0) {
        $reasons = [string]::Join(", ", $summary.capa.mismatch_reasons)
        Register-Result "FAIL" "capa manifest consistency" "Manifest does not match the bundled capa rules directory: $reasons."
    } else {
        Register-Result "PASS" "capa manifest consistency" "Manifest and bundled capa rules directory are internally consistent."
    }
}

Write-Host ""
Write-Host "Summary: PASS=$passCount WARN=$warnCount FAIL=$failCount"

if ($failCount -gt 0 -or $warnCount -gt 0) {
    exit 2
}

exit 0
