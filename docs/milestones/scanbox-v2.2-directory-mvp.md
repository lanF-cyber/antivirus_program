# ScanBox V2.2-A Directory Scan MVP Freeze

This document is the freeze snapshot for the current V2.2-A directory scanning milestone. It is intentionally a milestone summary, not a full operations manual.

## 1. What V2.2-A adds

V2.2-A extends the existing `scan` command so ScanBox can scan a directory and return a directory-level summary report:

- `scanbox scan <directory>`
- recursive traversal by default
- serial execution
- one child result per scanned file
- a top-level directory report with `summary` and `results[]`

The directory wrapper does not replace the single-file model. Each child entry still reuses the existing single-file `ScanReport`.

## 2. Current boundary

V2.2-A currently supports:

- recursive directory scanning
- stable `results[]` ordering by relative path
- directory summary JSON on `stdout`
- full report export through `--report-out`
- reuse of the existing single-file scan core

V2.2-A does not currently support:

- concurrent scanning
- batch quarantine
- archive expansion
- GUI or drag-and-drop flows
- cloud workflows
- committed golden outputs for directory mode

## 3. Directory report shape

The top-level directory report includes:

- `mode = "directory"`
- `target`
- `target_count`
- `scanned_count`
- `error_count`
- `overall_status`
- `issues`
- `summary`
- `results`

`results[]` are ordered by relative path in lexicographic order. This is a stability contract for the MVP, not an incidental implementation detail.

The directory-level `summary` and `overall_status` are both derived from child result verdicts. V2.2-A does not introduce a separate directory-only verdict system.

## 4. Detail level rules

The existing report detail split continues to apply:

- default `stdout` uses the focused JSON shape
- `results[]` child reports also use default detail on `stdout`
- `--report-out` writes the full JSON report

The directory mode should not become a new report bloat path. Default output stays optimized for human review and lightweight downstream parsing.

## 5. Directory quarantine boundary

V2.2-A intentionally does not support batch quarantine from directory mode.

These inputs are rejected with structured `input_error`:

- `scanbox scan <directory> --quarantine move`
- `scanbox scan <directory> --dry-run-quarantine`

The reason is scope control: the MVP adds directory traversal and aggregation only. It does not add multi-file destructive actions.

## 6. Relationship to earlier freezes

The current repository now has three separate baselines:

- v1: single-file scanning baseline
- V2.1: quarantine lifecycle baseline
- V2.2-A: directory scanning baseline

V2.2-A builds on the earlier baselines but does not replace them.

## 7. Acceptance entrypoint

The V2.2-A acceptance entrypoint is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1
```

The script validates the minimum must-pass path:

- editable install
- `pytest -q`
- directory fixture scan
- directory summary assertions
- `results[]` ordering assertions
- `--report-out` file generation and JSON parsing

Artifacts are written to:

```text
reports/acceptance-v2-directory/<timestamp>/
```

These artifacts are local run outputs, not committed repository baseline files.
