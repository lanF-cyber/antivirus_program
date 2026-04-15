# ScanBox Demo Flow

This is the shortest walkthrough for showing what the current ScanBox baseline can do in a few minutes.

Use this file for live demos.

Use the acceptance scripts only when the goal is baseline verification.

## 1. Optional Setup Check

If the environment is already prepared, you can skip this step.

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
```

## 2. Live Demo Steps

### 2.1 Benign Single-File Scan

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

Point out:

- `overall_status = "clean_by_known_checks"`
- JSON is emitted directly to `stdout`
- the tool stays local and CLI-first

### 2.2 Known-Malicious Sample Scan

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

Point out:

- `overall_status = "known_malicious"`
- engine-level detections are preserved
- this is still a normal local CLI workflow

### 2.3 Directory Scan MVP

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
```

Point out:

- `mode = "directory"`
- `target_count = 3`
- `scanned_count = 3`
- `results[]` is stable and sorted by relative path
- child entries still reuse the single-file report shape

Optional full report export:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp --report-out .\reports\directory-mvp.full.json
```

### 2.4 Quarantine Lifecycle Surface

```powershell
.\.venv\Scripts\python.exe -m scanbox quarantine list
.\.venv\Scripts\python.exe -m scanbox quarantine restore <scan_id>
.\.venv\Scripts\python.exe -m scanbox quarantine delete <scan_id> --yes
```

Point out:

- `list` returns record summaries
- `restore` uses `scan_id` as the primary identifier
- `delete` requires explicit `--yes`

If you want a full lifecycle validation instead of an ad-hoc demo, use the quarantine acceptance script below.

## 3. Demo Commands vs Acceptance Commands

Use the commands above when the goal is a short project showcase.

Use the acceptance scripts below when the goal is maintainers validating a baseline:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1
```

Interpretation:

- `acceptance_v1.ps1`: single-file scanning baseline
- `acceptance_v2_quarantine.ps1`: quarantine lifecycle baseline
- `acceptance_v2_directory.ps1`: directory scanning baseline

## 4. Suggested Three-Minute Showcase

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
- directory aggregation
- independent quarantine lifecycle entrypoints
