# Release Workflow

This document defines the minimum ScanBox release and maintenance workflow. It is intentionally repository-centered: no GUI packaging, installer work, release bundles, or network publishing actions are part of this baseline.

Important boundary:

- freeze tags are historical baseline anchors
- future semver tags are the formal release tags
- this workflow baseline does not mean ScanBox has already started a formal semver release cadence

## Purpose

Use this workflow when the goal is to prepare a clean, traceable repository release candidate from the current `main` branch.

This workflow is for:

- versioning discipline
- baseline-aware release preparation
- release notes preparation
- maintainer handoff and traceability

This workflow is not for:

- GUI packaging
- installers
- standalone release bundles
- implicit downloads
- network publishing or GitHub Release automation

## Source Of Truth

### Version source

When changing the project version, update these two files together in the same change:

- `pyproject.toml`
- `src/scanbox/__init__.py`

The release checklist must treat mismatches between these two files as a blocking issue.

### Baseline source

Current baseline anchors are:

- v1:
  - milestone: [scanbox-v1-freeze.md](milestones/scanbox-v1-freeze.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
  - freeze tag: `scanbox-v1-freeze`
- v2.1:
  - milestone: [scanbox-v2-quarantine.md](milestones/scanbox-v2-quarantine.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
  - freeze tag: `scanbox-v2.1-quarantine`
- v2.2-A:
  - milestone: [scanbox-v2.2-directory-mvp.md](milestones/scanbox-v2.2-directory-mvp.md)
  - acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`
  - freeze tag: `scanbox-v2.2-directory-mvp`

### Release candidate source

The default release candidate source is:

- local `main`
- aligned with `origin/main`

## Versioning And Tagging Convention

Use two separate tag families:

- freeze tags
  - historical baseline anchors
  - not rewritten
  - not reused as formal release tags
- semver tags
  - future formal release tags
  - format: `vX.Y.Z`

Current freeze tags:

- `scanbox-v1-freeze`
- `scanbox-v2.1-quarantine`
- `scanbox-v2.2-directory-mvp`

These existing tags are not semver release tags.

This workflow only establishes the future semver convention. It does not create a new tag by itself.

## Release Checklist

### Required Before Release

- Working tree is clean.
- Current branch is `main`.
- Local HEAD is aligned with `origin/main`.
- Version is updated consistently in:
  - `pyproject.toml`
  - `src/scanbox/__init__.py`
- The three baseline acceptance entrypoints are still the release gates and keep their existing responsibilities:
  - `acceptance_v1.ps1`
  - `acceptance_v2_quarantine.ps1`
  - `acceptance_v2_directory.ps1`
- `README.md`, `CHANGELOG.md`, [demo.md](demo.md), and the milestone entrypoints still agree on the current project state.
- Release notes are prepared from [release-notes-template.md](release-notes-template.md).
- The intended release commit and release tag are explicitly chosen before tagging or publishing anything.

### Recommended Before Release

- Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_standalone_pytest.ps1`.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`.
- Re-check [dependencies.md](dependencies.md), [operations.md](operations.md), and [development.md](development.md) so a maintainer can still reproduce the local environment and dependency wiring.
- Re-check roadmap issue status against the planned release notes follow-ups.
- If the release changes the public presentation layer, confirm `README.md` and [demo.md](demo.md) still support a short walkthrough.

Standalone pytest remains a recommended check only. It is not a new blocking gate.

Current standalone pytest note:

- the helper is the hardened preferred path for standalone pytest
- the raw `.\.venv\Scripts\python.exe -m pytest -q` command remains available as a lower-level direct command
- the raw command may still work, but it is not the preferred mitigated entrypoint
- helper output under `reports/pytest-standalone/<timestamp>/` is disposable local state only

## Release Prep Dry-Run

Use a dry-run when the goal is to rehearse release prep without creating a real tag, a formal published package artifact, or a real GitHub Release.

Dry-run goals:

- rehearse release prep
- re-check the baseline gates
- produce a traceable release candidate record

Dry-run boundaries:

- no installer work
- no formal published package artifact
- no real tag creation
- no real GitHub Release publication
- local packaged candidate evidence may still be produced when the rehearsal explicitly includes the packaged candidate flow

Dry-run repo checks should always include:

- candidate branch is `main`
- candidate source is checked against `origin/main`
- version consistency is checked in:
  - `pyproject.toml`
  - `src/scanbox/__init__.py`
- the three baseline acceptance scripts remain the baseline gates with their existing responsibilities

Use these companion documents:

- [release-prep-dry-run.md](release-prep-dry-run.md)
  - baseline worksheet and runbook
- [release-notes-dry-run-example.md](release-notes-dry-run-example.md)
  - worked dry-run example
- [release-notes-template.md](release-notes-template.md)
  - reusable future release entry template
- [release-decision-boundary.md](release-decision-boundary.md)  # <- added short cross-reference

Before a larger dry-run or final release prep pass, start with the quick local readiness precheck:

- `powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1`

Important boundary:

- this helper is a release prep quick gate / readiness precheck
- it is not a substitute for the acceptance scripts
- it checks `origin/main` alignment against local refs only
- it does not fetch, tag, publish, or modify repository state