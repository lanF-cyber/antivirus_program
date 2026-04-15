# ScanBox Architecture

ScanBox v1 is a single-file Windows-first scanning orchestrator. The CLI is intentionally thin and delegates the main work to package modules that can later be reused by an EXE wrapper or GUI.

## Flow

1. Parse CLI arguments
2. Load and validate TOML configuration
3. Resolve a `FileTarget`
4. Compute hashes
5. Detect file type
6. Run engine preflight checks
7. Execute supported scanners
8. Aggregate verdict
9. Optionally quarantine eligible files
10. Emit a stable JSON report

## Key modules

- `scanbox.cli`: argument parsing and exit codes
- `scanbox.config`: loading, merging, validating, and normalizing configuration
- `scanbox.core`: shared enums, models, file typing, hashing, and subprocess helpers
- `scanbox.adapters`: one adapter per scanner
- `scanbox.pipeline`: orchestration and verdict resolution
- `scanbox.quarantine`: move planning and audit persistence
- `scanbox.reporting`: JSON serialization

## Engine behavior

- ClamAV: full-file signature scan
- YARA: local bundled rule evaluation via `yara-python`
- capa: JSON capability analysis for supported executable targets only

## Safety invariants

- No implicit downloads
- No upload to third-party services
- No clean verdict when required enabled engines are missing or unavailable
- No claim that a non-hit means the file is safe
