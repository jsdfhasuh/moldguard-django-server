# MoldGuard 知识库与 Django 对齐说明

- **版本**：V1.0
- **日期**：2026-08-12
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`
- **目的**：明确知识库能够支持的业务、不能直接用于自动决策的内容，以及 Django 需要增加的数据模型、规则治理和接口。

---

## 1. 知识库内容概览

上传包包含 14 个文件：

```text
00_知识库索引与使用说明.md
01_模具保养业务流程.md
02_保养提醒_寿命与闲置规则.md
03_注塑模具保养标准.md
04_钣金模具保养标准.md
05_模具保养点检标准.md
06_模具故障与维修工时标准.md
07_模具储放_安全与记录规范.md
08_外部公司注塑三级保养参考.md
09_知识条目元数据与检索规则.md
99_规则冲突与待确认事项.md
MoldGuard_KB_结构化条目V0.1.jsonl
MoldGuard_模具保养知识库_审阅总稿V0.1.md
README_上传与使用建议.txt
```

结构化 JSONL 共 **353 条**知识条目，按类型统计：

| 知识类型 | 数量 |
|---|---:|
| 保养标准 | 99 |
| 故障与工时 | 79 |
| 知识说明 | 31 |
| 触发与寿命规则 | 27 |
| 外部参考 | 27 |
| 点检标准 | 26 |
| 知识库实施规则 | 24 |
| 数据治理 | 17 |
| 业务流程 | 13 |
| 储放与安全 | 10 |

主要业务规模：

- 注塑点检 11 条；
- 钣金点检 11 条；
- 注塑故障与维修工时 38 条；
- 钣金故障与维修工时 40 条；
- 注塑二保/三保零件明细 51 条；
- 钣金二保/三保明细 22 条；
- 外部 C 级维修触发事项 24 条；
- 规则冲突与数据治理事项 16 条。

---

## 2. 权威性审查结果

结构化条目的权威状态为：

| authority | approval_status | 数量 |
|---|---|---:|
| `INTERNAL_SOURCE` | 原文录入待确认 | 115 |
| `INTERNAL_SOURCE` | 待业务确认 | 126 |
| `INTERNAL_SOURCE` | 待核对转写 | 12 |
| `PROJECT_REQUIREMENT` | 项目约束 | 55 |
| `PROJECT_REQUIREMENT` | 原文录入待确认 | 1 |
| `EXTERNAL_REFERENCE` | 外部参考 | 27 |
| `PENDING_CONFIRMATION` | 待业务确认 | 17 |

当前知识包中没有标记为 `INTERNAL_CONFIRMED` 的业务规则。

因此必须执行以下原则：

1. 知识库正文可以用于解释、检索、邮件和现场指导；
2. `INTERNAL_SOURCE` 不能自动视为现行正式规则；
3. `PENDING_CONFIRMATION` 不能驱动自动预警、自动派工或自动结单；
4. `EXTERNAL_REFERENCE` 只能作为补充说明，不能覆盖内部标准；
5. 参赛演示所需规则必须在 Django 中单独标记为 `DEMO_APPROVED`；
6. 生产环境只允许 `INTERNAL_CONFIRMED` 规则驱动业务。

---

## 3. 发现的主要规则冲突

### 3.1 注塑保养周期存在多套体系

知识库同时保留：

- 按开发吨位：小于 1000 吨每 5 万模次，1000 吨及以上每 3 万模次；
- 按模具类别：精密复杂 3 万、普通简单 5 万、小型 10 万基础保养；
- 全面精度维护：9 万、15 万、30 万；
- 零件级二保/三保明细：4 万、5 万、9 万、10 万等多种值；
- 每 2 个月一次的时间提醒；
- 修模、换镶件、上传保养记录等周期复位事件。

Django 不得将这些规则压缩成一个 `maintenance_threshold` 字段，也不得静默选择一个版本覆盖其他版本。

### 3.2 钣金保养周期也存在版本差异

知识库同时存在：

- 成型类 15 万；
- 冲孔落料类、连续模类 40 万；
- 边板类 6 万或 40 万；
- 明细表中的二保/三保 8 万、16 万、20 万、32 万、40 万等。

一保、二保、三保必须分别建模，不能共用一个阈值。

### 3.3 寿命提醒与保养提醒必须分离

知识库中的一级至四级模具寿命提醒使用设计寿命和型腔数计算，属于寿命/报废评估；日常保养提醒用于维护计划。Django 应使用不同的 `alert_type`，不能把寿命预警当成保养到期。

### 3.4 外部 A/B/C 体系不得自动映射

外部资料使用 A、B、C 三级保养；内部资料使用一保、二保、三保或基础保养、全面维护。Django 可以保存外部参考标识，但禁止自动映射为内部等级。

---

## 4. Django 数据模型必须调整

## 4.1 Mold 增补字段

除原有模具编号、名称、类型、等级、类别、腔数、位置和累计模次外，建议增加：

- `mold_code_prefix`：如 `LC`；
- `part_name`：零件名称；
- `model_code`：机型或产品编码；
- `development_tonnage`：开发吨位；
- `cavity_layout`：保留 `1*4` 等源表表达；
- `material_tags`：玻纤、不锈钢、铝板等；
- `feature_tags`：磨砂面、薄细结构、关键装配尺寸等；
- `design_life_count`：设计寿命；
- `life_extension_count`：延期模数；
- `last_production_at`；
- `production_count_updated_at`；
- `idle_since`；
- `has_backup_mold`。

这些字段用于吨位规则、类别规则、LC 编码、寿命提醒、闲置判断和增强点检检索。

## 4.2 规则模型由单表升级为版本化规则体系

建议模型：

```text
MaintenanceScheme
MaintenanceLevel
MaintenanceRule
MaintenanceTriggerPoint
RuleSource
RuleConflict
RuleApprovalRecord
```

`MaintenanceRule` 至少包含：

```text
rule_id
rule_family
trigger_type
mold_type
mold_category
mold_code_prefix
exact_mold_id
part_name
tonnage_min
tonnage_max
maintenance_level_code
count_basis
count_threshold
time_threshold_days
standard_hours
reset_event
source_file
source_location
authority
approval_status
rule_version
effective_from
effective_to
priority
is_active
```

推荐枚举：

```text
rule_family:
  MAINTENANCE_REMINDER
  LIFE_REMINDER
  DAILY_INSPECTION
  IDLE_MANAGEMENT
  RESET_RULE

trigger_type:
  COUNT
  TIME
  EVENT
  MANUAL
  COMPOSITE

approval_status:
  DRAFT
  PENDING_CONFIRMATION
  DEMO_APPROVED
  INTERNAL_CONFIRMED
  EXTERNAL_REFERENCE
  DISABLED
```

自动业务只允许：

```text
DEMO 环境：DEMO_APPROVED、INTERNAL_CONFIRMED
生产环境：INTERNAL_CONFIRMED
```

其他状态只允许展示来源或要求人工确认。

## 4.3 增加保养计划层

知识库流程在工单前存在“保养计划制定、计划确认、送模”三个业务阶段，因此需要增加：

```text
MaintenancePlan
PlanCloseAttempt
MoldDeliverySchedule
```

保养计划支持：

- 自动触发；
- 手动提交；
- 管理员确认需要保养；
- 关闭计划并记录原因；
- 两次关闭机会的审计；
- 计划部确定送模时间和要求交模时间；
- 分厂确认已送模；
- 送模后创建或激活工单。

“两次关闭机会”的统计范围尚未确认，因此必须配置化，并在演示规则中明确按计划还是按模具周期统计。

## 4.4 增加点检结果模型

知识库提供 22 条点检标准。Django 不保存平台知识库的完整点检正文，但必须保存本次工单实际使用的点检快照和执行结果：

```text
InspectionTemplateSnapshot
InspectionSnapshotItem
InspectionSubmission
InspectionResult
```

每项结果：

```text
PASS
FAIL
NOT_APPLICABLE
```

约束：

- `NOT_APPLICABLE` 必须由执行人员选择并填写原因；
- `FAIL` 必须填写异常说明；
- 可保存照片或外部附件引用；
- 未提交点检不得报完工；
- 任一关键项失败不得直接验收完成，应转修模。

## 4.5 增加修模分流

建议模型：

```text
RepairReferral
FaultStandard
FaultMatchCandidate
```

知识库中的 78 条故障与维修工时只包含故障分类、描述和标准工时，没有根因、维修步骤、备件和安全要求。因此：

- Django 只进行精确匹配和候选匹配；
- 匹配必须同时考虑模具类型、故障类型和描述；
- “毛刺”“毛剌”“零件毛刺大”等不能自动合并；
- 未精确命中时返回候选项，由人员确认；
- 不得默认使用 5 小时；
- 修模完成后可以触发保养周期复位，但必须满足批准的复位规则。

## 4.6 强化知识快照

建议增加：

```text
KnowledgeCatalogRelease
KnowledgeSnapshot
KnowledgeSnapshotItem
```

`KnowledgeCatalogRelease` 保存：

- `catalog_version`，如 `kb-v0.1`；
- 上传包文件名；
- 文件 SHA-256；
- 条目数量；
- 发布状态；
- 导入时间。

每个 `KnowledgeSnapshotItem` 保存：

- `knowledge_id`；
- 标题；
- 来源文件；
- 来源位置；
- authority；
- approval_status；
- rule_version；
- 内容哈希；
- 本次用途：保养项目、点检、安全、验收、故障或工时。

Django 不保存整个向量知识库，但必须能证明本次工单使用了哪些条目。

---

## 5. 工单与状态机调整

知识库推荐的流程为：

```text
待确认
→ 待送模
→ 待派工
→ 已派工
→ 执行中
→ 待点检/待报工
→ 待验收
→ 已完成
```

建议拆分为两套状态机。

### 5.1 保养计划状态

```text
DRAFT
PENDING_CONFIRMATION
CONFIRMED
CLOSED
PENDING_DELIVERY
DELIVERED
WORK_ORDER_CREATED
CANCELLED
```

### 5.2 工单状态

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
PENDING_INSPECTION
PENDING_ACCEPTANCE
TRANSFERRED_TO_REPAIR
COMPLETED
CANCELLED
```

关键约束：

- 计划未确认不得进入送模；
- 未送模不得开始拆模保养；
- 未派工不得开工；
- 未完成点检不得报完工；
- 点检失败进入 `TRANSFERRED_TO_REPAIR`；
- 验收完成后才更新保养基准并复位周期。

---

## 6. 知识包交互契约

平台应按以下顺序检索：

1. Django 返回模具类型、类别、吨位、腔数、位置和已批准 `rule_id`；
2. 平台优先按 `rule_id` 或 `knowledge_profile_code` 精确过滤；
3. 按 `mold_type + maintenance_level` 检索点检条目；
4. 按安全、储放标签补充注意事项；
5. 有异常时按模具类型、故障类型和描述查询故障工时；
6. 生成知识包；
7. 回写 Django 固化知识快照；
8. 命中 `PENDING_CONFIRMATION` 时停止自动派工，转主管确认。

知识包建议结构：

```json
{
  "work_order_id": "WO-...",
  "mold_id": "MOLD-...",
  "rule_id": "APPROVED-RULE-ID",
  "rule_authority": "DEMO_APPROVED",
  "rule_version": "V1.0",
  "trigger_basis": {
    "current_count": 0,
    "last_maintenance_count": 0,
    "threshold": 0,
    "time_threshold_days": null
  },
  "maintenance_items": [],
  "inspection_items": [
    {
      "knowledge_id": "CHK-INJ-001",
      "title": "...",
      "item": "...",
      "acceptance": "...",
      "method": "目视",
      "authority": "INTERNAL_SOURCE",
      "approval_status": "待核对转写",
      "source_file": "模具保养点检标准.xlsx",
      "source_location": "..."
    }
  ],
  "safety_notes": [],
  "completion_requirements": [],
  "knowledge_snapshot_version": "kb-v0.1"
}
```

Django 校验：

- 工单、模具和 rule_id 一致；
- 规则允许在当前环境执行；
- 每个知识条目有 ID、来源、版本和权威状态；
- PENDING_CONFIRMATION 条目需要主管明确 override；
- EXTERNAL_REFERENCE 条目不能作为强制验收标准；
- 快照版本和内容哈希可追溯。

---

## 7. JSONL 使用限制

当前 JSONL 统一包含：

```text
id
title
mold_type
knowledge_type
source_file
source_location
authority
approval_status
rule_version
content
structured_data
```

但推荐元数据中的 `mold_category`、`maintenance_level`、`applicable_code`、`effective_from`、`effective_to` 并未稳定出现在顶层字段，且大量内容只存在于 `structured_data`。

因此：

- 不建议将 JSONL 直接当作 Django 规则表导入；
- 知识库正文继续由智能体平台导入和检索；
- Django 如需轻量目录，只导入条目元数据和哈希；
- 规则数据必须经过明确映射、类型转换、冲突检查和审批后进入 `MaintenanceRule`；
- 建议后续生成 V0.2 JSONL，补齐规范化字段。

---

## 8. 业务场景对 Django 的影响

| 业务场景 | Django 必须支持的能力 |
|---|---|
| 自动保养提醒 | 多规则版本、模次/时间/事件触发、预警保存 |
| 手动提交保养 | 手动计划、原因、操作人和审计 |
| 计划确认与两次关闭 | MaintenancePlan、关闭次数、关闭原因 |
| 分厂送模 | 送模计划、要求交模时间、送达确认 |
| 派工与知识邮件 | 候选人员、最终派工、知识快照、邮件回写 |
| 保养执行 | 开工、暂停、恢复、实际工时 |
| 点检与报完工 | 点检快照、逐项结果、照片、异常说明 |
| 验收结单 | 验收记录、履历更新、周期复位 |
| 点检失败转修模 | RepairReferral、故障候选和维修工时 |
| 生产中日常保养 | DAILY_INSPECTION 任务或记录 |
| 储放、调动和恢复生产 | 储放检查、调动前保养、恢复生产前拆模保养 |
| 寿命提醒 | 独立 LIFE_REMINDER，不与保养提醒混用 |
| 闲置模具管理 | 闲置分类、备份模具、人工评估 |
| 工时与效率分析 | 真实执行工时、等待、暂停、维修工时和完成率 |

---

## 9. 参赛版规则冻结建议

知识库当前没有已确认内部规则，因此比赛版应建立独立的 `DEMO_RULESET_V1`：

- 规则状态为 `DEMO_APPROVED`；
- 明确标记非企业正式制度；
- 固定主演示模具和预期结果；
- 只为已配置的演示模具自动预警；
- 其他冲突或缺失规则返回 `RULE_NOT_APPROVED`；
- 业务确认后再升级为 `INTERNAL_CONFIRMED`。

不得把全部 `INTERNAL_SOURCE` 条目批量标记为已批准。

---

## 10. 待业务确认清单

优先确认：

1. 注塑和钣金现行保养等级体系；
2. 规则优先级：PPT、标准文本、零件明细之间的覆盖关系；
3. 模次与时间条件是任一达到还是同时达到；
4. 修模、换镶件、上传记录等哪些事件允许周期复位；
5. 两次关闭机会的统计范围和第三次处理；
6. 钣金边板类 6 万与 40 万的适用边界；
7. LC109 是否同时属于连续模和边板类；
8. 注塑明细中缺失模具编码和异常触发值；
9. 点检图片转写文本是否确认；
10. 钣金明细空白工时是否继承主行；
11. 生命周期和闲置公式；
12. 标准工时究竟按保养等级、模具、零件还是故障分别管理。

这些事项不阻止比赛使用 `DEMO_RULESET_V1`，但阻止将系统描述为已经采用企业正式生产标准。

---

## 11. 结论

知识库 V0.1 已经足以支撑：

- 保养流程说明；
- 注塑、钣金操作知识检索；
- 22 条点检内容；
- 安全和储放要求；
- 78 条故障与工时候选；
- 知识随单邮件；
- 验收和异常分流。

它尚不足以直接支撑“无人工确认的正式自动预警”，原因是规则多版本并存、关键字段缺失且当前没有 `INTERNAL_CONFIRMED` 条目。

Django 必须承担规则审批、版本匹配、计划与工单状态、点检结果、修模分流和知识快照；智能体平台继续承担知识库检索、LLM 生成和邮件发送。