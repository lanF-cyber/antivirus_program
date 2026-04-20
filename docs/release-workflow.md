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
- the three acceptance scripts remain the baseline gates:
  - `acceptance_v1.ps1`
  - `acceptance_v2_quarantine.ps1`
  - `acceptance_v2_directory.ps1`

Use these companion documents:

- [release-prep-dry-run.md](release-prep-dry-run.md)
  - baseline worksheet and runbook
- [release-notes-dry-run-example.md](release-notes-dry-run-example.md)
  - worked dry-run example
- [release-notes-template.md](release-notes-template.md)
  - reusable future release entry template

Before a larger dry-run or final release prep pass, start with the quick local readiness precheck:

- `powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1`

Important boundary:

- this helper is a release prep quick gate / readiness precheck
- it is not a substitute for the acceptance scripts
- it checks `origin/main` alignment against local refs only
- it does not fetch, tag, publish, or modify repository state

## Packaged Release Candidate Execution

Use this flow when the goal is to produce a maintainer-facing packaged release candidate from the current repository state and record a traceable local evidence set.

Important boundary:

- this is a local packaged candidate discipline
- it does not publish a GitHub Release
- it does not create an installer
- it does not change acceptance responsibilities
- it does not expand the artifact contract

For artifact boundary, operator subset, and portability policy, use:

- [packaging-strategy.md](packaging-strategy.md)

For the individual local command entrypoints, use:

- [development.md](development.md)

### Preconditions

The packaged candidate flow assumes:

- working tree is clean
- current branch is `main`
- local HEAD is aligned with `origin/main`
- version is consistent in:
  - `pyproject.toml`
  - `src/scanbox/__init__.py`
- the three baseline acceptance scripts remain the baseline gates with their existing responsibilities

### Execution Order

Run the packaged candidate flow in this order:

1. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1`
2. `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
3. `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
4. `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`
5. `powershell -ExecutionPolicy Bypass -File .\scripts\assemble_packaging_staging_tree.ps1`
6. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_packaging_staging_tree.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>`
7. `powershell -ExecutionPolicy Bypass -File .\scripts\package_packaging_staging_tree.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>`
8. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_packaged_zip_artifact.ps1 -RunDirectory .\reports\packaging-staging\<timestamp>`
9. optional `powershell -ExecutionPolicy Bypass -File .\scripts\compare_packaged_zip_consistency.ps1 -BaselineRunDirectory .\reports\packaging-staging\<baseline-timestamp> -CandidateRunDirectory .\reports\packaging-staging\<timestamp>`
10. `powershell -ExecutionPolicy Bypass -File .\scripts\validate_operator_zip_consumption.ps1 -RunDirectory .\reports\packaging-staging\<timestamp> -BasePythonExe .\.venv\Scripts\python.exe`

For a maintainer-facing convenience wrapper around the same flow, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_packaged_candidate_rehearsal.ps1 -BasePythonExe .\.venv\Scripts\python.exe
```

This helper:

- preserves the same blocking gates and fixed candidate derivation
- does not replace the underlying evidence files
- writes a concise disposable evidence index under `reports/packaged-candidate-rehearsal/<timestamp>/packaged-candidate-evidence-index.json`
- does not elevate optional supportive evidence into a new blocking gate

Step-specific preconditions:

- `verify_release_readiness.ps1`
  - packaged candidate source has been selected
- the three baseline acceptance scripts
  - readiness precheck is already reviewed
- `assemble_packaging_staging_tree.ps1`
  - manifest and version sources are consistent
- `verify_packaging_staging_tree.ps1`
  - `assembly-record.json` exists for the target run
- `package_packaging_staging_tree.ps1`
  - staging verify overall = `PASS`
- `verify_packaged_zip_artifact.ps1`
  - zip artifact and `artifact-fingerprint.json` exist
- `compare_packaged_zip_consistency.ps1`
  - optional
  - only when a comparable prior run exists
  - both runs already have zip verify overall = `PASS`
- `validate_operator_zip_consumption.ps1`
  - zip verify overall = `PASS`
  - maintainer supplies `-BasePythonExe`

### Gate Types

These are the packaged candidate gates:

- blocking gates
  - `verify_release_readiness.ps1`
  - `acceptance_v1.ps1`
  - `acceptance_v2_quarantine.ps1`
  - `acceptance_v2_directory.ps1`
  - staging verify
  - zip verify
  - operator consumption validation
- optional supportive evidence
  - `compare_packaged_zip_consistency.ps1`

Important interpretation rules:

- `verify_release_readiness.ps1` and the three baseline acceptance scripts remain blocking gates
- later packaging evidence does not weaken those gates
- consistency compare is optional
- a missing consistency compare result does not downgrade the candidate
- a consistency compare `PASS` only strengthens the evidence set
- consistency compare does not become a new blocking gate here

### Candidate Evidence

Required candidate evidence-bearing outputs are:

- packaged run directory
- `assembly-record.json`
- `smoke-check.json`
- zip artifact
- `artifact-fingerprint.json`
- `zip-check.json`
- `operator-consumption-validation.json`

Optional supportive evidence is:

- `zip-consistency-check.json`

Disposable local diagnostics may still exist inside the same run, for example:

- staged artifact root
- unpacked operator validation directories
- other temporary local workspaces under the run directory

These diagnostics are disposable local state. They can support investigation, but they are not separate candidate evidence requirements.

### Packaged Candidate Success Criteria

Packaged candidate overall is derived only from the fixed gate combination below. It is not a free-form maintainer judgment.

- candidate overall = `FAIL`
  - if any blocking gate is `FAIL`
- candidate overall = `WARN`
  - only if all blocking gates before operator validation are `PASS`
  - and `operator-consumption-validation.json` overall = `WARN`
- candidate overall = `PASS`
  - only if all blocking gates are `PASS`
  - and `operator-consumption-validation.json` overall = `PASS`

Explicit operator validation rules:

- `operator-consumption-validation.json` overall = `WARN`
  - packaged candidate overall must be `WARN`
- `operator-consumption-validation.json` overall = `FAIL`
  - packaged candidate overall must be `FAIL`

Portability interpretation boundary:

- operator validation `WARN` means the current workstation achieved fallback-assisted diagnostic success
- it does not mean the supported operator path passed
- it does not create a formal support promise

## Baseline-Aware Delivery

Release preparation is baseline-aware first. Packaged candidate execution is an additional maintainer-facing evidence flow, not a replacement for the baseline gates.

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
- this workflow does not require a formal published package artifact
- this workflow does not require a real GitHub Release
- this workflow does not require network publication to be considered complete

For future distribution and artifact-boundary design, use:

- [packaging-strategy.md](packaging-strategy.md)

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
