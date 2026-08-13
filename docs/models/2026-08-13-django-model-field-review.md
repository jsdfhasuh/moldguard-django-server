# MoldGuard Django 最小模型字段审查表

- **状态**：`OWNER_FIELD_REVIEW_REQUIRED`
- **版本**：V2.0
- **日期**：2026-08-13
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.1
- **服务器定位**：无角色、无鉴权、仅使用 DEMO 数据的比赛测试服务器
- **目标**：确认最终 6 个模型和字段是否还可以继续删除

---

## 1. 本次收缩结果

模型从 14 个压缩到 6 个：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

已删除：

```text
MaintenanceRule
MaintenanceCycle
CycleResetEvent
InspectionItemResult
KnowledgeSnapshot
NotificationRecord
RepairReferral
IdempotencyRecord
```

这些能力改为：

- 两条规则写在代码常量中；
- 当前周期基线直接保存在 Mold；
- 周期复位由 MaintenanceRecord 记录；
- 点检、知识和邮件字段直接保存在 WorkOrder；
- 转修模只使用 WorkOrder 状态和原因；
- 幂等通过各业务表的唯一键实现。

历史导入功能及相关字段全部删除。

---

## 2. Mold 模具

模型：`apps.molds.models.Mold`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `mold_id` | `CharField(64, unique=True)` | 是 | 模具业务编号 | 保留 |
| `mold_name` | `CharField(200)` | 是 | 展示、工单和邮件 | 保留 |
| `mold_type` | `CharField(32, choices)` | 是 | `INJECTION` / `SHEET_METAL` | 保留 |
| `development_tonnage` | `DecimalField(10,2)` | 是 | 30,000/50,000规则依据 | 保留 |
| `current_count` | `PositiveBigIntegerField` | 是 | 当前累计模次 | 保留 |
| `cycle_baseline_count` | `PositiveBigIntegerField` | 是 | 当前周期起点模次 | 保留 |
| `cycle_baseline_time` | `DateTimeField` | 是 | 当前周期起点时间 | 保留 |
| `cycle_version` | `PositiveIntegerField(default=1)` | 是 | 每次复位递增 | 保留 |
| `last_reset_type` | `CharField(32, choices)` | 是 | 初始、保养、修模、换镶件 | 保留 |
| `last_reset_at` | `DateTimeField` | 是 | 最近复位时间 | 保留 |
| `location` | `CharField(200, blank=True)` | 否 | 合并原一级/二级位置 | 保留 |
| `production_line` | `CharField(120, blank=True)` | 否 | 同产线候选排序 | 保留 |
| `status` | `CharField(32, choices)` | 是 | 在产、库存、修模、停用 | 保留 |
| `knowledge_profile_code` | `CharField(100, blank=True)` | 否 | 平台知识库精确过滤 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 | 保留 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 | 保留 |

### 已删除字段

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

其中 `last_maintenance_*` 不再单独保存；接口需要时直接返回当前周期基线。

---

## 3. Alert 提醒

模型：`apps.molds.models.Alert`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `alert_id` | `CharField(64, unique=True)` | 是 | 提醒编号 | 保留 |
| `mold` | `ForeignKey(Mold)` | 是 | 关联模具 | 保留 |
| `alert_type` | `CharField(40, choices)` | 是 | 模次到期 / 2个月提醒 | 保留 |
| `cycle_version` | `PositiveIntegerField` | 是 | 属于哪个周期 | 保留 |
| `cycle_count_snapshot` | `PositiveBigIntegerField` | 是 | 创建时周期模次 | 保留 |
| `threshold_snapshot` | `PositiveBigIntegerField(null=True)` | 否 | 模次提醒阈值 | 保留 |
| `usage_percent_snapshot` | `DecimalField(7,2, null=True)` | 否 | 展示进度 | 保留 |
| `status` | `CharField(24, choices)` | 是 | `OPEN` / `ACKNOWLEDGED` / `CLOSED` | 保留 |
| `dedupe_key` | `CharField(160, unique=True)` | 是 | 防止重复扫描 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 | 保留 |
| `closed_at` | `DateTimeField(null=True)` | 否 | 关闭时间 | 保留 |

### 已删除字段

```text
health_score
recommended_priority
recommended_deadline
notification_history
rule_foreign_key
```

规则 ID 和阈值由服务动态返回；Alert 只保存本次阈值快照。

---

## 4. Employee 模拟人员

模型：`apps.staff.models.Employee`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `employee_id` | `CharField(64, unique=True)` | 是 | 模拟工号 | 保留 |
| `employee_name` | `CharField(100)` | 是 | 展示和邮件 | 保留 |
| `email` | `EmailField(blank=True)` | 否 | 测试收件邮箱 | 保留 |
| `production_line` | `CharField(120, blank=True)` | 否 | 同产线排序 | 保留 |
| `skills_json` | `JSONField(default=list)` | 是 | 技能列表 | 保留 |
| `current_load` | `DecimalField(5,4, default=0)` | 是 | 固定演示负荷 | 保留 |
| `on_duty` | `BooleanField(default=True)` | 是 | 是否在岗 | 保留 |
| `available` | `BooleanField(default=True)` | 是 | 是否可接单 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 | 保留 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 | 保留 |

### 已删除字段

```text
team
technician_level
user_account
role
permissions
proficiency
```

候选排序只使用技能、负荷、产线和可用状态。

---

## 5. WorkOrder 工单

模型：`apps.workorders.models.WorkOrder`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `work_order_id` | `CharField(64, unique=True)` | 是 | 工单编号 | 保留 |
| `alert` | `ForeignKey(Alert, null=True)` | 否 | 来源提醒 | 保留 |
| `mold` | `ForeignKey(Mold)` | 是 | 关联模具 | 保留 |
| `status` | `CharField(40, choices)` | 是 | 工单状态 | 保留 |
| `priority` | `CharField(16, choices, default=NORMAL)` | 是 | 邮件和展示 | 保留 |
| `standard_hours` | `DecimalField(7,2, default=8)` | 是 | 预计工时 | 保留 |
| `required_finish_at` | `DateTimeField(null=True)` | 否 | 超时和邮件 | 保留 |
| `assigned_employee` | `ForeignKey(Employee, null=True)` | 否 | 最终派工人 | 保留 |
| `required_skills_json` | `JSONField(default=list)` | 是 | 候选匹配依据 | 保留 |
| `knowledge_profile_code` | `CharField(100, blank=True)` | 否 | 知识过滤编码快照 | 保留 |
| `knowledge_snapshot_json` | `JSONField(default=dict)` | 是 | 最后一次知识快照 | 保留 |
| `inspection_items_json` | `JSONField(default=list)` | 是 | 点检模板和结果 | 保留 |
| `email_recipient` | `EmailField(blank=True)` | 否 | 最后一次收件人 | 保留 |
| `email_status` | `CharField(20, default=NOT_SENT)` | 是 | 最后一次发送状态 | 保留 |
| `email_message_id` | `CharField(160, blank=True)` | 否 | 平台消息ID | 保留 |
| `email_sent_at` | `DateTimeField(null=True)` | 否 | 发送时间 | 保留 |
| `email_error` | `TextField(blank=True)` | 否 | 最后一次失败原因 | 保留 |
| `assigned_at` | `DateTimeField(null=True)` | 否 | 派工时间 | 保留 |
| `started_at` | `DateTimeField(null=True)` | 否 | 开工时间 | 保留 |
| `pause_started_at` | `DateTimeField(null=True)` | 否 | 当前暂停开始 | 保留 |
| `paused_seconds` | `PositiveBigIntegerField(default=0)` | 是 | 累计暂停秒数 | 保留 |
| `reported_at` | `DateTimeField(null=True)` | 否 | 报完工时间 | 保留 |
| `accepted_at` | `DateTimeField(null=True)` | 否 | 验收完成时间 | 保留 |
| `completion_summary` | `TextField(blank=True)` | 否 | 完工说明 | 保留 |
| `repair_reason` | `TextField(blank=True)` | 否 | 转修模原因 | 保留 |
| `create_key` | `CharField(160, unique=True)` | 是 | 防止重复建单 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 | 保留 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 修改时间 | 保留 |

### 已删除字段和子表

```text
maintenance_level
plan
送模时间
主管确认
多版本知识快照
邮件主题
抄送列表
附件列表
邮件尝试历史
点检照片
独立点检表
独立知识表
独立邮件表
独立转修模表
历史导入关联
健康评分
```

### 动态计算，不落库

```text
dispatch_to_report_seconds
waiting_to_start_seconds
actual_execution_seconds
is_overdue
```

---

## 6. WorkOrderEvent 工单时间线

模型：`apps.workorders.models.WorkOrderEvent`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `work_order` | `ForeignKey(WorkOrder)` | 是 | 所属工单 | 保留 |
| `event_type` | `CharField(40)` | 是 | 派工、开工、暂停等 | 保留 |
| `from_status` | `CharField(40, blank=True)` | 否 | 原状态 | 保留 |
| `to_status` | `CharField(40, blank=True)` | 否 | 新状态 | 保留 |
| `operator_name` | `CharField(100, blank=True)` | 否 | 演示操作人文字 | 保留 |
| `remarks` | `TextField(blank=True)` | 否 | 说明 | 保留 |
| `request_key` | `CharField(160, null=True, unique=True)` | 否 | 防止重复动作 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 事件时间 | 保留 |

不建立用户外键、角色或权限。

---

## 7. MaintenanceRecord 系统履历

模型：`apps.molds.models.MaintenanceRecord`

| 字段 | Django 类型 | 必填 | 用途 | 建议 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 是 | 内部主键 | 保留 |
| `record_id` | `CharField(64, unique=True)` | 是 | 履历编号 | 保留 |
| `mold` | `ForeignKey(Mold)` | 是 | 所属模具 | 保留 |
| `work_order` | `ForeignKey(WorkOrder, null=True)` | 否 | 保养验收来源 | 保留 |
| `record_type` | `CharField(32, choices)` | 是 | 保养 / 修模 / 换镶件 | 保留 |
| `occurred_at` | `DateTimeField` | 是 | 实际完成时间 | 保留 |
| `occurred_count` | `PositiveBigIntegerField` | 是 | 完成时累计模次 | 保留 |
| `result` | `CharField(24, default=COMPLETED)` | 是 | 结果 | 保留 |
| `note` | `TextField(blank=True)` | 否 | 说明 | 保留 |
| `request_key` | `CharField(160, unique=True)` | 是 | 防止重复复位 | 保留 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 入库时间 | 保留 |

### 明确删除

```text
HISTORY_IMPORT 类型
source_file
source_record_id
content_hash
import_batch
import_row
```

该模型只记录系统运行后产生的保养、修模和换镶件事件。

---

## 8. 不建立的模型清单

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

## 9. 最终审查结论

建议直接按以上 6 个模型实施，不再增加字段。

仍可继续删除的只有 3 项：

| 可选删除项 | 删除影响 |
|---|---|
| `WorkOrder.priority` | 邮件无法直接展示任务紧急程度 |
| `WorkOrder.required_finish_at` | 无法判断工单超时 |
| `WorkOrderEvent.operator_name` | 时间线只显示动作，不显示演示操作人 |

其余字段均直接服务于当前主链路或防止重复数据。

负责人可按以下格式确认：

```text
模型范围=确认6个模型
priority=保留/删除
required_finish_at=保留/删除
operator_name=保留/删除
```