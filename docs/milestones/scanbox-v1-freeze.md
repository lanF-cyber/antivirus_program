# ScanBox v1 Freeze

本文档是当前 ScanBox v1 的冻结快照。目标不是重复维护手册，而是固定“这个里程碑已经做到哪里、怎么验收、哪些内容属于仓库基线、哪些仍然是本机私有状态”。

## 1. 当前形态

当前 ScanBox v1 的定位已经明确冻结为：

- Windows-first、本地单文件安全扫描 CLI
- 统一编排多个成熟开源引擎
- 输出统一 JSON 报告
- 默认 `stdout` 输出聚焦简版
- `--report-out` 输出 full 报告

当前不是：

- GUI
- 拖拽版
- 多文件或目录扫描器
- 云上传/在线沙箱
- “未命中即安全”的判定器

## 2. 已接通的真实能力

本里程碑冻结时，项目已经真实接通：

- YARA
- ClamAV
- capa

接通形态说明：

- 仓库默认配置：`config/scanbox.toml`
- 本机覆盖配置：`config/scanbox.local.toml`
- 环境检查入口：`scripts/verify_env.ps1`

本机私有状态仍然包括：

- `config/scanbox.local.toml`
- `config/clamav/freshclam.local.conf`
- `.local-tools/`
- `reports/`
- 当前工作站专属绝对路径

## 3. 当前输出策略

当前输出策略已经冻结为：

- `stdout`：聚焦简版 JSON，优先服务命令行阅读和后续轻量集成
- `--report-out`：full JSON，保留更完整的调试信息

特别说明：

- 默认 `stdout` 不再承载完整 `capa raw_summary.meta`
- full 报告继续保留完整调试信息
- `script.ps1` 继续默认跳过 `capa`

## 4. 当前测试状态

当前 v1 冻结快照以以下基线为准：

- `.\.venv\Scripts\python.exe -m pytest -q` 为绿色
- `scripts/verify_env.ps1` 能清晰报告当前环境状态
- hello / script / eicar 三条样本链路稳定

冻结快照验收使用的官方命令链路：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

## 5. 样本验收结果矩阵

| 样本 | 角色 | 预期退出码 | 预期 `overall_status` | 关键观察点 |
| --- | --- | --- | --- | --- |
| `tests/fixtures/benign/hello.txt` | 基础 clean 路径 | `0` | `clean_by_known_checks` | ClamAV `ok`，YARA `ok`，capa `skipped_not_applicable` |
| `tests/fixtures/benign/script.ps1` | 脚本 skip 路径 | `0` | `clean_by_known_checks` | `engines.capa.state = "skipped_not_applicable"`，`skip_reason = "script_file_not_supported_in_v1_policy"` |
| `tests/fixtures/eicar/eicar.com` | 恶意演示路径 | `1` | `known_malicious` | ClamAV 命中 `Eicar-Signature`，YARA 命中 `scanbox_test_eicar_marker` |
| `.\.venv\Scripts\python.exe` | 本机人工 `capa` 验收样本 | 人工观察 | 通常为 `clean_by_known_checks` | 重点看 `engines.capa.state = "ok"` 和 `analysis_summary`，不作为 committed golden 基线 |

## 6. Golden Outputs 约定

当前仓库提交的 golden outputs 位于：

- `docs/milestones/golden/`

这些文件的定位是：

- 来自真实样本运行结果
- 经过规范化和去敏
- 只保留稳定字段子集
- 用于展示、复现和对齐预期

不会提交为 golden 基线的内容：

- full JSON 报告
- 本机 `python.exe` 样本输出
- `scan_id`
- 时间戳
- 本机绝对路径
- 本机 runtime temp dir
- quarantine 实际落点路径

当前 committed golden 文件：

- `docs/milestones/golden/hello.stdout.sanitized.json`
- `docs/milestones/golden/script.stdout.sanitized.json`
- `docs/milestones/golden/eicar.stdout.sanitized.json`

## 7. 冻结边界

本轮冻结明确不做：

- GUI
- 拖拽
- 多文件/目录
- 新外部引擎接通
- verdict 逻辑变更
- `script.ps1` 的 `capa` 策略变更

本轮冻结也不把以下内容写回仓库默认基线：

- `config/scanbox.local.toml` 里的本机路径
- `freshclam.local.conf`
- `.local-tools/`
- `reports/` 里的本地产物

## 8. 一键验收入口

当前 v1 官方一键验收入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

脚本行为固定为：

- 只执行和检查
- 不自动修环境
- 不自动下载
- 不初始化系统组件
- 运行结果写入 `reports/acceptance-v1/<timestamp>/`
- 默认只跑必过项
- `python.exe` 的人工 `capa` 验收和 full report 体积对比属于本机增强项，只有显式传入 `-IncludeLocalEnhancements` 时才运行

## 9. 已知限制

- v1 仍然只支持单文件
- v1 仍然是 CLI first
- `python.exe` 样本只适合本机人工 `capa` 验收，不适合做 committed baseline
- `reports/` 下的 full 报告适合本地复盘，不适合直接提交到仓库
- “未命中”不代表“安全”

## 10. 下一阶段建议

后续如果继续推进，建议按下面顺序走：

1. 先保持当前 v1 基线不漂移
2. 后续功能开发单独开新里程碑
3. 如果需要新的 golden outputs，继续先做去敏再提交
4. 如果开始做持续发布或第二个里程碑，再引入 `CHANGELOG.md`
