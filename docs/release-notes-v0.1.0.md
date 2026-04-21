# Release Notes: v0.1.0

This is the first repo-tracked release-notes record for the current `v0.1.0` formal release-prep path.

Use this record together with:

- [release-decision-boundary.md](release-decision-boundary.md)
- [release-decision-v0.1.0.md](release-decision-v0.1.0.md)
- [release-workflow.md](release-workflow.md)

## Release Version

- `0.1.0`

## Release Commit

- target commit selection rule:
  - current `main` after this release-notes record and the companion per-release decision record are present on `main`
  - replace this rule with a concrete SHA before any real semver tag, GitHub Release, or artifact publication

## Release Tag

- deferred: not yet authorized

## Release Scope

- Covers the currently frozen baseline anchors:
  - v1 scanning baseline
  - v2.1 quarantine lifecycle baseline
  - v2.2-A directory scanning baseline
- Includes merged follow-up work:
  - V2.2-B directory filtering, accounting, and configurable filter handling
  - V2.3 reporting and UX polish work
- Includes Issue #3 step 1 release workflow documentation baseline

## Validation

- `pytest`: dry-run example status pending explicit execution
- `acceptance_v1.ps1`: dry-run example status pending explicit execution
- `acceptance_v2_quarantine.ps1`: dry-run example status pending explicit execution
- `acceptance_v2_directory.ps1`: dry-run example status pending explicit execution

## Docs And Maintainer Notes

- Use [release-workflow.md](release-workflow.md) as the release-prep source of truth
- Use [release-prep-dry-run.md](release-prep-dry-run.md) as the baseline worksheet/runbook
- Use [release-notes-template.md](release-notes-template.md) when creating a new release entry after a real release decision
- Re-check maintainer environment and dependency references before a real release step:
  - [dependencies.md](dependencies.md)
  - [operations.md](operations.md)
  - [development.md](development.md)

## Open Follow-Ups

- installer work remains out of scope
- packaging artifacts remain out of scope
- real semver tagging remains out of scope
- real GitHub Release publication remains out of scope
- future release automation remains out of scope
