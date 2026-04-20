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

Preferred maintainer entrypoint for standalone pytest:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_standalone_pytest.ps1
```

Lower-level direct command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Current note:

- the helper is the hardened preferred path for standalone pytest on this workstation class
- the raw command may still work, but it is not the preferred mitigated entrypoint
- the helper only uses disposable local output under `reports/pytest-standalone/<timestamp>/`
- those helper outputs are not part of the artifact contract or packaged candidate evidence contract

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

Directory scan regression currently rides on the normal standalone test suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_standalone_pytest.ps1
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

## V2.2-B directory enhancement note

The current follow-up round keeps the directory scan CLI surface unchanged.

Important boundaries:

- no new `--exclude` / `--include` flags yet
- directory filter configuration now lives under `[directory_scan]` in `config/scanbox.toml`
- default ignore behavior is still:
  - `.git`
  - `.venv`
  - `__pycache__`
- file-level filter settings now support active filtering for:
  - `ignored_file_names`
  - `ignored_suffixes`
- `ignored_patterns`
- basename matching rules stay intentionally simple:
  - `ignored_file_names` uses exact basename matching
  - `ignored_suffixes` uses basename suffix string matching
  - `ignored_patterns` uses glob-style matching against the normalized POSIX relative path string
  - the semantic anchor is `nested/*`, which matches `nested/eicar.com`
  - no regex, case expansion, Windows `\` compatibility, or special multi-extension handling is introduced
- the default empty file-level fields are a strict no-op and do not change the current baseline
- `summary` still tracks verdict totals only
- `overall_status` is still derived from child result verdicts only
- `error_count` keeps the same meaning as the V2.2-A baseline

The implementation focus in this round is internal:

- move directory ignore/filter rules into a dedicated internal policy layer
- wire the directory policy through config and TOML without changing the default result set
- add separate directory-level accounting instead of overloading existing summary fields
- keep `stdout` on the focused default detail and `--report-out` on full detail
- keep custom richer filter verification in `pytest`, not in `acceptance_v2_directory.ps1`

## V2.3 reporting polish note

This follow-up round keeps the existing report schema and top-level report semantics stable.

Current expectations:

- default stdout is more focused for quick reading
- `--report-out` is still the full debugging view
- structured issue wording is more consistent across engine and ScanBox-level issues
- directory child reports still reuse the same single-file default/full compaction rules
- directory top-level `summary` and `accounting` keep the same fields and values, but default output now moves non-zero entries to the front in a fixed reading order
- zero-value `summary` and `accounting` entries still remain in default output
- the `accounting` order is only a readability aid, not a severity ranking

Current ClamAV default output keeps a stable summary instead of the full raw command output:

- `returncode`
- `match_count`
- `result_summary`
- `failure_summary` when present

Current YARA default output is also more focused:

- it keeps `match_count` and `result_summary`
- it no longer repeats `match_rules` in default output
- rule-level hit detail still remains visible through `detections`
- full output still keeps the larger YARA debugging context

Current capa default output now keeps only the compact daily-view fields:

- `returncode`
- `rule_count`
- `result_summary`
- `analysis_summary`
- `skip_reason`
- `capa_skipped`
- `failure_summary` when present

The larger capa execution context such as command, runtime temp directory, metadata, and full failure debugging fields remains in the full report.

## Release workflow note

After feature or documentation work is ready for a repository-level release candidate, switch from ad hoc development flow to the dedicated release workflow:

- [release-workflow.md](release-workflow.md)

Current expectations:

- this is a release-process baseline, not installer or package work
- freeze tags remain baseline anchors
- future semver tags are the formal release tags
- version bumps must update both:
  - `pyproject.toml`
  - `src/scanbox/__init__.py`
- the baseline acceptance scripts keep their current split and remain the release gates

For a future release entry, start from:

- [release-notes-template.md](release-notes-template.md)

For future distribution and release-artifact design decisions, use:

- [packaging-strategy.md](packaging-strategy.md)

For dry-run rehearsal and a baseline worksheet, also use:

- [release-prep-dry-run.md](release-prep-dry-run.md)
- [release-notes-dry-run-example.md](release-notes-dry-run-example.md)

For the full packaged release-candidate execution order, fixed gate interpretation, and evidence checklist, use:

- [release-workflow.md](release-workflow.md)
- [release-prep-dry-run.md](release-prep-dry-run.md)

For the hardened standalone pytest maintainer entrypoint, use:

- `powershell -ExecutionPolicy Bypass -File .\scripts\run_standalone_pytest.ps1`

Before a larger release-prep pass, run the quick local readiness precheck:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1
```

This is a release prep quick gate only. It does not replace the final acceptance gates.

## Packaging staging-tree prototype

For the maintainer-facing packaging staging-tree prototype, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\assemble_packaging_staging_tree.ps1
```

The current staging-tree prototype is driven by:

- `packaging/packaging-manifest.json`

This produces local prototype output under:

```text
reports/packaging-staging/<timestamp>/
```

To re-run the structure check against an existing staging run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_packaging_staging_tree.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>
```

Important boundary:

- this is disposable local output
- it is not a formal release artifact
- it should not be committed
- fallback-assisted success only means the portability gap was diagnosed and bypassed for maintainer validation
- it does not mean the supported operator path fully passed
- after changing the manifest, re-run assemble and then re-run verify

## Local zip packaging prototype

The maintainer-side local packaging flow is:

1. assemble
2. verify staging
3. package zip
4. verify zip
5. compare consistency

Use an existing staging run as the input:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_packaging_staging_tree.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>
```

Then verify the archive-level output:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_packaged_zip_artifact.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>
```

If you want to compare two completed local zip runs for consistency under the current local prototype profile:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\compare_packaged_zip_consistency.ps1 -BaselineRunDirectory .\reports\packaging-staging\<baseline-timestamp> -CandidateRunDirectory .\reports\packaging-staging\<candidate-timestamp>
```

The zip, fingerprint, and zip-check records are written back into the same local run directory:

```text
reports/packaging-staging/<timestamp>/
```

Important boundary:

- this is disposable local output
- it is not a formal release artifact
- it should not be committed
- `zip_sha256` consistency is a goal under the current local prototype profile only
- it is not a public reproducible-build commitment for a future formal release

## Operator zip consumption validation

To validate the unpacked operator-facing path against an existing local zip run, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate_operator_zip_consumption.ps1 -RunDirectory .\reports\packaging-staging\<timestamp> -BasePythonExe .\.venv\Scripts\python.exe
```

This validation flow is maintainer-facing and runs the current operator-path sequence:

1. `assemble`
2. `verify staging`
3. `package zip`
4. `verify zip`
5. `validate unpacked operator path`

Current validation mode:

- `yara_only_first_run`
- creates a disposable unpacked artifact workspace under the same run directory
- creates a disposable artifact-local `.venv`
- creates a temporary `config/scanbox.local.toml` only for the validation run
- writes `operator-consumption-validation.json` back into the same run directory

Workstation profile outcomes:

- `supported_operator_path`
  - `overall = PASS`
  - the supported operator path completed without fallback
- `maintainer_fallback_assisted`
  - `overall = WARN`
  - maintainer-side fallback allowed validation to complete, but the supported operator path did not fully pass
- `unsupported_operator_path`
  - `overall = FAIL`
  - even fallback-assisted validation did not complete successfully

Current workstation example:

- on the current machine, the latest validation result is:
  - `workstation_profile = maintainer_fallback_assisted`
  - `supported_operator_path_overall = FAIL`
  - `fallback_assisted_overall = PASS`
  - `overall = WARN`
- treat this as a current workstation example only, not as a global rule for every environment
- read the record as:
  - `PASS` = supported operator path
  - `WARN` = fallback-assisted diagnostic success
  - `FAIL` = fallback-assisted validation also did not succeed

Important boundary:

- this is disposable local output
- it is not a formal release artifact
- it should not be committed
