# Release Notes Template

This is a future release entry template. It does not replace [CHANGELOG.md](../CHANGELOG.md), and it does not imply that ScanBox is already on a formal semver release cadence.

## Release Version

- `vX.Y.Z`

## Release Commit

- `<commit-sha>`

## Release Tag

- `<release-tag>`

## Release Scope

- Briefly describe what this release includes.
- State whether the release is baseline-only, maintenance-focused, or feature-focused.

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

- `pytest`:
  - `<status>`
- `acceptance_v1.ps1`:
  - `<status>`
- `acceptance_v2_quarantine.ps1`:
  - `<status>`
- `acceptance_v2_directory.ps1`:
  - `<status>`

## Docs And Maintainer Notes

- Note any required README, demo, operations, development, or dependency updates.
- Note any local-environment caveats that a maintainer should know before reproducing the release candidate.

## Open Follow-Ups

- List any work intentionally not included in this release.
- Reference the relevant roadmap issues or follow-up tasks.
