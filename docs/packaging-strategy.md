# Packaging Strategy

This document defines the initial packaging and release artifact strategy for ScanBox. It is a design reference only. It does not create a package artifact, installer, tag, or GitHub Release.

## Current Reality

ScanBox is not a self-contained desktop application today.

Current runtime and maintenance assumptions are:

- Windows-first operation
- Python environment managed explicitly by the maintainer or operator
- repo-local runtime assets outside the Python package itself:
  - `config/`
  - `rules/`
  - `scripts/verify_env.ps1`
  - operator and maintainer docs
- explicit external dependencies for:
  - ClamAV executable
  - ClamAV database
  - capa executable
- acceptance and release-readiness helpers that are maintainer-facing, not operator-facing

`pyproject.toml` currently defines the Python package only. It does not yet define a complete runtime-asset packaging boundary for rules, config templates, PowerShell helpers, or external engine wiring.

That means the repository is currently release-ready at the workflow level, but not yet artifact-designed at the distribution level.

## Recommended Initial Distribution

### Primary recommendation

The initial formal ScanBox distribution should be:

- a **single-folder distribution**
- delivered as a **zip archive**

This means the first release artifact should be a transparent Windows-first directory tree that can be unpacked locally, reviewed by the operator, and installed or run using explicit documented steps.

It is intentionally not:

- an installer
- a single-file executable
- an opaque binary bundle
- a wheel-only distribution

### Why this is the right first step

This is the best fit for the current project state because:

- it matches the actual runtime surface better than a wheel-only artifact
- it keeps config, rules, and verification helpers visible
- it keeps external engine assumptions explicit instead of hiding them
- it is easier to debug when ClamAV or capa wiring is wrong
- it supports controlled-environment reproducibility better than a more heavily packaged form
- it does not overpromise system-level installation semantics too early

### Recommended shape

The first artifact should be a filtered operator-facing folder tree, packaged as a zip, with contents conceptually like:

```text
scanbox-vX.Y.Z/
  README.md
  pyproject.toml
  src/
  config/
    scanbox.toml
    clamav/
      freshclam.conf
  rules/
    yara/
    capa/
  scripts/
    verify_env.ps1
  docs/
    dependencies.md
```

This keeps the first artifact:

- transparent
- auditable
- reproducible
- close to the real runtime layout already used by the repository

## Alternatives And Trade-Offs

### Wheel only

Not recommended as the first formal distribution.

Reason:

- the current wheel boundary would not naturally carry the full runtime story for rules, config templates, PowerShell verification, and external engine expectations
- a wheel-only release would hide too much of the actual operator surface behind packaging assumptions that the repository does not yet enforce

### Source archive plus setup docs

Acceptable as a maintainer or reference artifact, but not as the primary operator-facing release shape.

Reason:

- it keeps repo-only and operator-facing content mixed together
- it does not make the artifact boundary clear
- it places unnecessary repository history and maintenance material into the operator path

### Zip-style runnable bundle

If this means a transparent folder-tree zip, it is effectively the recommended approach.

If this means a partially opaque runnable bundle, it should not be the first default.

Reason:

- the first release should optimize for transparency and diagnosability, not for concealment of runtime structure

### Single-folder distribution

Recommended.

Definition:

- one unpacked folder tree
- explicit files and subdirectories
- no system installer semantics
- no hidden bootstrap logic

### Single-file packaging candidate

Explicitly deferred.

Reason:

- current external engine dependencies remain path-sensitive
- ClamAV database handling remains external
- runtime temp and failure-diagnosis behavior are easier to reason about in a transparent folder tree
- single-file packaging would force a higher bar for determinism than the project currently has

## Artifact Boundary

### Should be included in the future release artifact

The first operator-facing artifact should include the ScanBox-owned runtime subset:

- installable runtime source:
  - `pyproject.toml`
  - `src/`
- default config templates:
  - `config/scanbox.toml`
  - `config/clamav/freshclam.conf`
- bundled rules and manifests:
  - `rules/yara/bundled/`
  - `rules/yara/manifest.json`
  - `rules/capa/bundled/`
  - `rules/capa/manifest.json`
- operator-facing verification helper:
  - `scripts/verify_env.ps1`
- operator-facing documentation:
  - `README.md`
  - `docs/dependencies.md`

This is the minimum coherent subset that reflects how ScanBox actually operates today.

### Should remain repo-only

These items should not be part of the first operator-facing artifact:

- `tests/`
- acceptance scripts:
  - `scripts/acceptance_v1.ps1`
  - `scripts/acceptance_v2_quarantine.ps1`
  - `scripts/acceptance_v2_directory.ps1`
- milestone freeze documents
- release workflow, release-prep, and release-notes template documents
- `scripts/verify_release_readiness.ps1`
- `reports/`
- maintainer-only planning and metadata materials

### Should not be bundled in the first artifact

These remain explicit external/operator-provided items:

- ClamAV executable
- ClamAV database
- capa executable
- workstation-specific override config:
  - `config/scanbox.local.toml`
  - `config/clamav/freshclam.local.conf`

Important boundary:

- the first artifact defines what ScanBox itself should carry
- it does not attempt to hide or auto-install third-party engine dependencies

## Windows-First Trade-Offs

The Windows-first constraint matters here.

For the current ScanBox maturity level, Windows users are better served by:

- an unpackable zip
- a visible folder tree
- explicit PowerShell helpers
- readable config and rules directories

They are not yet better served by:

- an installer
- registry-oriented system integration
- a one-click opaque executable bundle

This is a deliberate trade-off:

- less convenience than a polished installer
- better reproducibility
- better path transparency
- better debugging when external engines or rules are miswired

The current ClamAV and capa acquisition model is part of reality and should be acknowledged by the distribution design, not hidden by it.

## Future Implementation Backlog

### Phase A

- define the exact single-folder release tree
- define the operator-facing subset precisely
- define artifact naming and versioning conventions
- add an operator quickstart section tailored to the future artifact

### Phase B

- evaluate whether to also produce a wheel as a secondary maintainer artifact
- only do this after rules/config/runtime asset inclusion has been validated

### Phase C

- re-evaluate heavier distribution options:
  - refined runnable zip conventions
  - semi-automated external dependency bootstrap
  - single-file packaging only if runtime and path behavior become sufficiently deterministic

## Recommendation Summary

The initial ScanBox distribution strategy should be:

- **primary**: single-folder distribution delivered as a zip archive
- **secondary later**: optional wheel for maintainer-oriented workflows
- **deferred**: installer and single-file packaging

This gives ScanBox the lowest-risk path from repository-ready to artifact-ready while preserving the project's current strengths:

- reproducibility
- traceability
- explicit dependency control
- Windows-first operational clarity
