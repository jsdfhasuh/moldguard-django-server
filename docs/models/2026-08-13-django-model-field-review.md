# MoldGuard Django 模型字段清单

- **状态**：`FIELD_SCOPE_FROZEN_KB_ALIGNED`
- **版本**：V3.0
- **日期**：2026-08-13
- **适用计划**：V4.2
- **知识库基线**：`MOLDGUARD-KB-1.2`

只建立 6 个持久化模型；复杂点检、知识和邮件内容使用 JSON 字段保存。

---

## 1. Mold

| 字段 | Django 类型 | 必填 | 说明 |
|---|---|---:|---|
| `mold_id` | `CharField(64, unique=True)` | 是 | 模具编号 |
| `mold_name` | `CharField(200)` | 是 | 模具名称 |
| `mold_type` | `CharField(32, choices)` | 是 | `INJECTION` / `SHEET_METAL` |
| `effective_mold_cycles` | `PositiveBigIntegerField` | 是 | 当前累计有效模次；服务器不做型腔换算 |
| `baseline_effective_mold_cycles` | `PositiveBigIntegerField` | 是 | 当前周期基准模次 |
| `baseline_maintenance_at` | `DateTimeField` | 是 | 当前周期基准时间 |
| `cycle_version` | `PositiveIntegerField(default=1)` | 是 | 每次周期复位递增 |
| `first_production_at` | `DateTimeField(null=True)` | 否 | 注塑 2 个月规则的首次起算点 |
| `development_tonnage` | `DecimalField(10,2,null=True)` | 否 | 注塑 30K/50K 规则；注塑自动扫描时必需 |
| `mold_category` | `CharField(40,null=True)` | 否 | 钣金 `FORMING/PUNCH_BLANKING/CONTINUOUS/SIDE_PANEL` |
| `mold_type_code` | `CharField(32,null=True)` | 否 | LC101 等编码 |
| `level_1_location` | `CharField(120,null=True)` | 否 | 一级位置，仅定位信息 |
| `level_2_location` | `CharField(120,null=True)` | 否 | 二级位置，仅定位信息 |
| `production_line` | `CharField(120,null=True)` | 否 | 候选人员同产线排序 |
| `output_updated_at` | `DateTimeField(null=True)` | 否 | 连续 2 年未更新产量判断 |
| `status` | `CharField(32, choices)` | 是 | `ACTIVE/INACTIVE/UNDER_REPAIR/DISABLED` |
| `knowledge_profile_code` | `CharField(100,null=True)` | 否 | 平台检索知识的精确过滤编码 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 更新时间 |

派生，不落库：

```text
cycle_mold_cycles
tonnage_band
threshold_count
next_due_count
next_due_time
```

---

## 2. Alert

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `alert_id` | `CharField(64, unique=True)` | 是 | 提醒编号 |
| `mold` | `ForeignKey(Mold)` | 是 | 模具 |
| `rule_id` | `CharField(100)` | 是 | 知识库规则 ID |
| `alert_type` | `CharField(40)` | 是 | `COUNT_TRIGGER/TIME_TRIGGER/MANUAL` |
| `cycle_version` | `PositiveIntegerField` | 是 | 触发时周期版本 |
| `cycle_mold_cycles_snapshot` | `PositiveBigIntegerField(null=True)` | 否 | 模次触发快照 |
| `threshold_count` | `PositiveBigIntegerField(null=True)` | 否 | 模次阈值 |
| `trigger_reason` | `TextField` | 是 | 触发原因 |
| `status` | `CharField(24)` | 是 | `OPEN/CLOSED` |
| `dedupe_key` | `CharField(200, unique=True)` | 是 | 防止重复扫描 |
| `triggered_at` | `DateTimeField` | 是 | 触发时间 |
| `closed_at` | `DateTimeField(null=True)` | 否 | 关闭时间 |

达到自动触发条件时，同时创建 WorkOrder。

---

## 3. Employee

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `employee_id` | `CharField(64, unique=True)` | 是 | 模拟员工编号 |
| `employee_name` | `CharField(120)` | 是 | 姓名 |
| `email` | `EmailField` | 是 | 测试收件邮箱 |
| `production_line` | `CharField(120,null=True)` | 否 | 同产线排序 |
| `skills_json` | `JSONField(default=list)` | 是 | 技能列表 |
| `current_load` | `DecimalField(5,4)` | 是 | 0—1 |
| `on_duty` | `BooleanField(default=True)` | 是 | 是否在岗 |
| `available` | `BooleanField(default=True)` | 是 | 是否可派工 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 更新时间 |

---

## 4. WorkOrder

### 4.1 主字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `work_order_id` | `CharField(64, unique=True)` | 是 | 工单编号 |
| `alert` | `ForeignKey(Alert,null=True)` | 否 | 手动工单可为空 |
| `mold` | `ForeignKey(Mold)` | 是 | 模具 |
| `parent_work_order` | `ForeignKey('self',null=True)` | 否 | 关联修模任务的原工单 |
| `linked_repair_order` | `ForeignKey('self',null=True,related_name='+')` | 否 | 原工单关联的修模任务 |
| `rule_id` | `CharField(100)` | 是 | 触发规则 |
| `work_order_type` | `CharField(48)` | 是 | 见枚举 |
| `status` | `CharField(40)` | 是 | 工单状态 |
| `assignee` | `ForeignKey(Employee,null=True)` | 否 | 被派工人员 |
| `required_finish_at` | `DateTimeField(null=True)` | 否 | 要求完成时间 |
| `create_key` | `CharField(200, unique=True)` | 是 | 防重复建单 |

工单类型：

```text
CYCLE_COUNT_MAINTENANCE
CYCLE_TIME_MAINTENANCE
REPAIR_SYNC_MAINTENANCE
REPAIR_TASK
LIGHTWEIGHT_DAILY
LIGHTWEIGHT_PRE_PRODUCTION
LIGHTWEIGHT_POST_PRODUCTION
LIGHTWEIGHT_FIXED_FREQUENCY
STORAGE_INSPECTION
```

### 4.2 触发与周期快照

| 字段 | 类型 | 必填 |
|---|---|---:|
| `effective_mold_cycles_snapshot` | `PositiveBigIntegerField` | 是 |
| `baseline_effective_mold_cycles_before` | `PositiveBigIntegerField` | 是 |
| `baseline_maintenance_at_before` | `DateTimeField` | 是 |
| `cycle_mold_cycles_snapshot` | `PositiveBigIntegerField(null=True)` | 否 |
| `threshold_count` | `PositiveBigIntegerField(null=True)` | 否 |
| `trigger_reason` | `TextField` | 是 |
| `triggered_at` | `DateTimeField` | 是 |
| `reset_count_cycle` | `BooleanField(default=False)` | 是 |
| `reset_time_cycle` | `BooleanField(default=False)` | 是 |

### 4.3 知识、点检与邮件

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `knowledge_snapshot_version` | `CharField(64)` | 是 | `MOLDGUARD-KB-1.2` |
| `knowledge_package_json` | `JSONField(default=dict)` | 是 | 邮件和报工页面使用的一份知识包 |
| `inspection_results_json` | `JSONField(default=list)` | 是 | 点检模板和结果 |
| `email_recipient` | `EmailField(null=True)` | 否 | 收件人 |
| `email_subject` | `CharField(240,null=True)` | 否 | 邮件主题 |
| `email_status` | `CharField(24,default='NOT_SENT')` | 是 | `NOT_SENT/SENT/FAILED` |
| `email_message_id` | `CharField(200,null=True)` | 否 | 平台消息 ID |
| `email_sent_at` | `DateTimeField(null=True)` | 否 | 发送时间 |
| `email_error` | `TextField(null=True)` | 否 | 失败信息 |

### 4.4 报工字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `report_method` | `CharField(24,default='WEB_FORM')` | 是 | 当前固定网页表单 |
| `report_form_schema_version` | `CharField(32,default='REPORT-FORM-1.0')` | 是 | 表单版本 |
| `report_type` | `CharField(24,null=True)` | 否 | `NORMAL/ABNORMAL` |
| `report_summary` | `TextField(null=True)` | 否 | 完成情况 |
| `abnormal_items_json` | `JSONField(default=list)` | 是 | 异常项目 |
| `photos_json` | `JSONField(default=list)` | 是 | 可选照片引用 |
| `parts_replaced_json` | `JSONField(default=list)` | 是 | 更换件 |
| `source_fault_id` | `CharField(100,null=True)` | 否 | 故障源表 ID |
| `fault_type` | `CharField(120,null=True)` | 否 | 故障类型 |
| `fault_description` | `TextField(null=True)` | 否 | 原始描述 |
| `standard_repair_hours` | `DecimalField(8,2,null=True)` | 否 | 标准工时 |
| `actual_work_hours` | `DecimalField(8,2,null=True)` | 否 | 实际工时；报工时必填 |
| `abnormal_next_action` | `CharField(40,null=True)` | 否 | `CONTINUE_PROCESSING/CREATE_REPAIR_TASK` |
| `repair_reason` | `TextField(null=True)` | 否 | 转修模原因 |

`report_url` 不落库，按服务基地址和 `work_order_id` 动态生成：

```text
/report/{work_order_id}
```

### 4.5 时间字段

```text
assigned_at
started_at
pause_started_at
paused_seconds
completed_at
reported_at
created_at
updated_at
```

---

## 5. WorkOrderEvent

```text
work_order
event_type
from_status
to_status
operator_id          # 可空，仅展示
remarks
request_key          # 可空；重试时复用
created_at
```

---

## 6. MaintenanceRecord

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `record_id` | `CharField(64,unique=True)` | 是 | 履历编号 |
| `mold` | `ForeignKey(Mold)` | 是 | 模具 |
| `work_order` | `ForeignKey(WorkOrder,null=True)` | 否 | 来源工单 |
| `record_type` | `CharField(48)` | 是 | 与工单类型对应 |
| `occurred_at` | `DateTimeField` | 是 | 正常报工完成时间 |
| `effective_mold_cycles_snapshot` | `PositiveBigIntegerField` | 是 | 报工时有效模次 |
| `baseline_count_before` | `PositiveBigIntegerField` | 是 | 复位前模次基准 |
| `baseline_time_before` | `DateTimeField` | 是 | 复位前时间基准 |
| `baseline_count_after` | `PositiveBigIntegerField` | 是 | 复位后模次基准 |
| `baseline_time_after` | `DateTimeField` | 是 | 复位后时间基准 |
| `reset_count_cycle` | `BooleanField` | 是 | 是否复位产量周期 |
| `reset_time_cycle` | `BooleanField` | 是 | 是否复位时间周期 |
| `knowledge_snapshot_version` | `CharField(64)` | 是 | 知识版本 |
| `actual_work_hours` | `DecimalField(8,2,null=True)` | 否 | 实际工时 |
| `result` | `CharField(24)` | 是 | `NORMAL/ABNORMAL`，履历通常为 NORMAL |
| `note` | `TextField(null=True)` | 否 | 说明 |
| `request_key` | `CharField(200,unique=True)` | 是 | 防重复复位 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |

---

## 7. 不建立的模型

```text
User / Role / Permission
MaintenanceRule（规则使用代码常量）
MaintenanceCycle（基线直接存在 Mold）
InspectionItem（使用 JSON）
KnowledgeSnapshot（使用 JSON）
NotificationRecord（字段合并到 WorkOrder）
RepairReferral（使用同一个 WorkOrder 模型建立 REPAIR_TASK）
HistoryImport
AuditLog
```
