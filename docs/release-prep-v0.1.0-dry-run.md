# v0.1.0 Release Prep Dry-Run

> Dry-run only.
> No real tag created.
> No GitHub Release published.

This document is the completed release-prep record for the `v0.1.0` release candidate dry-run. It is an instance record, not the repository baseline worksheet.

## Candidate

- Candidate version: `0.1.0`
- Candidate commit: `451250ca27de763c4ab210ef5379729256e8657e`
- Planned semver tag: `v0.1.0` (`dry-run only`)
- Dry-run date: `2026-04-17`
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
  - `origin/main` alignment was checked against local refs only.

## Baseline Gates

### `acceptance_v1.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v1\20260417T045124Z`
- Short note: v1 single-file baseline passed with `PASS=6 FAIL=0`.

### `acceptance_v2_quarantine.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v2-quarantine\20260417T045237Z`
- Short note: quarantine lifecycle baseline passed with `PASS=8 FAIL=0`.

### `acceptance_v2_directory.ps1`

- Status: `PASS`
- Artifact path: `reports\acceptance-v2-directory\20260417T045406Z`
- Short note: directory scanning baseline passed with `PASS=4 FAIL=0`.

## Recommended Checks

### `pytest -q`

- Status: `PASS`
- Artifact path: console output only
- Short note: `82 passed in 34.60s`.

### `verify_env.ps1`

- Status: not re-run in this dry-run
- Artifact path: n/a
- Short note: environment verification remains part of the documented maintainer workflow, but the quick gate and acceptance runs were sufficient for this dry-run closure.

### Dependency repro entrypoints checked

- `docs/dependencies.md`: checked as workflow entrypoint
- `docs/operations.md`: checked as workflow entrypoint
- `docs/development.md`: checked as workflow entrypoint
- Short note: maintainer-facing environment and workflow entrypoints remain present and consistent with the current release workflow chain.

### Docs coherence checked

- `README.md`: checked
- `CHANGELOG.md`: checked
- `docs/demo.md`: checked by reference only
- milestone entrypoints: checked
- Short note: no release workflow entry gap was found; no documentation patch was required outside the new dry-run instance files.

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

- Issue #1: completed and closed
- Issue #2: completed and closed
- Issue #3: completed and closed

This dry-run confirms that the current release workflow can represent the already completed work without requiring a real tag, GitHub Release, or packaging artifact.

## Outcome

- Ready / not ready: `ready`
- Blocking items: `none`
- Non-blocking follow-ups:
  - real semver tag creation remains out of scope for this dry-run
  - GitHub Release publication remains out of scope for this dry-run
  - packaging artifacts and installer flow remain future follow-up work
