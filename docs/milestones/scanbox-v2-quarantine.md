# ScanBox V2.1 Quarantine Freeze

本文档是当前 ScanBox V2.1 的阶段性 freeze 快照，目标是固定 quarantine lifecycle 已经做到哪里、如何验收、哪些内容属于仓库基线、哪些仍然只是本机产物。

## 1. 当前定位

当前 V2.1 不是新的扫描引擎阶段，而是在 v1 scanning baseline 之上，把 quarantine 从“扫描时的附带动作”推进成“可管理的生命周期子系统”。

当前 V2.1 freeze 覆盖：

- `scanbox quarantine list`
- `scanbox quarantine restore <scan_id>`
- `scanbox quarantine delete <scan_id> --yes`

当前 V2.1 不做：

- batch restore/delete
- `show`
- 自动改名恢复
- 强制覆盖恢复
- GUI
- 拖拽
- 多文件/目录
- 云服务

## 2. 当前支持的 quarantine 能力

### 2.1 主标识

默认主标识是 `scan_id`。

原因：

- 它已经是 scan report 和 audit sidecar 的稳定关联键
- 不依赖 quarantine 目录中文件名的时间戳前缀
- 恢复和删除时比 payload 文件名更适合做用户级定位

### 2.2 list

`scanbox quarantine list` 当前只输出记录级摘要，不展开完整 `events` 历史。

摘要字段固定为：

- `scan_id`
- `state`
- `original_path`
- `quarantine_path`
- `hashes.sha256`
- `moved_at`
- `audit_path`
- `payload_exists`

### 2.3 restore

`scanbox quarantine restore <scan_id>` 的安全边界：

- 默认恢复到 audit sidecar 中记录的 `original_path`
- 如果显式传 `--output-path`，恢复到显式目标
- 如果目标已存在，恢复会被拒绝
- 不自动改名
- 不自动覆盖
- 不自动创建缺失的父目录

### 2.4 delete

`scanbox quarantine delete <scan_id> --yes` 的安全边界：

- 必须显式 `--yes`
- 不交互
- 不批量
- 只删除 quarantine payload
- audit sidecar 保留并更新为 `state = deleted`

## 3. Legacy audit 兼容规则

对旧版 sidecar 的兼容采用保守规则：

- payload 存在且无显式 `state` -> 推断为 `quarantined`
- payload 不存在且无显式 `state` -> 标记为 `unknown`
- 不会草率把无状态旧记录强行解释成 `restored` 或 `deleted`

当记录被判定为 `unknown` 时，会返回结构化问题，例如：

- `legacy_state_missing`

## 4. 审计与状态变化

当前 quarantine audit sidecar 已经升级为 lifecycle 记录源。

最低字段包括：

- `audit_schema_version`
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

`events` 的规则固定为 append-only：

- restore/delete 成功时只追加新事件
- 保留旧事件
- 不覆盖、不截断历史

## 5. 和 v1 freeze 的关系

当前基线应理解为两条并行 freeze：

- v1：scanning baseline
- V2.1：quarantine lifecycle baseline

它们的关系是：

- v1 继续负责扫描主链路 freeze
- V2.1 只负责 quarantine lifecycle freeze
- `scripts/acceptance_v1.ps1` 不被污染
- V2.1 使用独立的 acceptance 脚本

## 6. V2.1 acceptance 入口

当前 V2.1 的官方验收入口应为：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\acceptance_v2_quarantine.ps1
```

第一阶段默认只验证最小 lifecycle：

1. 一条 move
2. 一条 restore
3. 一条 delete
4. list 前后状态变化

脚本运行产物写到：

```text
reports/acceptance-v2-quarantine/<timestamp>/
```

## 7. 基线边界

属于仓库基线：

- quarantine lifecycle 代码
- quarantine 单测
- 本文档
- `scripts/acceptance_v2_quarantine.ps1`
- README / operations / development 中的入口说明

不属于仓库基线：

- repo 根 `quarantine/`
- 本机实际 quarantine payload
- 本机实际 audit sidecar
- `reports/acceptance-v2-quarantine/<timestamp>/`
- 本机绝对路径
- 时间戳
- `scan_id`
- 运行时目录

## 8. 下一阶段建议

如果后续继续推进 quarantine，建议顺序为：

1. 先保持当前 V2.1 baseline 稳定
2. 如需更强可视化或追溯能力，再单独设计 `show`
3. 如需更复杂的恢复策略，再单独设计 rename/overwrite 语义
4. 不要在 freeze 收口阶段继续横向扩张功能面
