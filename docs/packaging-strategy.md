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

The first artifact should be a filtered operator-facing folder tree, packaged as a zip.

The concrete artifact-era path structure is defined in the `Future Release Tree` section below.

This keeps the first artifact:

- transparent
- auditable
- reproducible
- close to the real runtime layout already used by the repository

## Future Release Tree

The future artifact needs two separate concepts:

- **repo layout**
  - the current development repository structure
- **artifact layout**
  - the operator-facing directory tree inside the future release zip

These are related, but they are not the same thing.

Important boundary:

- the future artifact must not be treated as a raw zip of the repository root
- the current repo `src/scanbox/` path is only the source location today
- the artifact should expose a filtered, operator-facing tree with stable and readable paths
- this design step does not promise that `src/scanbox/` will remain the final operator-visible runtime path inside the artifact

### Proposed logical artifact root

```text
scanbox-vX.Y.Z-windows-x64/
  README.md
  QUICKSTART.md
  requirements.txt
  pyproject.toml
  runtime/
    scanbox/
  config/
    scanbox.toml
    clamav/
      freshclam.conf
  rules/
    yara/
      bundled/
      manifest.json
    capa/
      bundled/
      manifest.json
  scripts/
    verify_env.ps1
    run_scanbox.ps1
  docs/
    dependencies.md
```

### Path interpretation

- `runtime/scanbox/`
  - this is the **artifact-era logical runtime location**
  - it is not a hard promise that the artifact must expose the repo's `src/scanbox/` path directly
- `config/`
  - this carries operator-visible default config templates only
- `rules/`
  - this carries the bundled rule subsets and manifests needed for runtime behavior
- `scripts/verify_env.ps1`
  - this remains the operator-facing verification entrypoint
- `scripts/run_scanbox.ps1`
  - this is the operator-facing launcher for unpacked artifact use
- `docs/dependencies.md`
  - this is a selective operator doc include, not a signal that the full `docs/` tree belongs in the artifact

### Repo layout to artifact layout mapping

This future mapping should be explicit:

- repo source subtree
  - `src/scanbox/`
- future artifact runtime subtree
  - `runtime/scanbox/`

That mapping is a packaging concern, not a reason to expose the repository source layout as the final artifact contract.

## Artifact Assembly Spec

The future packaging flow should treat artifact assembly as an explicit mapping step:

- input:
  - selected repo content
- transformation:
  - repo-layout to artifact-layout mapping
- output:
  - a staged artifact tree rooted at `scanbox-vX.Y.Z-windows-x64/`

It must not treat the repository root as a directly shippable folder.

### Assembly boundary

The future artifact should be assembled as a filtered operator-facing tree.

- `runtime/scanbox/`
  - this is the **artifact-internal runtime path**
  - it does **not** change the Python import contract
  - it does **not** promise that repo `src/scanbox/` is the final operator-visible runtime path
- `config/`
  - this carries default operator-facing config templates only
- `rules/`
  - this carries bundled runtime rule content plus rule manifests
- `scripts/verify_env.ps1`
  - this remains the operator-facing verification helper
- `docs/dependencies.md`
  - this remains a selective operator-facing docs include
- `pyproject.toml`
  - this is included for version metadata visibility, release traceability, and artifact/source correlation
  - it is not a runtime-critical file for normal operator execution

### Required assembly mappings

The initial explicit mapping set should be:

| Repo source | Artifact destination | Why it is copied |
| --- | --- | --- |
| `README.md` | `README.md` | top-level operator entrypoint |
| `QUICKSTART.md` | `QUICKSTART.md` | operator-facing unpacked artifact quickstart |
| `requirements.txt` | `requirements.txt` | runtime-only Python dependency entrypoint |
| `pyproject.toml` | `pyproject.toml` | version metadata visibility and traceability |
| `src/scanbox/` | `runtime/scanbox/` | artifact-internal runtime subset |
| `config/scanbox.toml` | `config/scanbox.toml` | default config template |
| `config/clamav/freshclam.conf` | `config/clamav/freshclam.conf` | default freshclam template |
| `rules/yara/bundled/` | `rules/yara/bundled/` | bundled YARA runtime content |
| `rules/yara/manifest.json` | `rules/yara/manifest.json` | YARA rule metadata |
| `rules/capa/bundled/` | `rules/capa/bundled/` | bundled capa runtime content |
| `rules/capa/manifest.json` | `rules/capa/manifest.json` | capa rule metadata |
| `scripts/verify_env.ps1` | `scripts/verify_env.ps1` | operator-facing verification helper |
| `scripts/run_scanbox.ps1` | `scripts/run_scanbox.ps1` | operator-facing unpacked artifact launcher |
| `docs/dependencies.md` | `docs/dependencies.md` | operator-facing dependency/setup reference |

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

## Artifact Manifest Boundary

The future single-folder artifact should use a filtered manifest model rather than a whole-repo copy model.

### Included in the first artifact

| Artifact-era path | Source of truth today | Inclusion status | Notes |
| --- | --- | --- | --- |
| `README.md` | repo root | include | operator-facing top-level entrypoint |
| `QUICKSTART.md` | repo root | include | operator-facing unpacked artifact quickstart |
| `requirements.txt` | repo root | include | runtime-only Python dependency entrypoint |
| `pyproject.toml` | repo root | include | version metadata visibility and release traceability |
| `runtime/scanbox/` | `src/scanbox/` | include | artifact-era runtime subset, not a direct repo-path contract |
| `config/scanbox.toml` | `config/scanbox.toml` | include | default config template |
| `config/clamav/freshclam.conf` | `config/clamav/freshclam.conf` | include | default freshclam template |
| `rules/yara/bundled/` | `rules/yara/bundled/` | include | bundled YARA rules |
| `rules/yara/manifest.json` | `rules/yara/manifest.json` | include | bundled YARA metadata |
| `rules/capa/bundled/` | `rules/capa/bundled/` | include | bundled capa rules subset |
| `rules/capa/manifest.json` | `rules/capa/manifest.json` | include | bundled capa metadata |
| `scripts/verify_env.ps1` | `scripts/verify_env.ps1` | include | operator-facing verification helper |
| `scripts/run_scanbox.ps1` | `scripts/run_scanbox.ps1` | include | operator-facing unpacked artifact launcher |
| `docs/dependencies.md` | `docs/dependencies.md` | include | operator-facing docs subset only |

Important documentation boundary:

- `docs/dependencies.md` entering the artifact means **selective doc inclusion**
- it does **not** mean the entire `docs/` tree enters the artifact
- the future artifact should carry only the operator-facing docs subset that supports setup and verification

### Repo-only

| Path class | Status | Reason |
| --- | --- | --- |
| `tests/` | repo-only | maintainer validation, not operator runtime |
| acceptance scripts | repo-only | baseline gates remain maintainer-facing |
| milestone freeze docs | repo-only | historical baseline anchors |
| release workflow and dry-run docs | repo-only | maintainer release process only |
| `scripts/verify_release_readiness.ps1` | repo-only | maintainer readiness precheck |
| `reports/` | repo-only | local run artifacts only |
| `.git/` and repo management metadata | repo-only | source-control material is not part of the artifact contract |
| `.venv/` | repo-only | local environment only |
| `__pycache__/` and `*.pyc` | repo-only | transient Python cache content |
| maintainer metadata and planning docs | repo-only | not operator-facing runtime material |

### External and not bundled

| Dependency class | Status | Reason |
| --- | --- | --- |
| ClamAV executable | external | third-party runtime dependency |
| ClamAV database | external | operator-provided / workstation-provided runtime data |
| capa executable | external | third-party runtime dependency |
| `config/scanbox.local.toml` | external/local only | workstation-specific override |
| `config/clamav/freshclam.local.conf` | external/local only | workstation-specific override |

The first single-folder distribution explicitly does **not** promise:

- automatic acquisition of external dependencies
- automatic discovery of external dependencies
- automatic database download
- automatic writing of workstation-local override config
- automatic external engine bootstrap

Those actions remain outside the first artifact contract.

### Vendored third-party notices policy

The future artifact should treat third-party notices conservatively:

- vendored third-party notices and license files should be retained
- retaining license and notice material takes priority over small size reductions
- repo-service metadata such as `.github/` may be excluded
- vendored `README.md` files may be treated as an implementation choice, but they do not outrank license or notice retention

## Manifest Generation Design

Future packaging should be driven by a maintainer-side manifest model rather than by ad hoc copy rules.

Current prototype note:

- `packaging/packaging-manifest.json` is the repo-tracked maintainer-side assembly source of truth for the staging-tree prototype
- it does not belong to the future operator-facing artifact contract

Current local zip prototype note:

- the maintainer-side local zip prototype now targets a deterministic profile named `normalized-zip-v1`
- this is a local consistency-tightening measure for repeatable prototype output
- it is not a public reproducible-build commitment for a future formal release artifact

Current operator-path note:

- the current operator-facing quickstart path is intentionally a `YARA-only first run`
- it exists to validate unpacked artifact consumption without requiring immediate ClamAV or capa wiring
- it does not replace the fuller external dependency setup described in `docs/dependencies.md`
- maintainer-side validation may use local fallbacks to continue diagnosing portability gaps
- those fallbacks are not part of the operator-facing artifact contract

### Manifest rule shape

Include entries should be defined with:

- `source`
- `destination`
- `kind`
  - `file`
  - `directory`
- `required`
- `notes`

Exclude entries should be defined with:

- `pattern`
- `scope`
- `reason`

### Rule priority

The future assembly implementation should use this fixed priority order:

1. **Hard excludes first**
- external-not-bundled content must never enter the artifact
- maintainer-only content must never enter the artifact

2. **Scoped excludes override broad includes**
- excludes inside an included directory take priority over directory-level includes
- example:
  - `rules/capa/bundled/` may be included as a subtree
  - `.github/` inside that subtree still remains excluded

3. **Explicit include mappings are applied after excludes are resolved**
- only explicitly mapped content is eligible for the artifact

4. **Anything not explicitly included is excluded by default**
- the assembly policy is allowlist-first, not copy-all-then-trim

### Generated manifest snapshot

The future packaging workflow should generate a maintainer-side manifest snapshot with at least:

- artifact version
- platform id
- artifact root name
- include mapping summary
- exclude rules summary
- generation timestamp
- source commit or equivalent source tree identifier
- smoke-check result summary

Default design choice:

- the generated manifest snapshot is a **build-side sidecar**
- the first operator-facing artifact does not need to carry that snapshot inside the artifact root

## Artifact Naming And Versioning Convention

### Primary recommended pattern

- `scanbox-vX.Y.Z-windows-x64.zip`

### Acceptable variant

- `scanbox_X.Y.Z_windows_x64.zip`

### Naming rules

- the primary pattern should be preferred for future formal artifacts
- the acceptable variant is only for compatibility or internal tooling situations
- the first artifact root folder should align with the primary pattern:
  - `scanbox-vX.Y.Z-windows-x64/`
- freeze tag names do not enter artifact filenames
- artifact naming uses the same semver string as the future formal release tag family, but does not imply that a real tag already exists

### Version source

Artifact version must come only from these two files:

- `pyproject.toml`
- `src/scanbox/__init__.py`

They must match.

### Platform scope

The first design stage only defines:

- `windows-x64`

It does not pre-design additional platform suffixes such as:

- `windows-arm64`
- `linux-x64`
- `macos-*`

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

## Windows-First Path Transparency Requirements

The future single-folder artifact should satisfy these path transparency requirements:

- an operator should be able to see where runtime code, config, rules, and verification helpers live
- the artifact should not require an installer or opaque bootstrap layer to explain path relationships
- external engine wiring must remain explicit
- default config templates, rules, and verification helpers should remain in stable and inspectable locations
- the first artifact should optimize for reproducibility and diagnosability before it optimizes for installer-like convenience

Known current friction:

- `config/scanbox.toml` currently carries `C:\Tools\...` style placeholder executable paths for ClamAV and capa
- that is acceptable for the repository today, but it is not the final operator-facing story for a future artifact
- this design step records that mismatch as a future packaging follow-up
- this step does not change code or configuration to solve it

## Packaging Smoke-Check Definition

The future packaging flow should define a packaging smoke-check that validates the assembled artifact tree before any archive step is considered.

This smoke-check is:

- a structure and traceability check
- not runtime verification
- not acceptance
- not a replacement for baseline gates

### Minimum smoke-check surface

The first smoke-check definition should verify:

- artifact root folder name matches the naming convention
- version metadata is traceable from:
  - `pyproject.toml`
  - runtime package version source
- all required include entries are present
- repo-only content is absent
- external-not-bundled content is absent
- transient content is absent:
  - `__pycache__/`
  - `*.pyc`
  - `.venv/`
- maintainer-only scripts do not enter the artifact, especially:
  - acceptance scripts
  - `scripts/verify_release_readiness.ps1`
- operator-facing subset exists, including:
  - `scripts/verify_env.ps1`
  - `docs/dependencies.md`
  - rule manifests

## Future Packaging Script I/O Boundary

The future packaging script should be defined around staged artifact assembly, not around zip creation alone.

### Inputs

- repo root
- version
- target platform
  - `windows-x64`
- staging or output directory
- assembly spec
- include and exclude rules

### First-class outputs

- staged artifact tree
- generated manifest snapshot
- smoke-check result

### Secondary packaging output

- zip filename
- zip path

Important boundary:

- the **staged artifact tree is a first-class output**
- a zip archive is only one possible packaging form for that staged tree
- assembly should not be tightly coupled to zip creation

### Explicit non-goals

The future packaging script should not:

- download ClamAV or capa
- download the ClamAV database
- automatically discover workstation-local external dependencies
- automatically write workstation-local override config
- create tags
- create GitHub Releases
- modify repo-tracked files

## Future Implementation Backlog

### Phase A

- define the exact artifact assembly spec
- define the manifest generation format
- define the operator-facing subset precisely
- define the repo-layout to artifact-layout mapping implementation
- add an operator quickstart section tailored to the future artifact

### Phase B

- evaluate whether to also produce a wheel as a secondary maintainer artifact
- only do this after rules/config/runtime asset inclusion has been validated
- decide the final artifact-internal runtime path implementation details
- decide whether `rules/capa/bundled/` metadata files such as `.github/`, vendored `README.md`, and `LICENSE.txt` are copied, filtered, or normalized for artifact use
- define the packaging smoke-check automation boundary

### Phase C

- re-evaluate heavier distribution options:
  - refined runnable zip conventions
  - semi-automated external dependency bootstrap
  - single-file packaging only if runtime and path behavior become sufficiently deterministic
- define the minimum packaging smoke-check needed before any real artifact is considered release-ready

## Minimal Follow-Up List

- define the artifact assembly spec / manifest generation workflow
- define the exact include/exclude rules from repo layout to artifact layout
- decide the final physical runtime path implementation inside the artifact
- decide the artifact treatment of vendored capa metadata files
- decide whether operator quickstart guidance lives in `README.md` or a dedicated artifact-local quickstart file
- define the packaging smoke-check implementation without changing acceptance responsibilities

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
