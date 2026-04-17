# Release Prep Dry-Run Worksheet

This file is the baseline release-prep worksheet and runbook.

Important use rule:

- keep this file as the repository baseline worksheet
- do not repeatedly overwrite it as the only historical record
- for an actual dry-run, copy this file and fill the copy
- or generate a new instance from this structure for each dry-run record

This worksheet supports baseline-aware release prep. It does not create a real release, real tag, or package artifact.

Recommended first step before filling a copied dry-run record:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_release_readiness.ps1
```

That helper is a quick local precheck only. It does not replace the final acceptance gates.

## Candidate

- Candidate version:
- Candidate commit:
- Planned semver tag:
- Dry-run date:
- Maintainer:

## Repo State Checks

- Working tree clean:
- Current branch = `main`:
- `origin` configured:
- Local candidate identified:
- `origin/main` alignment checked:

## Version Consistency

- `pyproject.toml` version:
- `src/scanbox/__init__.py` version:
- Match / mismatch:
- Blocking issue if mismatched:

## Baseline Gates

### `acceptance_v1.ps1`

- Status:
- Artifact path:
- Short note:

### `acceptance_v2_quarantine.ps1`

- Status:
- Artifact path:
- Short note:

### `acceptance_v2_directory.ps1`

- Status:
- Artifact path:
- Short note:

## Recommended Checks

### `pytest -q`

- Status:
- Artifact path:
- Short note:

### `verify_env.ps1`

- Status:
- Artifact path:
- Short note:

### Dependency repro entrypoints checked

- `docs/dependencies.md`:
- `docs/operations.md`:
- `docs/development.md`:
- Short note:

### Docs coherence checked

- `README.md`:
- `CHANGELOG.md`:
- `docs/demo.md`:
- milestone entrypoints:
- Short note:

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
- planned semver tags in this worksheet are dry-run fields only unless a real release step is explicitly taken later

## Roadmap Context

- Issue #1: V2.2-B directory scanning enhancements
- Issue #2: V2.3 reporting and UX polish
- Issue #3: Future packaging and release workflow

## Outcome

- Ready / not ready:
- Blocking items:
- Non-blocking follow-ups:
