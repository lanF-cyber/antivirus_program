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

- Run `.\.venv\Scripts\python.exe -m pytest -q`.
- Run `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`.
- Re-check [dependencies.md](dependencies.md), [operations.md](operations.md), and [development.md](development.md) so a maintainer can still reproduce the local environment and dependency wiring.
- Re-check roadmap issue status against the planned release notes follow-ups.
- If the release changes the public presentation layer, confirm `README.md` and [demo.md](demo.md) still support a short walkthrough.

## Baseline-Aware Delivery

Release preparation is baseline-aware, not package-aware.

That means the release preparation flow should always reference:

- v1 scanning baseline
- v2.1 quarantine lifecycle baseline
- v2.2-A directory scanning baseline

Use the three baseline acceptance scripts as release gates, not as mixed feature sandboxes:

- `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
- `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`

Important boundary:

- acceptance scripts keep their current responsibilities
- this workflow does not require a real package artifact
- this workflow does not require a real GitHub Release
- this workflow does not require network publication to be considered complete

## Environment Repro Entry Points

For environment and dependency reproduction, use the existing repository entrypoints instead of inventing a separate large release-prep environment manual:

- [dependencies.md](dependencies.md)
- [operations.md](operations.md)
- [development.md](development.md)
- `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`

## Roadmap Context

Release notes and release prep should acknowledge the current roadmap context:

- [Issue #1: V2.2-B directory scanning enhancements](https://github.com/lanF-cyber/antivirus_program/issues/1)
- [Issue #2: V2.3 reporting and UX polish](https://github.com/lanF-cyber/antivirus_program/issues/2)
- [Issue #3: Future packaging and release workflow](https://github.com/lanF-cyber/antivirus_program/issues/3)

Use these references to make the release boundary clear:

- what is already covered by the frozen baselines
- what is already merged on `main`
- what still belongs to future follow-up work
