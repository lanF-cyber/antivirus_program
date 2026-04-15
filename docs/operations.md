# ScanBox 操作与维护手册

本文档面向 ScanBox 项目作者本人和后续维护者。目标不是介绍理念，而是把“这个仓库现在到底怎么用、怎么改、从哪里下手、怎么判断结果是否正常”写清楚，后续维护时直接照着做即可。

## 0. v1 冻结快照入口

如果这次打开仓库的目标是“先确认 ScanBox v1 现在冻结到了哪里”，先走这条最短路径：

1. 看 [v1 冻结说明](milestones/scanbox-v1-freeze.md)
2. 看 `docs/milestones/golden/` 里的 committed golden outputs
3. 跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

入口分工固定为：

- `docs/milestones/scanbox-v1-freeze.md`：阶段性冻结快照
- `docs/operations.md`：长期维护手册
- `reports/`：本机生成产物，不是 committed baseline

## 1. 项目当前形态

当前 ScanBox v1 的定位非常明确：

- 它是一个 **Windows 本地单文件安全扫描 CLI**
- 它 **不是 GUI**
- 它 **不是拖拽版**
- 它 **不是单 exe 发布版**
- 它 **不是自带全部外部引擎的完整成品**
- 它当前更像一个 **多引擎扫描编排器 + JSON 报告器**

它现在做的事情是：

1. 接收一个本地文件路径
2. 计算 hash
3. 按策略调用外部扫描器或本地规则
4. 汇总成统一 JSON 报告
5. 在满足条件时给出 quarantine 处置结果

它现在不做的事情是：

1. 不做多文件和目录扫描
2. 不做 GUI 交互
3. 不自动联网下载引擎
4. 不内置完整 ClamAV / capa 运行环境
5. 不因为“没命中”就宣称文件绝对安全

## 2. 项目目录怎么理解

下面这张表是日常维护时最常看的目录解释。

| 路径 | 作用 | 维护时怎么理解 |
| --- | --- | --- |
| `config/` | 默认运行配置与本机覆盖配置 | `scanbox.toml` 是仓库默认值，`scanbox.local.toml` 是本机覆盖；`clamav/` 下同时放 freshclam 模板和本机配置 |
| `docs/` | 项目文档 | 这里放维护文档、依赖来源说明、开发说明 |
| `rules/` | 项目内规则快照 | `yara/` 放项目内固定 YARA 规则；`capa/` 放 vendored 的 capa-rules 快照或占位目录 |
| `scripts/` | PowerShell 辅助脚本 | 用于环境检查、基础 setup、显式更新规则/库 |
| `src/scanbox/` | 主程序代码 | 这是扫描逻辑本体，CLI、adapter、pipeline、reporting 都在这里 |
| `tests/` | 测试代码与样本 | 单元测试、集成测试、无害样本、stub 数据都在这里 |
| `requirements.txt` | 运行时 Python 依赖 | 这里只放 Python 包，不放 ClamAV/capa 二进制 |
| `requirements-dev.txt` | 开发和测试依赖 | 主要是 pytest 相关包 |
| `pyproject.toml` | 项目打包与安装入口 | `src` 布局、editable install、pytest 配置都从这里走 |
| `README.md` | 仓库首页入口 | 维护者第一次打开仓库时应先看这里的最短路径 |

### `src/scanbox/` 子目录怎么理解

| 路径 | 作用 |
| --- | --- |
| `src/scanbox/cli/` | 命令行入口，负责参数解析与退出码 |
| `src/scanbox/config/` | 配置加载、路径规范化、配置校验 |
| `src/scanbox/core/` | 共用枚举、模型、hash、文件类型识别、异常 |
| `src/scanbox/adapters/` | 外部引擎适配层，ClamAV/YARA/capa 都在这里 |
| `src/scanbox/pipeline/` | 扫描主流程、预检查、状态归类 |
| `src/scanbox/quarantine/` | quarantine 逻辑与审计记录 |
| `src/scanbox/reporting/` | JSON 输出层 |
| `src/scanbox/targets/` | 扫描目标抽象，目前只有单文件 |

## 3. 我平时真正会改哪些文件

### 高频可改

这些是最常改、改了也最符合当前 v1 边界的地方。

| 文件/目录 | 分类 | 作用 | 什么时候改 |
| --- | --- | --- | --- |
| `config/scanbox.toml` | 仓库默认配置入口 | 默认 profile、超时、通用引擎路径、quarantine 目录 | 改仓库默认行为时优先改这里 |
| `config/scanbox.local.toml` | 本机覆盖配置入口 | 当前机器的实际引擎路径覆盖，只放需要覆盖的键 | 改这台机器的实际路径时优先改这里，不要把它当仓库默认值 |
| `docs/dependencies.md` | 依赖来源入口 | 记录官方来源、固定版本、引入方式 | 升级/替换外部依赖时改这里 |
| `scripts/verify_env.ps1` | 环境检查入口 | 检查 Python、配置、manifest、基础目录是否存在 | 想让环境检查更具体时改这里 |
| `scripts/setup_windows.ps1` | 初始化说明入口 | 给新机器或新环境一个最基本的上手检查 | 调整 setup 提示时改这里 |
| `config/clamav/freshclam.conf` | freshclam 模板 | 提交到仓库的示例配置，不直接代表某台机器的真实路径 | 调整模板或说明时改这里 |
| `config/clamav/freshclam.local.conf` | freshclam 本机配置 | 当前机器实际用来初始化 ClamAV 数据库的本地配置 | 只在本机路径变化时改，不作为长期默认值 |
| `rules/yara/bundled/*` | 规则入口 | 项目内固定 YARA 规则文件 | 增加、替换、删除项目内规则时改这里 |
| `rules/yara/manifest.json` | YARA 规则元数据 | 规则集版本、来源、启用数量 | 规则集有变化时一起更新 |
| `src/scanbox/adapters/*` | 引擎适配层 | 每个外部引擎如何 discover / supports / scan | 改引擎调用方式、解析逻辑时改这里 |
| `src/scanbox/pipeline/*` | 扫描主流程 | 预检查、主流水线、状态归类 | 改 overall_status、流程顺序、策略时改这里 |
| `src/scanbox/reporting/json_report.py` | 报告输出层 | JSON 序列化与错误报告结构 | 改 JSON 字段或输出方式时改这里 |
| `tests/*` | 测试层 | 验证配置、adapter、pipeline、CLI 行为 | 每次改行为都应该补或改测试 |

### 低频可改

这些文件可以改，但通常不是高频入口。

| 文件/目录 | 作用 | 什么时候改 |
| --- | --- | --- |
| `rules/capa/bundled/*` | vendored 的 capa-rules 快照位置 | 更新 vendored 官方快照版本时改 |
| `rules/capa/manifest.json` | capa-rules 元数据 | 更新 vendored 快照版本时改 |
| `src/scanbox/core/models.py` | 全局数据模型 | 改统一报告模型或状态枚举时改 |
| `src/scanbox/core/filetypes.py` | 文件类型识别 | 改脚本/PE/ELF/Mach-O 判定策略时改 |
| `src/scanbox/cli/main.py` | CLI 入口 | 改参数、退出码、命令结构时改 |
| `docs/development.md` | 开发说明 | 调整开发流程时改 |
| `docs/architecture.md` | 架构说明 | 主流程设计变化后更新 |

### 一般不要乱改

这些不是绝对不能动，但动之前要明确你是在改“项目基础结构”，不是在做普通维护。

| 文件 | 原因 |
| --- | --- |
| `pyproject.toml` | 这里决定了 `src` 布局安装方式、editable install 和测试配置，改坏后很容易出现“pytest 能过但 python -m scanbox 跑不起来” |
| `src/scanbox/__main__.py` | 这是 `python -m scanbox` 的模块入口，通常不需要频繁改 |
| `src/scanbox/__init__.py` | 包版本与包入口元信息，不是日常策略入口 |
| `requirements.txt` | 运行时依赖要精确、稳定，不要随手加杂项 |
| `requirements-dev.txt` | 测试工具链入口，随意变动可能影响 CI 或本地环境 |

### 提交约定

- 应提交到仓库：
  - `config/scanbox.toml`
  - `config/clamav/freshclam.conf`
  - `docs/*`
  - `src/scanbox/*`
  - `tests/*`
- 只保留在本机：
  - `config/scanbox.local.toml`
  - `config/clamav/freshclam.local.conf`
  - `.local-tools/`
- 判断原则：
  - 会因为“换一台机器”就失效的路径，不应放进仓库默认配置
  - 只影响当前维护者工作站的覆盖值，优先放进 `.local` 文件

## 4. 不同操作该从什么入口做

下面这张表按“任务 -> 应该改哪里”列出。

| 任务 | 应该去改哪里 | 说明 |
| --- | --- | --- |
| 改默认超时 | `config/scanbox.toml`，必要时 `src/scanbox/core/timeouts.py` | 默认值先看配置，只有超时模型本身变化才改代码 |
| 改默认 quarantine 行为 | `src/scanbox/cli/main.py` 和 `src/scanbox/quarantine/service.py` | CLI 默认值在 `main.py`，实际策略在 `service.py` |
| 改引擎路径 | 当前机器先改 `config/scanbox.local.toml`，只有默认值变化才改 `config/scanbox.toml` | 不要先改代码，先区分“仓库默认值”还是“本机实际路径” |
| 增加/替换 YARA 规则 | `rules/yara/bundled/*` + `rules/yara/manifest.json` | 规则变更后记得同步 manifest |
| vendor 固定 capa-rules | `rules/capa/bundled/*` + `rules/capa/manifest.json` + `docs/dependencies.md` | 把固定官方快照放进项目，再写清 pinned ref |
| 改 `overall_status` 归类逻辑 | `src/scanbox/pipeline/verdicts.py` | 这里是状态归类主入口 |
| 改 JSON 报告字段 | `src/scanbox/core/models.py` + `src/scanbox/reporting/json_report.py` | 先改模型，再确认输出序列化 |
| 改脚本文件是否跳过 capa | `src/scanbox/core/filetypes.py` + `src/scanbox/pipeline/orchestrator.py` + `src/scanbox/adapters/capa.py` | 需要同时看“识别”“适用”“跳过原因”三层 |
| 加新的测试样本 | `tests/fixtures/*` | 无害样本放对应子目录 |
| 加新的测试断言 | `tests/unit/*` 或 `tests/integration/*` | 纯逻辑放 unit，实际链路放 integration |
| 调整 README 和开发文档 | `README.md`、`docs/development.md`、`docs/operations.md` | 优先保证 README 能把人带到正确入口 |

## 5. 本地开发实际操作步骤

以下命令默认你已经在 PowerShell 中，并且仓库根目录是：

```powershell
Set-Location C:\Users\Lancelot\Desktop\antivirus_program
```

### 5.1 创建 venv

```powershell
python -m venv .venv
```

### 5.2 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt -r .\requirements-dev.txt
```

### 5.3 做 editable install

这是 `src` 布局项目的关键步骤。没有这一步，`python -m scanbox` 可能无法导入包。

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

### 5.4 跑 pytest

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 5.5 跑环境检查脚本

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
```

### 5.6 扫 benign `hello.txt`

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
```

### 5.7 扫 `script.ps1`

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1
```

### 5.8 扫 `eicar.com`

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

### 5.9 将报告保存到文件

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt --report-out .\reports\hello.json
```

说明：

- 直接输出到 `stdout` 的是默认简版 JSON，优先服务命令行阅读和快速判断
- `--report-out` 落盘的是 full 版 JSON，保留更完整的调试字段
- 两者保持同一套 schema，只是 detail level 不同，不是两套完全不同的报告格式

### 5.10 一键跑当前 v1 官方验收

如果你的目标不是单条命令调试，而是“确认当前仓库基线仍然完整”，优先直接跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

这个脚本会依次执行：

1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest -q`
3. `powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1`
4. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt`
5. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1`
6. `.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com`

运行产物会写到：

```text
reports/acceptance-v1/<timestamp>/
```

这批产物只用于本地复盘，不是仓库冻结基线。

如果你还想追加本机增强项，例如 `python.exe` 的人工 `capa` 验收或 full report 体积对比，再显式传：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1 -IncludeLocalEnhancements
```

### 5.11 使用其它 profile

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com --profile aggressive
```

### 5.12 试跑 quarantine 但不实际移动文件

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com --quarantine move --dry-run-quarantine
```

## 6. 外部依赖怎么接入

这一节很重要。当前项目不是把所有外部能力都放进 Python 包里。

### 6.1 什么不是 pip 依赖

- ClamAV **不是** pip 依赖
- capa **不是** pip 依赖
- 它们都需要你从 **官方来源** 获取二进制或官方发布产物，再在配置里指向它们

### 6.2 什么是项目内固定快照

- `rules/yara/bundled/`
  - 这是项目内固定 YARA 规则目录
  - 当前已经有用于本地测试的 starter 规则
- `rules/capa/bundled/`
  - 这是项目里预留的 capa-rules vendor 目录
  - 当前仓库里已经 vendored 了 pinned 官方 `capa-rules v9.3.0` 完整快照
  - 当前应以 `rules/capa/manifest.json` 中 `vendor_status = "vendored"` 为准

### 6.3 真实外部来源从哪里看

先看：

- [docs/dependencies.md](C:\Users\Lancelot\Desktop\antivirus_program\docs\dependencies.md)

这里记录了：

- ClamAV 官方来源
- capa 官方来源
- capa-rules 官方来源
- Python 依赖官方来源

### 6.4 ClamAV 怎么接入

实际步骤：

1. 从 `docs/dependencies.md` 记录的官方来源获取 ClamAV
2. Windows 下优先使用 pinned 官方发布物：
   - `clamav-1.4.3.win.x64.zip`
   - `clamav-1.4.3.win.x64.zip.sig`
3. 在手动下载之前，先确认当前网络链路是否适合 GitHub release 大文件：
   - 当前已确认官方 release 元数据可获取
   - 当前已确认官方 SHA256 可获取
   - 当前已确认小型 `.sig` 文件可通过 GitHub assets API 下载
   - 当前已确认大型 Windows zip 的 release asset 下载链路不可用或极慢
   - 如果还要重试下载，不要反复硬挂；先切换到更适合 GitHub release 大文件的节点或代理规则，再重新尝试
4. 手动下载后先校验 SHA256：
   - `5c86a6ed17e45e5c14c9c7c7b58cfaabcdee55a195991439bb6b6c6618827e6c`
5. 解压或安装到你自己的本机路径，例如：
   - `C:\Tools\ClamAV\clamscan.exe`
   - `C:\Tools\ClamAV\db\`
6. 保持 `config/scanbox.toml` 作为仓库默认配置，不要把单机绝对路径直接写回这里
7. 在当前机器创建或更新：
   - `config/scanbox.local.toml`
8. 只覆盖当前机器需要的键，例如：

```toml
[engines.clamav]
executable = "C:\\Users\\Lancelot\\Desktop\\安装包\\clamav-1.4.3.win.x64\\clamscan.exe"
```

9. `database_dir` 默认可以继续使用仓库里的相对路径：
   - `.local-tools\clamav\db`
10. 当前仓库还提供了 `freshclam` 模板和本机配置两层：
   - 模板：`config/clamav/freshclam.conf`
   - 本机：`config/clamav/freshclam.local.conf`
11. 如果官方 Windows 包里带有 `freshclam.exe`，用它把签名库初始化到 `database_dir`，示例：

```powershell
& 'C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\freshclam.exe' --config-file 'C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf' --stdout --verbose --show-progress
```

12. 如果 `freshclam` 输出里出现 `https_proxy` / `all_proxy` 指向死掉的本地端口，例如 `127.0.0.1:9`，只对当前命令临时清空这些变量后再重试：

```powershell
$env:https_proxy=''; $env:HTTPS_PROXY=''; $env:http_proxy=''; $env:HTTP_PROXY=''; $env:all_proxy=''; $env:ALL_PROXY=''
& 'C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\freshclam.exe' --config-file 'C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf' --stdout --verbose --show-progress
```

13. 跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

### 6.4.1 `verify_env.ps1` 里 ClamAV 报错怎么理解

- `verify_env.ps1` 默认先读 `config/scanbox.toml`，再自动叠加同目录下的 `config/scanbox.local.toml`，最后再应用环境变量覆盖
- `executable_missing`
  - `engines.clamav.executable` 指向的 `clamscan.exe` 不存在
- `configured_path_invalid`
  - 配置路径存在，但类型不对
  - 例如把 `executable` 指到了目录，或把 `database_dir` 指到了普通文件
- `database_missing`
  - `database_dir` 不存在，还没有初始化到这个路径
- `database_empty`
  - `database_dir` 存在，但里面没有实际数据库文件

处理顺序建议固定为：

1. 先确认 `clamscan.exe` 路径
2. 再确认 `database_dir` 路径
3. 再确认是否已经用官方方式把签名库初始化进 `database_dir`

### 6.4.2 当前仓库内对 ClamAV 的真实结论

- 当前仓库已经为 ClamAV 预留了完整配置入口、adapter、preflight 和环境检查脚本
- 当前仓库已经在这台机器上接通了真实 ClamAV 二进制和数据库目录
- 当前仓库现在采用的是“仓库默认配置 + 本机覆盖配置”：
  - 仓库默认：`config/scanbox.toml`
  - 本机覆盖：`config/scanbox.local.toml`
- 当前环境已经确认：
  - 官方 release 元数据可获取
  - 官方 SHA256 可获取
  - 小型 `.sig` 文件可通过 assets API 下载
  - 大型 Windows zip 的 release asset 下载链路不稳定，因此当前 zip 是手动获取并校验通过后接入的
  - 真实 `clamscan.exe` 位于 `C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\clamscan.exe`
  - 真实 `freshclam.exe` 位于 `C:\Users\Lancelot\Desktop\安装包\clamav-1.4.3.win.x64\freshclam.exe`
  - 当前数据库目录位于 `C:\Users\Lancelot\Desktop\antivirus_program\.local-tools\clamav\db`
  - 当前 `freshclam` 本机配置位于 `C:\Users\Lancelot\Desktop\antivirus_program\config\clamav\freshclam.local.conf`
- 因此当前状态应理解为：
  - ScanBox 在这台机器上已经接通真实 ClamAV
  - 后续如果你移动了解压目录，只需要同步更新 `config/scanbox.local.toml`

### 6.5 capa 怎么接入

实际步骤：

1. 从 `docs/dependencies.md` 记录的官方来源获取 capa
2. Windows 下优先使用 pinned 官方产物：
   - `capa-v9.3.1-windows.zip`
3. 仓库默认配置继续保留通用值：
   - `config/scanbox.toml`
   - `engines.capa.executable = C:\Tools\capa\capa.exe`
4. 当前机器不要改仓库默认值，优先打开：
   - `config/scanbox.local.toml`
5. 只覆盖当前机器实际可用的 executable，例如：

```toml
[engines.capa]
executable = ".local-tools\\capa\\capa-v9.3.1\\capa.exe"
```

6. `rules_dir` 和 `manifest` 默认继续使用仓库内 vendored 快照：
   - `rules/capa/bundled/`
   - `rules/capa/manifest.json`
7. 当前仓库里已经把 pinned 官方 `capa-rules v9.3.0` vendor 进来了，所以接通 `capa` 时通常只需要补 executable，不需要再改 rules 路径
8. 当前实现会在运行 `capa.exe` 时把临时解包目录固定到仓库内可写路径：
   - `.local-tools/capa/runtime-tmp`
   - 这是为了避免 PyInstaller 单文件版 `capa.exe` 因默认临时目录不可写而启动失败
9. 接通后先跑：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\.venv\Scripts\python.exe
```

10. 验收重点不是“必须报恶意”，而是：
   - `engines.capa.state = "ok"`
   - `raw_summary` 里能看到真实 `capa` 执行摘要
11. 只有在你真的要改仓库默认值时，才回到 `config/scanbox.toml`

### 6.6 capa-rules 怎么接入

当前仓库里 `rules/capa/bundled/` 已经是 vendored 官方快照。以后如果要更新版本，按这个顺序做：

1. 从 `docs/dependencies.md` 里的官方来源获取固定版本 `capa-rules`
2. 不要追踪 `main/master`
3. 将固定快照内容放入：

```text
rules/capa/bundled/
```

4. 更新：

```text
rules/capa/manifest.json
```

至少同步这些字段：

- `version`
- `source`
- `pinned_ref`
- `vendor_status`
- `vendored_at`
- `rule_count`

其中 `rule_count` 的口径固定为：

- 只统计 `rules/capa/bundled/` 下真正可供 capa 使用的规则文件
- 当前统一按 `.yml` / `.yaml` 文件统计
- 不统计 README、占位文件、隐藏文件或说明文件

### 6.7 YARA 规则怎么接入

当前 ScanBox v1 主要走项目内 bundled YARA 规则。

你平时做的是：

1. 修改或新增 `rules/yara/bundled/*.yar`
2. 同步更新 `rules/yara/manifest.json`
3. 跑 benign / eicar 样本验证命中是否符合预期

### 6.8 缺少外部依赖时 JSON 会怎样

如果缺少外部引擎或规则，通常会看到：

- `overall_status = "engine_missing"` 或 `overall_status = "engine_unavailable"`
- `issues[]` 里出现类似：
  - `executable_missing`
  - `configured_path_invalid`
  - `database_missing`
  - `manifest_missing`
  - `rules_missing`

这属于“环境未就绪”，不是扫描器崩了，也不是样本天然安全。

## 7. 如何看 JSON 结果

日常先看这 5 个字段：

- `overall_status`
- `engines`
- `hashes`
- `quarantine`
- `issues`

### 7.1 `overall_status`

这是最终统一状态。优先按这个字段判断当前结果的大方向。

常见值：

- `known_malicious`
- `suspicious`
- `clean_by_known_checks`
- `scan_error`
- `partial_scan`
- `engine_missing`
- `engine_unavailable`

### 7.2 `engines`

这里记录每个扫描器的独立结果。

重点看：

- `state`
- `detections`
- `issues`
- `raw_summary`

其中 `raw_summary` 当前应这样理解：

- 默认 `stdout` 里的 `raw_summary` 是聚焦后的执行摘要
- `--report-out` 里的 `raw_summary` 会保留更完整的原始调试信息
- 对 `capa` 来说，默认简版重点看：
  - `returncode`
  - `rule_count`
  - `runtime_temp_dir`
  - `skip_reason`
  - `analysis_summary`
- `analysis_summary` 第一轮只放稳定字段：
  - `capa_version`
  - `flavor`
  - `format`
  - `arch`
  - `os`
  - `extractor`
  - `matched_rule_count`

判断时优先看单个引擎是否：

- 真正执行了
- 被策略跳过了
- 缺少依赖
- 命中了检测

### 7.3 `hashes`

这里是基础证据字段。

当前至少看：

- `sha256`
- `md5`
- `sha1`

其中 `sha256` 是主 hash。

### 7.4 `quarantine`

这里看本次扫描的处置结果。

重点看：

- `requested_mode`
- `performed`
- `reason`
- `quarantine_path`

如果只是建议隔离但没有执行，`performed` 会是 `false`。

### 7.5 `issues`

这是全局问题列表。它通常用于区分“环境未就绪”和“扫描真正发现东西”。

#### `engine_missing` 是什么意思

表示启用的引擎或规则在预检查阶段就缺失了，例如：

- ClamAV 可执行文件不存在
- YARA 规则目录不存在
- manifest 不存在

这种情况优先处理环境，不要先讨论样本安全性。

#### `engine_unavailable` 是什么意思

表示引擎存在，但运行时不可用，例如：

- 数据库未初始化
- 引擎返回运行时错误
- JSON 输出损坏

这通常是“装了，但没装好”或者“规则/库不可用”。

#### `partial_scan` 是什么意思

表示某些启用且适用的步骤没有完整完成，例如：

- 某个引擎超时
- 某个步骤出错

这不是 clean，也不是完整成功扫描。

#### `clean_by_known_checks` 不代表什么

`clean_by_known_checks` 只表示：

- 启用且适用的已知检查没有发现已知恶意或可疑证据

它 **不代表绝对安全**。

#### `known_malicious` 在当前项目里一般由什么触发

当前项目里，常见触发来源是：

- ClamAV 明确恶意签名命中
- YARA 高置信恶意规则命中

目前仓库内自带的 `eicar.com` 样本会通过 bundled YARA 规则触发一个稳定的 `known_malicious` 演示路径。

## 8. 当前已知边界与限制

这部分不是 TODO，而是当前真实边界。

- v1 **只支持单文件**
- v1 默认是 **CLI**
- v1 脚本文件默认 **不走 capa**
- v1 的真实 ClamAV / capa 能力取决于本机是否安装对应外部依赖
- 当前 `rules/capa/bundled/` 已经是完整官方 `capa-rules v9.3.0` 快照
- 当前 `rules/capa/manifest.json` 应明确显示 `vendor_status = "vendored"`，并保持 `rule_count` 与实际规则文件数一致
- 当前“开发态可运行”**不等于**“日用完整产品”
- 当前更适合做：
  - 流水线验证
  - JSON 报告验证
  - adapter 扩展
  - 规则管理
- 当前不适合直接当作：
  - 完整桌面产品
  - 可直接分发给普通用户的一键版

## 9. 推荐维护流程

以后每次维护，建议固定按下面顺序走。

### 9.1 改之前

先确认当前仓库根目录：

```powershell
Set-Location C:\Users\Lancelot\Desktop\antivirus_program
```

然后先跑：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

确认当前基线是绿的。

### 9.2 改动时

按任务选择入口：

- 改仓库默认配置：先改 `config/scanbox.toml`
- 改本机路径：先改 `config/scanbox.local.toml`
- 改规则：先改 `rules/yara/bundled/` 或 `rules/capa/bundled/`
- 改引擎调用：改 `src/scanbox/adapters/`
- 改归类逻辑：改 `src/scanbox/pipeline/verdicts.py`
- 改 JSON：改 `src/scanbox/core/models.py` 和 `src/scanbox/reporting/json_report.py`

### 9.3 改完先跑测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### 9.4 再跑三个固定样本

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

### 9.5 看结果时重点看什么

1. `hello.txt`
   - 应该是结构化 JSON
   - 通常不会命中恶意
   - 如果外部引擎缺失，常见是 `engine_missing`
2. `script.ps1`
   - 必须是结构化 JSON
   - `capa` 应该默认跳过
   - `raw_summary` 应包含脚本跳过原因
3. `eicar.com`
   - 应该能稳定走恶意命中演示路径
   - 当前项目里通常通过 YARA 规则命中 `known_malicious`

### 9.6 最后再决定是否继续改

如果这三类样本都符合预期，再继续做下一轮修改。

## 10. 常见误区与排错

### 10.1 `pytest` 能过，但 `python -m scanbox` 不能跑

这在 `src` 布局项目里很常见。

原因通常是：

- 测试通过依赖 `tests/conftest.py` 把 `src` 注入了 `sys.path`
- 但开发态 CLI 需要项目本身已经安装到当前 venv

正确处理方式：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

不要把 `PYTHONPATH=src` 当成长期正式修复。

### 10.2 未安装外部引擎导致 `engine_missing`

如果 JSON 里看到：

- `overall_status = "engine_missing"`
- `issues[]` 里有 `executable_missing` / `configured_path_invalid` / `rules_missing` / `manifest_missing`

这通常表示：

- 程序能跑
- 但外部依赖没接好

这不是主程序崩溃。

### 10.3 PowerShell 执行策略拦截脚本

如果 `.ps1` 脚本被拦截，直接用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_env.ps1
```

### 10.4 `src` 布局项目需要 `pip install -e .`

这是 ScanBox 现在的标准开发态安装方式。

只装 requirements 不够，日常还要做：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

### 10.5 JSON 输出在 `stdout`，日志在 `stderr`

如果你要把 JSON 管道给别的工具，不要把调试输出混进去。

当前设计是：

- JSON 报告走 `stdout`
- 诊断/警告应该走 `stderr`
- 默认 `stdout` 输出聚焦版 JSON，不再默认承载完整 `capa raw_summary.meta`
- 如果要保留完整调试信息，使用 `--report-out`

### 10.6 没命中不代表绝对安全

这是 ScanBox v1 的核心边界之一。

即使结果是：

- `clean_by_known_checks`

也只能解释为：

- 启用且适用的已知检查没有发现已知恶意

不能解释为：

- 文件绝对安全

## 11. 维护者最短路径

如果你这次打开仓库只是想快速恢复上下文，直接按下面顺序做：

1. 先看冻结快照：`docs/milestones/scanbox-v1-freeze.md`
2. 再看本文档：`docs/operations.md`
3. 先跑一键验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
```

4. 如果只想手动复核，再跑测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

5. 再单独跑三个样本：

```powershell
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\hello.txt
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\benign\script.ps1
.\.venv\Scripts\python.exe -m scanbox scan .\tests\fixtures\eicar\eicar.com
```

6. committed golden outputs 在：

```text
docs/milestones/golden/
```

7. 本地 `reports/` 只用于复盘，不要把它们当 committed baseline。
## 12. Quarantine lifecycle

V2 Phase 1 adds a dedicated quarantine management surface on top of the existing scan-time move action.

### 12.1 Commands

```powershell
.\.venv\Scripts\python.exe -m scanbox quarantine list
.\.venv\Scripts\python.exe -m scanbox quarantine restore <scan_id>
.\.venv\Scripts\python.exe -m scanbox quarantine delete <scan_id> --yes
```

### 12.2 What `list` shows

`scanbox quarantine list` intentionally returns only record-level summaries in Phase 1. It does not expand the full append-only `events` history.

Each record summary includes:

- `scan_id`
- `state`
- `original_path`
- `quarantine_path`
- `hashes.sha256`
- `moved_at`
- `audit_path`
- `payload_exists`

### 12.3 State rules

Lifecycle states are:

- `quarantined`
- `restored`
- `deleted`
- `unknown`

Legacy compatibility is conservative:

- if the payload still exists and the audit sidecar has no explicit `state`, the record is inferred as `quarantined`
- if the payload does not exist and the audit sidecar has no explicit `state`, the record becomes `unknown`
- `unknown` records carry structured issues such as `legacy_state_missing`

### 12.4 Restore safety

- Default locator: `scan_id`
- Default restore target: the stored `original_path`
- If the restore target already exists, restore is rejected
- Restore does not auto-rename and does not overwrite existing files
- If the target parent directory does not exist, restore is rejected instead of creating directories implicitly

### 12.5 Delete safety

- `delete` requires explicit `--yes`
- There is no interactive prompt in Phase 1
- There is no batch delete in Phase 1
- Delete removes only the quarantined payload
- The audit sidecar remains in place and is updated to `state = deleted`

### 12.6 Audit behavior

The audit sidecar remains the single source of truth for quarantine lifecycle data.

Phase 1 minimum audit fields include:

- `scan_id`
- `overall_status`
- `hashes`
- `original_path`
- `quarantine_path`
- `moved_at`
- `reason`
- `state`
- `state_changed_at`
- `restore_target_path`
- `delete_reason`
- `events`

`events` are append-only:

- successful restore/delete operations append a new event
- previous events are preserved
- failed restore/delete attempts do not rewrite audit history

### 12.7 V2.1 freeze and acceptance boundary

Treat quarantine lifecycle as a separate small milestone from the frozen v1 scanning baseline.

Use these entrypoints:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v1.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
```

Interpretation:

- `acceptance_v1.ps1` verifies the scanning baseline
- `acceptance_v2_quarantine.ps1` verifies quarantine lifecycle only

Important boundary:

- the repo-root `quarantine/` directory is local workstation state, not committed baseline
- V2.1 acceptance uses its own timestamped output directory and its own quarantine directory for the run
- do not treat local audit sidecars or payloads under repo-root `quarantine/` as golden outputs
