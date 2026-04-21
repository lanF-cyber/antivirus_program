# Formal Release Decision Boundary

## Purpose

This document defines the repo-tracked policy boundary between:

- current local packaged candidate discipline
- formal semver release decision
- release notes finalization
- semver tag creation
- GitHub Release creation
- artifact publication

This is a policy boundary document. It is not a release execution record.

## Current State

The repository currently has:

- an established local packaged candidate discipline
- a packaged candidate rehearsal helper
- a reviewer-facing handoff layer
- a clean/aligned happy-path packaged candidate `PASS` run

Current packaged candidate evidence remains local disposable output. It is not converted into a repo-tracked release contract by its existence.

## Decision Boundary

The following terms remain separate decision surfaces:

- current local packaged candidate discipline
  - maintainer-facing validation discipline
  - local evidence only
- formal semver release decision
  - repo-tracked decision to consider a specific version and commit for formal release execution
- release notes finalization
  - repo-tracked content finalization step for a specific release candidate
- semver tag creation
  - explicit release action
  - not implied by packaged candidate `PASS`
- GitHub Release creation
  - explicit release action
  - separate from semver tag creation
- artifact publication
  - explicit release action
  - separate from both semver tag creation and GitHub Release creation

Current packaged candidate `PASS` does not expand the artifact contract.

Current packaged candidate `PASS` does not promote supportive evidence into blocking gates.

Current packaged candidate `PASS` does not change acceptance script responsibilities.

## Current Conclusion

ScanBox can enter formal release decision work now.

This does not mean it is already authorized to tag, publish a GitHub Release, or publish an artifact.

The current packaged candidate `PASS` means:

- the maintainer-facing local packaged candidate discipline is real and repeatable
- it is not an artifact-contract expansion
- it is not a conversion of `reports/` outputs into repo-tracked release contract
- it is not a promotion of supportive evidence into blocking gates
- it is not a change to acceptance script responsibilities

Current repo-tracked records for the active `v0.1.0` formal release-prep path are:

- [release-decision-v0.1.0.md](release-decision-v0.1.0.md)
- [release-notes-v0.1.0.md](release-notes-v0.1.0.md)

## Minimum Repo-Tracked Prerequisites Before Real Release Action

Actual release execution still requires:

- one per-release decision record
- one finalized repo-tracked release-notes record

The per-release decision record must explicitly state:

- version
- target commit
- whether semver tag creation is in-scope
- whether GitHub Release creation is in-scope
- whether artifact publication is in-scope
- whether any of those actions are intentionally deferred

Execution-prep boundary:

- entering formal release decision work is allowed now
- actual release execution still requires an explicit per-release decision record
- semver tag, GitHub Release, and artifact publication remain separable actions and must be explicitly chosen

## Non-Goals

- no installer
- no artifact-contract expansion
- no automatic GitHub Release publishing
- no automatic semver tag creation
- no acceptance responsibility changes
