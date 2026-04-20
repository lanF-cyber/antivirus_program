# v0.1.0 Packaged Candidate Dry-Run

> Dry-run only.
> No GitHub Release published.
> No installer created.
> No formal published package artifact created.

This document records one real local packaged candidate rehearsal for the `v0.1.0` ScanBox candidate. Repository readiness, the three baseline gates, staging verify, zip verify, and the optional consistency compare all passed. Operator consumption validation on the current workstation ended at `WARN`, so the packaged candidate overall is `WARN`.

## Candidate

- Candidate version: `0.1.0`
- Candidate commit: `2cc0a9d13ca901d83cbc32eb4213ae73bf7b80c2`
- Planned semver tag: `v0.1.0` (`dry-run only`)
- Dry-run date: `2026-04-20`
- Maintainer: `Codex`

## Repo State Checks

- Working tree clean: `yes`
- Current branch = `main`: `yes`
- `origin` configured: `yes`
- Local candidate identified: `yes`
- `origin/main` alignment checked: `yes`

## Version Consistency

- `pyproject.toml` version: `0.1.0`
- `src/scanbox/__init__.py` version: `0.1.0`
- Match / mismatch: `match`
- Blocking issue if mismatched: `none`

## Quick Gate

- Script: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1`
- Status: `PASS`
- Artifact path: `console output only`
- Summary: `OVERALL=PASS PASS=8 WARN=0 FAIL=0`
- Notes:
  - `Branch = PASS`
  - `Working tree = PASS`
  - `Origin remote = PASS`
  - `Origin main ref = PASS`
  - `HEAD alignment = PASS`
  - `Version sync = PASS`
  - `Workflow docs = PASS`
  - `Acceptance scripts = PASS`
  - `origin/main` alignment was checked against local refs only

## Baseline Gates

### `acceptance_v1.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v1\20260419T161538Z`
- Short note: v1 single-file baseline passed with `PASS=6 FAIL=0`.

### `acceptance_v2_quarantine.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v2-quarantine\20260419T161538Z`
- Short note: quarantine lifecycle baseline passed with `PASS=8 FAIL=0`.

### `acceptance_v2_directory.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v2-directory\20260419T161538Z`
- Short note: directory scanning baseline passed with `PASS=4 FAIL=0`.

## Recommended Checks

### `pytest -q`

- Executed: `yes`
- Status: `FAIL`
- Artifact path: `console output only`
- Summary: `33 passed, 49 errors, 2 warnings in 18.53s`
- Short note: fixture setup failed because `pytest` could not access `C:\Users\Lancelot\AppData\Local\Temp\pytest-of-Lancelot`.

### `verify_env.ps1`

- Executed: `not separately re-run`
- Status: `not separately re-run`
- Artifact path: `n/a`
- Summary: repo-mode verification already ran inside `acceptance_v1.ps1`; artifact-mode verification was recorded through `operator-consumption-validation.json`.

### Dependency repro entrypoints checked

- `docs/dependencies.md`: checked
- `docs/operations.md`: checked
- `docs/development.md`: checked
- Short note: maintainer-facing environment and packaged candidate entrypoints remain present and coherent with the current release workflow chain.

### Docs coherence checked

- `README.md`: checked
- `CHANGELOG.md`: checked
- `docs/demo.md`: checked
- milestone entrypoints: checked
- Short note: no coherence gap was found between repo entrypoints, milestone references, and the current packaged candidate discipline.

## Packaged Candidate Evidence

### Candidate evidence

- Packaged run directory: `reports\packaging-staging\20260419T161736Z`
- `assembly-record.json` path: `reports\packaging-staging\20260419T161736Z\assembly-record.json`
- `assembly-record.json` status: `generated`
- `smoke-check.json` path: `reports\packaging-staging\20260419T161736Z\smoke-check.json`
- `smoke-check.json` status: `PASS`
- Zip artifact path: `reports\packaging-staging\20260419T161736Z\scanbox-v0.1.0-windows-x64.zip`
- `artifact-fingerprint.json` path: `reports\packaging-staging\20260419T161736Z\artifact-fingerprint.json`
- `zip-check.json` path: `reports\packaging-staging\20260419T161736Z\zip-check.json`
- `zip-check.json` status: `PASS`
- `operator-consumption-validation.json` path: `reports\packaging-staging\20260419T161736Z\operator-consumption-validation.json`
- `operator-consumption-validation.json` status: `WARN`
- optional `zip-consistency-check.json` path: `reports\packaging-staging\20260419T161736Z\zip-consistency-check.json`
- optional `zip-consistency-check.json` status: `PASS`

### Disposable local diagnostics

- Staged artifact root: `reports\packaging-staging\20260419T161736Z\scanbox-v0.1.0-windows-x64`
- Unpacked operator validation directories: `reports\packaging-staging\20260419T161736Z\operator-consumption-unpacked-20260419T161916Z`
- Other temporary run-local diagnostics: `reports\packaging-staging\20260419T161736Z\operator-consumption-unpacked-20260419T161916Z\scanbox-v0.1.0-windows-x64\.local-temp`
- Short note: these local directories supported investigation only; they were not treated as separate evidence requirements.

## Packaged Candidate Interpretation

Packaged candidate overall is derived from fixed gates. It is not a free-form maintainer judgment.

Blocking gates:

- `verify_release_readiness.ps1`: `PASS`
- `acceptance_v1.ps1`: `PASS`
- `acceptance_v2_quarantine.ps1`: `PASS`
- `acceptance_v2_directory.ps1`: `PASS`
- staging verify: `PASS`
- zip verify: `PASS`
- operator consumption validation: `WARN`

Supportive optional evidence:

- `compare_packaged_zip_consistency.ps1`: `PASS`
- Baseline run: `reports\packaging-staging\20260419T082308Z`
- Candidate run: `reports\packaging-staging\20260419T161736Z`
- Short note: consistency compare was comparable under `normalized-zip-v1` and strengthened the evidence set without changing candidate derivation.

- Candidate overall: `WARN`
- Portability note:
  - `current workstation only`
  - `fallback-assisted diagnostic success`
  - `not a supported operator path PASS`
  - `not a formal support promise`
  - detail: `workstation_profile = maintainer_fallback_assisted`
  - fallback steps: `venv_without_pip`, `copy_base_site_packages`
  - portability gaps: `supported_path_venv_with_pip_unavailable`, `supported_path_runtime_dependency_install_unavailable`
- Blocking items: `none`
- Non-blocking follow-ups:
  - standalone `pytest -q` should be rechecked with a writable temp/cache path on this workstation
  - current workstation portability still depends on maintainer fallback for unpacked operator validation

## Baseline References

- v1
  - milestone: [scanbox-v1-freeze.md](milestones/scanbox-v1-freeze.md)
  - freeze tag: `scanbox-v1-freeze`
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
- v2.1
  - milestone: [scanbox-v2-quarantine.md](milestones/scanbox-v2-quarantine.md)
  - freeze tag: `scanbox-v2.1-quarantine`
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
- v2.2-A
  - milestone: [scanbox-v2.2-directory-mvp.md](milestones/scanbox-v2.2-directory-mvp.md)
  - freeze tag: `scanbox-v2.2-directory-mvp`
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`

Important boundary:

- freeze tags are historical baseline anchors
- planned semver tag `v0.1.0` in this document is a dry-run field only

## Roadmap Context

- Issue #1 through Issue #9 are completed and closed
- Issue #10 first step completed the packaged release-candidate execution discipline
- This document records the real packaged candidate rehearsal for Issue #10 second step

## Outcome

- Candidate overall: `WARN`
- Ready / not ready: `ready`
- Blocking items: `none`
- Non-blocking follow-ups:
  - standalone `pytest -q` currently fails on this machine because the default `pytest-of-Lancelot` temp root is not accessible
  - current workstation packaged operator validation still needs maintainer fallback, so the supported operator path is not yet `PASS`
