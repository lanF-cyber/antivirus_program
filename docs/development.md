# Development

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt -r .\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## Verify the environment

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
```

## v1 milestone acceptance

If the immediate goal is not feature work but confirming the current v1 baseline, start here:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

The acceptance script runs the current official v1 chain:

1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest -q`
3. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`
4. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt`
5. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1`
6. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com`

Artifacts from the current run are written to:

```text
reports/acceptance-v1/<timestamp>/
```

Keep these two buckets separate:

- `reports/acceptance-v1/<timestamp>/`: local run artifacts for review
- `docs/milestones/golden/`: committed sanitized golden outputs

Optional local-only enhancements stay out of the default must-pass chain. If you explicitly want the workstation-only `python.exe` capa validation and a local full report size comparison, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1 -IncludeLocalEnhancements
```

Milestone snapshot entrypoint:

- [scanbox-v1-freeze.md](milestones/scanbox-v1-freeze.md)

## Quarantine lifecycle development

V2 Phase 1 keeps quarantine lifecycle work out of the frozen v1 acceptance baseline. Use the normal scan flow to create a quarantined record, then manage it with the dedicated subcommands.

Minimal manual flow:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com --quarantine move
.\.venv\Scripts\python.exe -m scanbox quarantine list
.\.venv\Scripts\python.exe -m scanbox quarantine restore <scan_id>
.\.venv\Scripts\python.exe -m scanbox quarantine delete <scan_id> --yes
```

Behavioral guardrails:

- `list` only returns record summaries, not full `events`
- `restore` defaults to the stored `original_path`
- `restore` rejects an existing target path instead of overwriting it
- `delete` requires `--yes` and only removes the payload, not the audit sidecar
- legacy records without an explicit `state` are handled conservatively:
  - payload present -> inferred `quarantined`
  - payload missing -> `unknown` with structured issues

## Manual ClamAV continuation

If `verify_env.ps1` reports `executable_missing`, `database_missing`, `database_empty`, or `configured_path_invalid` for ClamAV, continue from the official pinned Windows package recorded in [dependencies.md](dependencies.md).

Recommended manual flow:

```powershell
# 1. Download the pinned official artifact manually:
#    clamav-1.4.3.win.x64.zip
#
# 2. Verify the SHA256 matches:
#    5c86a6ed17e45e5c14c9c7c7b58cfaabcdee55a195991439bb6b6c6618827e6c
#
# 3. Extract it to a local directory of your choice, for example:
#    C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\
#
# 4. Keep config\scanbox.toml as the repository default, then create
#    config\scanbox.local.toml for this workstation:
#    [engines.clamav]
#    executable = "C:\\Users\\Lancelot\\Desktop\\安装包\\clamav-1.4.3.win.x64\\clamscan.exe"
#
# 5. Create the repository-local database directory:
New-Item -ItemType Directory -Force -Path .\.local-tools\clamav\db | Out-Null
#
# 6. Copy config\clamav\freshclam.conf to config\clamav\freshclam.local.conf
#    and set DatabaseDirectory to the real local database path if needed.
#
# 7. If freshclam.exe is present in the official package, initialize the database.
& 'C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\freshclam.exe' --config-file 'C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf' --stdout --verbose --show-progress
#
# 8. If freshclam reports dead proxy variables such as https_proxy/all_proxy
#    pointing at 127.0.0.1:9, clear them for the command and retry:
$env:https_proxy=''; $env:HTTPS_PROXY=''; $env:http_proxy=''; $env:HTTP_PROXY=''; $env:all_proxy=''; $env:ALL_PROXY=''
& 'C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\freshclam.exe' --config-file 'C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf' --stdout --verbose --show-progress

# 9. Re-run environment verification and the sample scans:
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

ScanBox CLI and `verify_env.ps1` will automatically load `config/scanbox.local.toml` when `config/scanbox.toml` is the selected base config.

Current environment note:

- The official ClamAV release metadata is reachable.
- Small assets such as `.sig` files are reachable through the GitHub assets API.
- The large Windows zip download path was not reliable from this environment, so the official package was acquired manually and validated separately.
- The current validated local setup on this workstation is:
  - repository default config: `config/scanbox.toml`
  - workstation override config: `config/scanbox.local.toml`
  - executable override: `C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\clamscan.exe`
  - database_dir: `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\clamav\db`
  - freshclam local config: `C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf`
  - freshclam template: `C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.conf`

## Manual capa continuation

The repository now carries a vendored pinned official `capa-rules v9.3.0` snapshot in `rules/capa/bundled/`. On a new workstation, the remaining manual step is usually the official `capa.exe` itself.

Recommended manual flow:

```powershell
# 1. Obtain the pinned official Windows artifact recorded in docs/dependencies.md:
#    capa-v9.3.1-windows.zip
#
# 2. Verify the SHA256 matches:
#    d6e05a7c0c2171c4e476032d205267c03787db2ecedb7717e45a64b9f5895023
#
# 3. Extract it into a workstation-local path, for example:
#    .\.local-tools\capa\capa-v9.3.1\capa.exe
#
# 4. Keep config\scanbox.toml as the repository default and update
#    config\scanbox.local.toml only:
#    [engines.capa]
#    executable = ".local-tools\\capa\\capa-v9.3.1\\capa.exe"
#
# 5. Re-run verification:
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
#
# 6. Use a local PE file only for manual validation:
.\.venv\Scripts\python.exe -m scanbox scan .\.venv\Scripts\python.exe
```

Current environment note:

- The official `capa` release metadata is reachable from this workstation when the dead local proxy variables are cleared.
- The pinned Windows artifact was validated locally and extracted to:
  - `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\capa\capa-v9.3.1\capa.exe`
- The workstation override lives in:
  - `C:\Users\Lancelot\Desktop\antivirus_program\config\scanbox.local.toml`
- ScanBox now runs `capa.exe` with a repository-local temporary directory:
  - `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\capa\runtime-tmp`
  - This avoids PyInstaller extraction failures caused by an unwritable default temp directory.

## Run the CLI

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

If you want the full debugging report on disk while keeping a focused JSON on stdout:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\.venv\Scripts\python.exe --report-out .\reports\python-full.json
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Notes

- `stdout` is reserved for JSON reports.
- The default stdout JSON is the focused report shape.
- `--report-out` writes the full report, including larger engine debugging fields such as the full `capa` metadata payload.
- Diagnostic output belongs on `stderr`.
- v1 intentionally supports one file path per invocation.
- For daily maintenance, prefer [Operations](operations.md) as the primary entrypoint.
- For the current frozen milestone snapshot, start from [scanbox-v1-freeze.md](milestones/scanbox-v1-freeze.md).

## V2.1 freeze note

Quarantine lifecycle now has its own acceptance baseline:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
```

Do not treat it as a replacement for:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

Current split:

- `acceptance_v1.ps1`: scanning baseline
- `acceptance_v2_quarantine.ps1`: quarantine lifecycle baseline

The V2.1 script writes to:

```text
reports/acceptance-v2-quarantine/<timestamp>/
```

and overrides the quarantine directory for the run, so it does not depend on the repo-root `quarantine/` directory.

## V2.2-A directory scan MVP

Directory scanning now has a minimal serial MVP that keeps the existing single-file scan core intact.

Minimal local command:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
```

Optional full report for manual review:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp --report-out .\reports\directory-mvp.full.json
```

Current boundary:

- recursive by default
- serial execution only
- stable `results[]` ordering by relative path
- child results still use the single-file `ScanReport`
- no batch quarantine in directory mode

Directory scan regression currently rides on the normal test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## V2.2-A freeze note

Directory scanning now has its own acceptance baseline:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1
```

Do not treat it as a replacement for:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
```

Current split:

- `acceptance_v1.ps1`: single-file scanning baseline
- `acceptance_v2_quarantine.ps1`: quarantine lifecycle baseline
- `acceptance_v2_directory.ps1`: directory scanning baseline

The V2.2-A script writes to:

```text
reports/acceptance-v2-directory/<timestamp>/
```

The full report path is fixed to:

```text
reports/acceptance-v2-directory/<timestamp>/directory.full.json
```

These are local artifacts only. V2.2-A does not add committed golden outputs for directory mode in this freeze.
