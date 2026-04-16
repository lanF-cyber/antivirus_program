# Release Notes Dry-Run Example

Dry-run example only.

- no real release created
- no tag created
- no GitHub Release published

## Release Version

- `0.1.0`

## Release Commit

- `23c30ec9d4204d35100c1297a9469ef60c6d6247`

## Release Tag

- Planned semver tag only: `v0.1.0`

## Release Scope

- Covers the currently frozen baseline anchors:
  - v1 scanning baseline
  - v2.1 quarantine lifecycle baseline
  - v2.2-A directory scanning baseline
- Includes the currently merged V2.2-B follow-up work on directory filtering, accounting, and configurable filter handling.
- Includes the currently merged V2.3 reporting and UX polish work on issue wording and focused default output.
- Includes Issue #3 step 1 release workflow documentation baseline:
  - [release-workflow.md](release-workflow.md)
  - [release-notes-template.md](release-notes-template.md)

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

- `pytest`
  - dry-run example status: pending explicit execution
- `acceptance_v1.ps1`
  - dry-run example status: pending explicit execution
- `acceptance_v2_quarantine.ps1`
  - dry-run example status: pending explicit execution
- `acceptance_v2_directory.ps1`
  - dry-run example status: pending explicit execution

## Docs And Maintainer Notes

- Use [release-workflow.md](release-workflow.md) as the release-prep source of truth.
- Use [release-prep-dry-run.md](release-prep-dry-run.md) as the baseline worksheet/runbook.
- Use [release-notes-template.md](release-notes-template.md) when creating a new release entry after a real release decision.
- Re-check maintainer environment and dependency references before a real release step:
  - [dependencies.md](dependencies.md)
  - [operations.md](operations.md)
  - [development.md](development.md)

## Open Follow-Ups

- installer work remains out of scope
- packaging artifacts remain out of scope
- real semver tagging remains out of scope in this dry-run
- real GitHub Release publication remains out of scope
- future release automation remains out of scope
