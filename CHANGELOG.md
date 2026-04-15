# Changelog

This changelog is a maintainer-facing overview of the current frozen ScanBox milestones. It is intentionally short and points to the milestone documents and acceptance entrypoints instead of repeating the full operational docs.

## v1: scanning baseline

- Tag: `scanbox-v1-freeze`
- Acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`
- Added:
  - single-file scanning baseline
  - YARA / ClamAV / capa integration
  - focused JSON on `stdout`
  - full JSON through `--report-out`
  - environment verification via `scripts/verify_env.ps1`
- Current boundary:
  - CLI-first
  - single-file baseline only
  - no GUI, drag-and-drop, cloud service, or concurrent batch workflow
  - `script.ps1` remains `capa`-skipped by policy

## v2.1: quarantine lifecycle baseline

- Tag: `scanbox-v2.1-quarantine`
- Acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1`
- Added:
  - `scanbox quarantine list`
  - `scanbox quarantine restore <scan_id>`
  - `scanbox quarantine delete <scan_id> --yes`
  - append-only quarantine audit history
  - conservative legacy audit compatibility
- Current boundary:
  - `list` returns record summaries only
  - restore rejects path conflicts by default
  - delete requires explicit `--yes`
  - no batch restore/delete, no `show`, no force-overwrite restore

## v2.2-A: directory scanning baseline

- Tag: `scanbox-v2.2-directory-mvp`
- Acceptance: `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1`
- Added:
  - `scanbox scan <directory>`
  - recursive directory traversal
  - serial per-file scanning
  - top-level directory summary report with child single-file results
  - stable `results[]` ordering by relative path
- Current boundary:
  - default `stdout` remains focused detail
  - `--report-out` remains the full report path
  - explicit directory `--quarantine move` / `--dry-run-quarantine` returns structured `input_error`
  - no concurrent scanning, no batch quarantine, no archive expansion, no committed golden outputs for directory mode

## Milestone entrypoints

- v1 snapshot: [docs/milestones/scanbox-v1-freeze.md](docs/milestones/scanbox-v1-freeze.md)
- V2.1 snapshot: [docs/milestones/scanbox-v2-quarantine.md](docs/milestones/scanbox-v2-quarantine.md)
- V2.2-A snapshot: [docs/milestones/scanbox-v2.2-directory-mvp.md](docs/milestones/scanbox-v2.2-directory-mvp.md)
- Operations guide: [docs/operations.md](docs/operations.md)
- Development guide: [docs/development.md](docs/development.md)
