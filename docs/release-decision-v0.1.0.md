# Release Decision Record: v0.1.0

This is the first repo-tracked per-release decision record for the current `v0.1.0` formal release-prep path.

Use this record together with:

- [release-decision-boundary.md](release-decision-boundary.md)
- [release-notes-v0.1.0.md](release-notes-v0.1.0.md)
- [release-workflow.md](release-workflow.md)

## Current Decision

- target version: `0.1.0`
- target commit selection rule:
  - current `main` after this decision record and its companion repo-tracked release-notes record are present on `main`
  - replace this selection rule with an explicit commit SHA before any real semver tag, GitHub Release, or artifact publication action is authorized
- semver tag creation: deferred
- GitHub Release creation: deferred
- artifact publication: deferred

## What Is In Scope Now

The current decision allows:

- formal release decision work for `v0.1.0`
- a repo-tracked release-notes record for `v0.1.0`
- continued repository-centered release preparation against the current `main` branch
- baseline-aware review of whether a later decision update should authorize real release actions

The current decision does not yet authorize:

- real semver tag creation
- real GitHub Release creation
- real artifact publication

## Basis For This Decision

This decision is based on the current repository state:

- the local packaged candidate discipline is established
- the packaged candidate rehearsal helper exists
- the reviewer-facing handoff layer exists
- a clean/aligned happy-path packaged candidate `PASS` run exists
- the formal release decision boundary is already documented in [release-decision-boundary.md](release-decision-boundary.md)

These facts are sufficient to enter formal release decision work.

They are not, by themselves, sufficient to treat real release actions as already authorized.

## Boundary Reminders

Current local packaged candidate evidence remains maintainer-facing local evidence.

That means:

- `reports/` outputs are not converted into repo-tracked release contract
- supportive evidence is not promoted into blocking gates
- acceptance responsibilities remain unchanged
- current packaged candidate `PASS` is not itself a release publication authorization

## Next Required Repo-Tracked Records

Before any real semver tag, GitHub Release, or artifact publication action is authorized, the repo should still have:

- this per-release decision record
- one finalized repo-tracked release-notes record for `v0.1.0`

A later update to this decision record must explicitly state when any of the following become in-scope:

- semver tag creation
- GitHub Release creation
- artifact publication
