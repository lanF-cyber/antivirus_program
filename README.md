# ScanBox

ScanBox is a Windows-first local security scanning orchestrator. It does not implement its own antivirus engine. Instead, it coordinates mature open source scanners, normalizes their results, and emits a single JSON report for a single file target or a directory scan summary report for a directory target.

## 当前定位

当前仓库以 **ScanBox v1 milestone baseline** 为准。

- 这是一个 Windows-first、本地单文件安全扫描 CLI
- 当前真实接通了 YARA、ClamAV、capa 三条主链路
- 默认 `stdout` 输出聚焦简版 JSON
- `--report-out` 输出 full JSON
- 当前重点是“可复现、可验收、可维护”的 v1 基线，不继续横向扩 GUI、拖拽、多文件或云能力

## 我该先看什么

维护者最短路径：

1. 第一步看 [v1 冻结说明](docs/milestones/scanbox-v1-freeze.md)
2. 第二步看 [操作与维护手册](docs/operations.md)
3. 第三步直接跑 `powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1`

如果上面三步都顺利，再去看其它文档。

维护约定：

- `config/scanbox.toml` 是仓库默认配置，应保持通用
- `config/scanbox.local.toml` 是本机覆盖配置，用来放这台机器的实际引擎路径，不应作为长期默认值
- `docs/milestones/golden/` 是 committed 的去敏 golden outputs
- `reports/` 是本机生成产物，不是仓库冻结基线

## 如何快速做一次本地验收

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

这条命令会按当前 v1 官方验收链路依次执行：

1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest -q`
3. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`
4. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt`
5. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1`
6. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com`

当前运行产物会写到 `reports/acceptance-v1/<timestamp>/`。

如需额外跑本机增强项，例如 `python.exe` 的人工 `capa` 验收和 full report 体积对比，再显式追加：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1 -IncludeLocalEnhancements
```

## Current scope

- Python CLI first
- Single-file scanning plus directory scan MVP
- Hashing: SHA256, MD5, optional SHA1
- External engines:
  - ClamAV
  - YARA via `yara-python`
  - capa for supported executable targets
- Unified JSON reporting
- Structured engine errors and timeouts
- Optional quarantine move with audit metadata
- Quarantine lifecycle management via:
  - `scanbox quarantine list`
  - `scanbox quarantine restore <scan_id>`
  - `scanbox quarantine delete <scan_id> --yes`

## Non-goals for v1

- GUI
- Native Windows drag-and-drop shell integration
- EXE packaging
- Concurrent or complex batch scanning
- Automatic downloads or implicit network access
- Claims that "no detection" means "safe"

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt -r .\requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

## Example command

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\.venv\Scripts\python.exe --report-out .\reports\python-full.json
```

## V2.2-A directory scan MVP

Directory scanning now supports a minimal recursive, serial MVP:

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\directory_mvp
```

Current V2.2-A boundary:

- recursive directory walking
- serial per-file scanning
- stable `results[]` ordering by relative path
- top-level summary JSON that reuses single-file `ScanReport` for each child result
- `stdout` stays on default detail, `--report-out` stays full
- no batch quarantine for directory mode

## Exit codes

- `0`: clean-by-known-checks scan completed
- `1`: known malicious
- `2`: suspicious
- `3`: partial scan
- `4`: engine missing
- `5`: engine unavailable
- `6`: scan error
- `7`: configuration error
- `8`: invalid input

## Documentation

- [v1 Freeze](docs/milestones/scanbox-v1-freeze.md)
- [V2.1 Quarantine Freeze](docs/milestones/scanbox-v2-quarantine.md)
- [V2.2-A Directory Freeze](docs/milestones/scanbox-v2.2-directory-mvp.md)
- [Changelog](CHANGELOG.md)
- [Demo Flow](docs/demo.md)
- [Operations](docs/operations.md)
- [Architecture](docs/architecture.md)
- [Dependencies](docs/dependencies.md)
- [Development](docs/development.md)

## V2 Phase 1 note

Quarantine is no longer only a scan-time move action. The current baseline also supports lifecycle management:

```powershell
.\.venv\Scripts\python.exe -m scanbox quarantine list
.\.venv\Scripts\python.exe -m scanbox quarantine restore <scan_id>
.\.venv\Scripts\python.exe -m scanbox quarantine delete <scan_id> --yes
```

Safety defaults:

- `list` returns record summaries only and does not expand full event history
- `restore` rejects path conflicts by default
- `delete` requires explicit `--yes`

## Freeze entrypoints

The repository now has three distinct baselines:

- v1 scanning baseline
- V2.1 quarantine lifecycle baseline
- V2.2-A directory scanning baseline

Recommended entrypoints:

1. [v1 Freeze](docs/milestones/scanbox-v1-freeze.md)
2. [V2.1 Quarantine Freeze](docs/milestones/scanbox-v2-quarantine.md)
3. [V2.2-A Directory Freeze](docs/milestones/scanbox-v2.2-directory-mvp.md)
4. [Operations](docs/operations.md)
5. Pick the acceptance script that matches the goal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_directory.ps1
```

Use:

- `acceptance_v1.ps1` for the single-file scanning baseline
- `acceptance_v2_quarantine.ps1` for the quarantine lifecycle baseline
- `acceptance_v2_directory.ps1` for the directory scanning baseline
