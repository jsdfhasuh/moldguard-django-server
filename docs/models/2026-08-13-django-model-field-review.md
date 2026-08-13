# MoldGuard Django 最小模型字段清单

- **状态**：`FIELD_SCOPE_FROZEN`
- **版本**：V2.1
- **日期**：2026-08-13
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.1
- **服务器定位**：无角色、无鉴权、无历史导入的比赛测试服务器

---

## 1. 最终模型

只建立 6 个持久化模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

规则使用代码常量；周期基线直接保存在 Mold；点检、知识和邮件结果直接保存在 WorkOrder；复位履历统一保存在 MaintenanceRecord。

---

## 2. Mold

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `mold_id` | `CharField(64, unique=True)` | 是 | 模具编号 |
| `mold_name` | `CharField(200)` | 是 | 展示、工单和邮件 |
| `mold_type` | `CharField(32, choices)` | 是 | `INJECTION` / `SHEET_METAL` |
| `development_tonnage` | `DecimalField(10,2)` | 是 | 30,000/50,000规则依据 |
| `current_count` | `PositiveBigIntegerField` | 是 | 当前累计模次 |
| `cycle_baseline_count` | `PositiveBigIntegerField` | 是 | 当前周期起点模次 |
| `cycle_baseline_time` | `DateTimeField` | 是 | 当前周期起点时间 |
| `cycle_version` | `PositiveIntegerField(default=1)` | 是 | 每次复位递增 |
| `last_reset_type` | `CharField(32, choices)` | 是 | 初始、保养、修模、换镶件 |
| `last_reset_at` | `DateTimeField` | 是 | 最近复位时间 |
| `location` | `CharField(200, blank=True)` | 否 | 合并后的模具位置 |
| `production_line` | `CharField(120, blank=True)` | 否 | 同产线候选排序 |
| `status` | `CharField(32, choices)` | 是 | 在产、库存、修模、停用 |
| `knowledge_profile_code` | `CharField(100, blank=True)` | 否 | 知识库过滤编码 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 |

删除：

```text
mold_level
mold_category
cavity_count
primary_location
secondary_location
knowledge_tags_json
design_life_count
idle_since
has_backup_mold
last_maintenance_count
last_maintenance_time
```

---

## 3. Alert

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `alert_id` | `CharField(64, unique=True)` | 是 | 提醒编号 |
| `mold` | `ForeignKey(Mold)` | 是 | 关联模具 |
| `alert_type` | `CharField(40, choices)` | 是 | 模次到期 / 2个月提醒 |
| `cycle_version` | `PositiveIntegerField` | 是 | 所属周期 |
| `cycle_count_snapshot` | `PositiveBigIntegerField` | 是 | 创建时周期模次 |
| `threshold_snapshot` | `PositiveBigIntegerField(null=True)` | 否 | 模次阈值，时间提醒为空 |
| `usage_percent_snapshot` | `DecimalField(7,2, null=True)` | 否 | 创建时使用率 |
| `status` | `CharField(24, choices)` | 是 | `OPEN` / `ACKNOWLEDGED` / `CLOSED` |
| `dedupe_key` | `CharField(160, unique=True)` | 是 | 扫描去重 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `closed_at` | `DateTimeField(null=True)` | 否 | 关闭时间 |

不保存健康评分、建议截止时间或通知历史。

---

## 4. Employee

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `employee_id` | `CharField(64, unique=True)` | 是 | 模拟工号 |
| `employee_name` | `CharField(100)` | 是 | 展示和邮件 |
| `email` | `EmailField(blank=True)` | 否 | 测试收件邮箱 |
| `production_line` | `CharField(120, blank=True)` | 否 | 同产线排序 |
| `skills_json` | `JSONField(default=list)` | 是 | 技能列表 |
| `current_load` | `DecimalField(5,4, default=0)` | 是 | 固定演示负荷 |
| `on_duty` | `BooleanField(default=True)` | 是 | 是否在岗 |
| `available` | `BooleanField(default=True)` | 是 | 是否可接单 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 |

不保存班组、技师等级、账号、角色和熟练度。

---

## 5. WorkOrder

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `work_order_id` | `CharField(64, unique=True)` | 是 | 工单编号 |
| `alert` | `ForeignKey(Alert, null=True)` | 否 | 来源提醒 |
| `mold` | `ForeignKey(Mold)` | 是 | 关联模具 |
| `status` | `CharField(40, choices)` | 是 | 工单状态 |
| `priority` | `CharField(16, choices, default=NORMAL)` | 是 | 邮件和展示 |
| `standard_hours` | `DecimalField(7,2, default=8)` | 是 | 预计工时 |
| `required_finish_at` | `DateTimeField(null=True)` | 否 | 超时和邮件 |
| `assigned_employee` | `ForeignKey(Employee, null=True)` | 否 | 派工人 |
| `required_skills_json` | `JSONField(default=list)` | 是 | 候选匹配 |
| `knowledge_profile_code` | `CharField(100, blank=True)` | 否 | 知识编码快照 |
| `knowledge_snapshot_json` | `JSONField(default=dict)` | 是 | 最后一份知识快照 |
| `inspection_items_json` | `JSONField(default=list)` | 是 | 点检模板和结果 |
| `email_recipient` | `EmailField(blank=True)` | 否 | 最后一次收件人 |
| `email_status` | `CharField(20, default=NOT_SENT)` | 是 | 最后一次邮件状态 |
| `email_message_id` | `CharField(160, blank=True)` | 否 | 平台消息ID |
| `email_sent_at` | `DateTimeField(null=True)` | 否 | 发送时间 |
| `email_error` | `TextField(blank=True)` | 否 | 最后一次失败原因 |
| `assigned_at` | `DateTimeField(null=True)` | 否 | 派工时间 |
| `started_at` | `DateTimeField(null=True)` | 否 | 开工时间 |
| `pause_started_at` | `DateTimeField(null=True)` | 否 | 当前暂停开始 |
| `paused_seconds` | `PositiveBigIntegerField(default=0)` | 是 | 累计暂停秒数 |
| `reported_at` | `DateTimeField(null=True)` | 否 | 报完工时间 |
| `accepted_at` | `DateTimeField(null=True)` | 否 | 验收时间 |
| `completion_summary` | `TextField(blank=True)` | 否 | 完工说明 |
| `repair_reason` | `TextField(blank=True)` | 否 | 转修模原因 |
| `create_key` | `CharField(160, unique=True)` | 是 | 防止重复建单 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 |

动态计算，不落库：

```text
派工至报工总历时
等待开工时长
实际执行时长
是否超时
```

---

## 6. WorkOrderEvent

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `work_order` | `ForeignKey(WorkOrder)` | 是 | 所属工单 |
| `event_type` | `CharField(40)` | 是 | 派工、开工、暂停等 |
| `from_status` | `CharField(40, blank=True)` | 否 | 原状态 |
| `to_status` | `CharField(40, blank=True)` | 否 | 新状态 |
| `remarks` | `TextField(blank=True)` | 否 | 说明 |
| `request_key` | `CharField(160, null=True, unique=True)` | 否 | 重复动作去重 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 事件时间 |

不保存操作人、账号或角色。

---

## 7. MaintenanceRecord

| 字段 | Django类型 | 必填 | 用途 |
|---|---|---:|---|
| `id` | `BigAutoField` | 是 | 内部主键 |
| `record_id` | `CharField(64, unique=True)` | 是 | 履历编号 |
| `mold` | `ForeignKey(Mold)` | 是 | 所属模具 |
| `work_order` | `ForeignKey(WorkOrder, null=True)` | 否 | 保养验收来源 |
| `record_type` | `CharField(32, choices)` | 是 | 保养 / 修模 / 换镶件 |
| `occurred_at` | `DateTimeField` | 是 | 完成时间 |
| `occurred_count` | `PositiveBigIntegerField` | 是 | 完成时累计模次 |
| `result` | `CharField(24, default=COMPLETED)` | 是 | 结果 |
| `note` | `TextField(blank=True)` | 否 | 说明 |
| `request_key` | `CharField(160, unique=True)` | 是 | 防止重复复位 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 入库时间 |

不支持 `HISTORY_IMPORT`，不保存文件来源或导入批次。

---

## 8. 不建立的模型

```text
User
Role
Permission
Supervisor
MaintenancePlan
DeliverySchedule
MaintenanceRule
MaintenanceCycle
CycleResetEvent
Skill
EmployeeSkill
InspectionItemResult
KnowledgeSnapshot
NotificationRecord
RepairReferral
IdempotencyRecord
FaultStandard
HistoryImportBatch
HistoryImportRow
AuditLog
AnalyticsResult
```

---

## 9. 最终结论

```text
模型数量：6
字段范围：已冻结
历史导入：已删除
健康评分：已删除
角色与鉴权：已删除
```

`priority` 和 `required_finish_at` 保留，因为邮件需要表达任务紧急程度和完成时间；其余可选展示字段均已删除。