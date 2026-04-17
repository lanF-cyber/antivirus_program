# ScanBox

ScanBox is a Windows-first local security scanning CLI that orchestrates ClamAV, YARA, and capa, then emits a single JSON result for a file target or a directory summary for a directory target.

## Current Capabilities

- Single-file scanning
- Directory scanning MVP via `scanbox scan <directory>`
- Engine orchestration across:
  - ClamAV
  - YARA
  - capa
- Focused JSON on `stdout`
- Full JSON via `--report-out`
- Quarantine lifecycle commands:
  - `scanbox quarantine list`
  - `scanbox quarantine restore <scan_id>`
  - `scanbox quarantine delete <scan_id> --yes`
- Local environment verification via `scripts/verify_env.ps1`
- Maintainer acceptance scripts for the current baselines

## Current Non-Goals

- GUI
- Drag-and-drop shell workflow
- Concurrent scanning
- Batch quarantine actions
- Archive expansion
- Cloud service or automatic upload
- Treating "no detection" as "safe"

## Quick Start

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

## Quick Demo

Fastest project walkthrough:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
.\.venv\Scripts\python.exe -m scanbox quarantine list
```

For the short showcase script and talking points, see [docs/demo.md](docs/demo.md).

## Baselines

| Baseline | What it covers | Acceptance | Tag |
| --- | --- | --- | --- |
| v1 | Single-file scanning baseline | `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1` | `scanbox-v1-freeze` |
| v2.1 | Quarantine lifecycle baseline | `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1` | `scanbox-v2.1-quarantine` |
| v2.2-A | Directory scanning baseline | `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1` | `scanbox-v2.2-directory-mvp` |

## What To Read First

1. [Demo flow](docs/demo.md)
2. [v1 milestone](docs/milestones/scanbox-v1-freeze.md)
3. [v2.1 quarantine milestone](docs/milestones/scanbox-v2-quarantine.md)
4. [v2.2-A directory milestone](docs/milestones/scanbox-v2.2-directory-mvp.md)

## Maintainer Entry Points

- [CHANGELOG.md](CHANGELOG.md)
- [Operations guide](docs/operations.md)
- [Development guide](docs/development.md)
- [Release workflow](docs/release-workflow.md)
- [Packaging strategy](docs/packaging-strategy.md)
- [Release notes template](docs/release-notes-template.md)
- [Repository metadata suggestions](docs/repo-metadata.md)
- [Architecture notes](docs/architecture.md)
- [Dependencies](docs/dependencies.md)
