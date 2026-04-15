# ScanBox Demo Flow

This document is the shortest walkthrough for showing what the current ScanBox baseline can do. It is meant for a quick demo, not for full maintenance or full acceptance.

## 1. Demo setup

If the local environment is already prepared, you can go straight to the scan commands below.

If you need the minimal setup first:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
```

## 2. Demo commands

### 2.1 Benign single-file scan

Show the normal clean path:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

What to point out:

- `overall_status = "clean_by_known_checks"`
- structured JSON on `stdout`
- no GUI and no hidden background workflow

### 2.2 EICAR malicious sample scan

Show a stable known-malicious path:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

What to point out:

- `overall_status = "known_malicious"`
- the report includes engine-level detections
- this is still a local CLI workflow

### 2.3 Directory scan MVP

Show the current directory wrapper over the single-file scan core:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
```

What to point out:

- `mode = "directory"`
- `target_count = 3`
- `scanned_count = 3`
- `results[]` is stable and sorted by relative path
- child results still reuse the single-file report shape

Optional full report export:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp --report-out .\reports\directory-mvp.full.json
```

### 2.4 Quarantine lifecycle

Show the command surface first:

```powershell
.\.venv\Scripts\python.exe -m scanbox quarantine list
.\.venv\Scripts\python.exe -m scanbox quarantine restore <scan_id>
.\.venv\Scripts\python.exe -m scanbox quarantine delete <scan_id> --yes
```

What to point out:

- `list` returns record summaries
- `restore` uses `scan_id` as the primary identifier
- `delete` requires explicit `--yes`

If you want the full quarantine lifecycle demo instead of a live ad-hoc flow, use the dedicated acceptance script in the next section.

## 3. Demo commands vs acceptance commands

Use the commands above when the goal is a quick showcase.

Use the acceptance scripts below when the goal is baseline verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1
```

Interpretation:

- `acceptance_v1.ps1`: single-file scanning baseline
- `acceptance_v2_quarantine.ps1`: quarantine lifecycle baseline
- `acceptance_v2_directory.ps1`: directory scanning baseline

## 4. Suggested shortest live showcase

If you only have a few minutes, run these in order:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
.\.venv\Scripts\python.exe -m scanbox quarantine list
```

That sequence shows:

- clean single-file scanning
- known-malicious single-file detection
- directory scan aggregation
- independent quarantine lifecycle entrypoints
