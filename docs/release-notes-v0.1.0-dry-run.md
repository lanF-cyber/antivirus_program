# v0.1.0 Release Notes Dry-Run

> Dry-run only.
> No real tag created.
> No GitHub Release published.

This document is a release-notes dry-run entry for the `v0.1.0` release candidate. It records the current repository state without creating a formal release.

## Release Version

- `0.1.0`

## Release Commit

- `451250ca27de763c4ab210ef5379729256e8657e`

## Release Tag

- Planned tag: `v0.1.0`
- Status: dry-run only, not created

## Release Scope

- Baseline-aware release candidate dry-run covering the current frozen ScanBox baselines:
  - v1 single-file scanning baseline
  - v2.1 quarantine lifecycle baseline
  - v2.2-A directory scanning baseline
- Includes the already completed maintainer and product-adjacent follow-up work merged to `main` through:
  - Issue #1: V2.2-B directory scanning enhancements
  - Issue #2: V2.3 reporting and UX polish
  - Issue #3: future packaging and release workflow groundwork
- This entry does not treat Issue #4 as a shipped product feature; Issue #4 is only the dry-run workflow validation step for this candidate.

## Baseline References

- v1 baseline
  - freeze tag: `scanbox-v1-freeze`
  - milestone: [scanbox-v1-freeze.md](milestones/scanbox-v1-freeze.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
- v2.1 baseline
  - freeze tag: `scanbox-v2.1-quarantine`
  - milestone: [scanbox-v2-quarantine.md](milestones/scanbox-v2-quarantine.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
- v2.2-A baseline
  - freeze tag: `scanbox-v2.2-directory-mvp`
  - milestone: [scanbox-v2.2-directory-mvp.md](milestones/scanbox-v2.2-directory-mvp.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`

## Validation

- `verify_release_readiness.ps1`:
  - `PASS`
  - `OVERALL=PASS PASS=8 WARN=0 FAIL=0`
  - `origin/main` alignment was checked against local refs only.
- `pytest -q`:
  - `PASS`
  - `82 passed in 34.60s`
- `acceptance_v1.ps1`:
  - `PASS`
  - artifacts: `reports\acceptance-v1\20260417T045124Z`
  - note: single-file baseline matched expectation with `PASS=6 FAIL=0`
- `acceptance_v2_quarantine.ps1`:
  - `PASS`
  - artifacts: `reports\acceptance-v2-quarantine\20260417T045237Z`
  - note: quarantine lifecycle baseline matched expectation with `PASS=8 FAIL=0`
- `acceptance_v2_directory.ps1`:
  - `PASS`
  - artifacts: `reports\acceptance-v2-directory\20260417T045406Z`
  - note: directory baseline matched expectation with `PASS=4 FAIL=0`

## Docs And Maintainer Notes

- Release workflow entrypoint: [release-workflow.md](release-workflow.md)
- Baseline worksheet/runbook: [release-prep-dry-run.md](release-prep-dry-run.md)
- Historical dry-run example: [release-notes-dry-run-example.md](release-notes-dry-run-example.md)
- Environment and maintainer references:
  - [dependencies.md](dependencies.md)
  - [operations.md](operations.md)
  - [development.md](development.md)
- No release workflow entry gap was found during this dry-run, so `README.md` and `CHANGELOG.md` were left unchanged.

## Open Follow-Ups

- real semver tag creation is still not performed in this dry-run
- GitHub Release publication is still not performed in this dry-run
- packaging artifacts and installer flow remain future work
- release automation beyond the current quick gate and documentation chain remains future work
