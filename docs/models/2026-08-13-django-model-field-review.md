# MoldGuard Django 模型字段清单

- **状态**：`FIELD_SCOPE_FROZEN_V5_1`
- **版本**：V3.1
- **日期**：2026-08-13
- **适用计划**：V5.0 + V5.1
- **知识库基线**：`MOLDGUARD-KB-1.2`
- **报工契约**：`REPORT-FORM-1.1`

当前建立：

```text
6个业务模型
+ 1个幂等基础设施模型
```

业务模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

基础设施模型：

```text
ClientRequestRecord
```

复杂点检、知识包、邮件结果和异常内容使用 JSON 字段保存。

---

## 1. Mold

| 字段 | Django 类型 | 必填 | 说明 |
|---|---|---:|---|
| `mold_id` | `CharField(64, primary_key=True)` | 是 | 模具编号 |
| `mold_name` | `CharField(200)` | 是 | 模具名称 |
| `mold_type` | `CharField(32, choices)` | 是 | `INJECTION` / `SHEET_METAL` |
| `effective_mold_cycles` | `PositiveBigIntegerField` | 是 | 当前累计有效模次；服务器不做型腔换算 |
| `baseline_effective_mold_cycles` | `PositiveBigIntegerField` | 是 | 当前周期基准模次 |
| `baseline_maintenance_at` | `DateTimeField` | 是 | 当前周期基准时间 |
| `cycle_version` | `PositiveIntegerField(default=1)` | 是 | 每次正式周期复位递增 |
| `first_production_at` | `DateTimeField(null=True, blank=True)` | 否 | 注塑首次2个月起算点 |
| `development_tonnage` | `DecimalField(10,2,null=True,blank=True)` | 否 | 注塑30K/50K规则 |
| `mold_category` | `CharField(40,null=True,blank=True)` | 否 | `FORMING/PUNCH_BLANKING/CONTINUOUS/SIDE_PANEL` |
| `mold_type_code` | `CharField(32,null=True,blank=True)` | 否 | `LC101`—`LC109` |
| `level_1_location` | `CharField(120,blank=True,default='')` | 否 | 一级位置，仅定位 |
| `level_2_location` | `CharField(120,blank=True,default='')` | 否 | 二级位置，仅定位 |
| `production_line` | `CharField(120,blank=True,default='')` | 否 | 候选人员同产线排序 |
| `output_updated_at` | `DateTimeField(null=True,blank=True)` | 否 | 连续2年未更新产量判断 |
| `status` | `CharField(32,choices)` | 是 | `ACTIVE/INACTIVE/UNDER_REPAIR/DISABLED` |
| `knowledge_profile_code` | `CharField(100,blank=True,default='')` | 否 | 平台知识精确过滤编码 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 更新时间 |

数据库约束：

```text
effective_mold_cycles >= 0
baseline_effective_mold_cycles >= 0
baseline_effective_mold_cycles <= effective_mold_cycles
cycle_version >= 1
```

业务校验：

```text
INJECTION自动扫描必须有development_tonnage
SHEET_METAL自动扫描必须有mold_category
LC109只允许CONTINUOUS或SIDE_PANEL
```

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
| `alert_id` | `CharField(64,primary_key=True)` | 是 | 提醒编号 |
| `mold` | `ForeignKey(Mold,PROTECT)` | 是 | 模具 |
| `primary_rule_id` | `CharField(100)` | 是 | 主规则ID |
| `matched_rule_ids_json` | `JSONField(default=list)` | 是 | 同时命中的全部规则 |
| `alert_type` | `CharField(40)` | 是 | `FORMAL_MAINTENANCE/MANUAL` |
| `cycle_version` | `PositiveIntegerField` | 是 | 触发时周期版本 |
| `cycle_mold_cycles_snapshot` | `PositiveBigIntegerField(null=True)` | 否 | 模次快照 |
| `threshold_count` | `PositiveBigIntegerField(null=True)` | 否 | 主规则阈值 |
| `trigger_reason` | `TextField` | 是 | 完整触发说明 |
| `status` | `CharField(24)` | 是 | `OPEN/CLOSED` |
| `dedupe_key` | `CharField(200,unique=True)` | 是 | 防重复扫描 |
| `triggered_at` | `DateTimeField` | 是 | 触发时间 |
| `closed_at` | `DateTimeField(null=True,blank=True)` | 否 | 关闭时间 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 更新时间 |

正式保养去重键：

```text
FORMAL_MAINTENANCE:{mold_id}:{cycle_version}
```

注塑模次和时间同时命中时只建立一条 Alert，`primary_rule_id` 使用模次规则，`matched_rule_ids_json` 同时保存两个规则。

---

## 3. Employee

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `employee_id` | `CharField(64,primary_key=True)` | 是 | 模拟员工编号 |
| `employee_name` | `CharField(120)` | 是 | 姓名 |
| `email` | `EmailField` | 是 | 测试收件邮箱 |
| `production_line` | `CharField(120,blank=True,default='')` | 否 | 同产线排序 |
| `skills_json` | `JSONField(default=list)` | 是 | `INJECTION/SHEET_METAL`技能列表 |
| `current_load` | `DecimalField(5,4)` | 是 | 0—1固定DEMO值 |
| `on_duty` | `BooleanField(default=True)` | 是 | 是否在岗 |
| `available` | `BooleanField(default=True)` | 是 | 是否可派工 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 是 | 更新时间 |

约束：

```text
0 <= current_load <= 1
```

一天版本不自动修改 `current_load`。

---

## 4. WorkOrder

### 4.1 主字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `work_order_id` | `CharField(64,primary_key=True)` | 是 | 工单编号 |
| `alert` | `ForeignKey(Alert,null=True,blank=True,PROTECT)` | 否 | 手动或修模子工单可为空 |
| `mold` | `ForeignKey(Mold,PROTECT)` | 是 | 模具 |
| `parent_work_order` | `ForeignKey('self',null=True,blank=True,PROTECT)` | 否 | 修模子工单的原工单 |
| `linked_repair_order` | `ForeignKey('self',null=True,blank=True,SET_NULL,related_name='+')` | 否 | 原工单关联的当前修模子单 |
| `primary_rule_id` | `CharField(100)` | 是 | 主触发规则 |
| `matched_rule_ids_json` | `JSONField(default=list)` | 是 | 同时命中的规则 |
| `work_order_type` | `CharField(48)` | 是 | 工单类型 |
| `status` | `CharField(40)` | 是 | 工单状态 |
| `assignee` | `ForeignKey(Employee,null=True,blank=True,PROTECT)` | 否 | 被派工人员 |
| `standard_hours` | `DecimalField(8,2,null=True,blank=True)` | 否 | 显式DEMO配置；不猜测 |
| `required_finish_at` | `DateTimeField(null=True,blank=True)` | 否 | 显式DEMO配置计算 |
| `create_key` | `CharField(200,unique=True)` | 是 | 防重复建单 |

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

状态：

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
ABNORMAL_REPORTED
REPAIR_LINKED
COMPLETED
CANCELLED
```

一天P0不提供通用cancel接口，但保留枚举便于后续扩展。

### 4.2 触发与周期快照

| 字段 | 类型 | 必填 |
|---|---|---:|
| `effective_mold_cycles_snapshot` | `PositiveBigIntegerField` | 是 |
| `baseline_effective_mold_cycles_before` | `PositiveBigIntegerField` | 是 |
| `baseline_maintenance_at_before` | `DateTimeField` | 是 |
| `cycle_mold_cycles_snapshot` | `PositiveBigIntegerField(null=True,blank=True)` | 否 |
| `threshold_count` | `PositiveBigIntegerField(null=True,blank=True)` | 否 |
| `trigger_reason` | `TextField` | 是 |
| `triggered_at` | `DateTimeField` | 是 |
| `reset_count_cycle` | `BooleanField(default=False)` | 是 |
| `reset_time_cycle` | `BooleanField(default=False)` | 是 |

### 4.3 知识与邮件

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `knowledge_snapshot_version` | `CharField(64,default='MOLDGUARD-KB-1.2')` | 是 | 知识版本 |
| `knowledge_package_json` | `JSONField(default=dict)` | 是 | 邮件和页面使用的唯一知识包 |
| `knowledge_package_hash` | `CharField(64,blank=True,default='')` | 否 | 规范化JSON SHA-256 |
| `knowledge_locked_at` | `DateTimeField(null=True,blank=True)` | 否 | 邮件发送成功后锁定 |
| `inspection_results_json` | `JSONField(default=list)` | 是 | 最终点检提交结果 |
| `email_recipient` | `EmailField(null=True,blank=True)` | 否 | 收件人 |
| `email_subject` | `CharField(240,blank=True,default='')` | 否 | 邮件主题 |
| `email_status` | `CharField(24,default='NOT_SENT')` | 是 | `NOT_SENT/SENT/FAILED` |
| `email_message_id` | `CharField(200,blank=True,default='')` | 否 | 平台消息ID |
| `email_sent_at` | `DateTimeField(null=True,blank=True)` | 否 | 发送时间 |
| `email_error` | `TextField(blank=True,default='')` | 否 | 失败信息 |

知识包在 `email_status=SENT` 或已报工后不可覆盖。

### 4.4 报工字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `report_method` | `CharField(24,default='WEB_FORM')` | 是 | 固定网页/JSON共用服务 |
| `report_form_schema_version` | `CharField(32,default='REPORT-FORM-1.1')` | 是 | 表单版本 |
| `report_type` | `CharField(24,null=True,blank=True)` | 否 | `NORMAL/ABNORMAL` |
| `report_summary` | `TextField(blank=True,default='')` | 否 | 完成或异常说明 |
| `abnormal_items_json` | `JSONField(default=list)` | 是 | 异常项 |
| `photos_json` | `JSONField(default=list)` | 是 | URL或文本引用，不收二进制 |
| `parts_replaced_json` | `JSONField(default=list)` | 是 | 更换件 |
| `source_fault_id` | `CharField(100,blank=True,default='')` | 否 | 故障源表ID |
| `fault_type` | `CharField(120,blank=True,default='')` | 否 | 故障类型 |
| `fault_description` | `TextField(blank=True,default='')` | 否 | 原始故障描述 |
| `standard_repair_hours` | `DecimalField(8,2,null=True,blank=True)` | 否 | 故障候选标准工时 |
| `actual_work_hours` | `DecimalField(8,2,null=True,blank=True)` | 否 | 正常/异常报工时填写 |
| `abnormal_next_action` | `CharField(40,blank=True,default='')` | 否 | `CONTINUE_PROCESSING/CREATE_REPAIR_TASK` |
| `repair_reason` | `TextField(blank=True,default='')` | 否 | 转修模原因 |

`report_url` 不落库：

```text
{MOLDGUARD_PUBLIC_BASE_URL}/report/{work_order_id}
```

客户端不提交员工编号，服务器使用 `assignee` 作为报工人。

### 4.5 时间字段

```text
assigned_at
started_at
pause_started_at
paused_seconds
reported_at
completed_at
created_at
updated_at
```

---

## 5. WorkOrderEvent

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `event_id` | `CharField(64,primary_key=True)` | 是 | 事件编号 |
| `work_order` | `ForeignKey(WorkOrder,CASCADE)` | 是 | 工单 |
| `event_type` | `CharField(80)` | 是 | 事件类型 |
| `from_status` | `CharField(40,blank=True,default='')` | 否 | 原状态 |
| `to_status` | `CharField(40,blank=True,default='')` | 否 | 新状态 |
| `operator_id` | `CharField(80,blank=True,default='')` | 否 | 展示字段，不做身份校验 |
| `remarks` | `TextField(blank=True,default='')` | 否 | 备注 |
| `event_data_json` | `JSONField(default=dict)` | 是 | 事件快照 |
| `request_key` | `CharField(200,null=True,blank=True,unique=True)` | 否 | 动作级去重辅助 |
| `occurred_at` | `DateTimeField` | 是 | 业务发生时间 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 入库时间 |

所有状态变化必须写事件。

---

## 6. MaintenanceRecord

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `record_id` | `CharField(64,primary_key=True)` | 是 | 履历编号 |
| `mold` | `ForeignKey(Mold,PROTECT)` | 是 | 模具 |
| `work_order` | `OneToOneField(WorkOrder,PROTECT)` | 是 | 来源工单 |
| `record_type` | `CharField(48)` | 是 | 与工单类型对应 |
| `occurred_at` | `DateTimeField` | 是 | 正常报工完成时间 |
| `effective_mold_cycles_snapshot` | `PositiveBigIntegerField` | 是 | 报工时模次 |
| `baseline_count_before` | `PositiveBigIntegerField` | 是 | 复位前基准 |
| `baseline_time_before` | `DateTimeField` | 是 | 复位前时间 |
| `baseline_count_after` | `PositiveBigIntegerField` | 是 | 复位后基准 |
| `baseline_time_after` | `DateTimeField` | 是 | 复位后时间 |
| `reset_count_cycle` | `BooleanField` | 是 | 是否复位模次 |
| `reset_time_cycle` | `BooleanField` | 是 | 是否复位时间 |
| `knowledge_snapshot_version` | `CharField(64)` | 是 | 知识版本 |
| `knowledge_package_hash` | `CharField(64)` | 是 | 知识内容哈希 |
| `standard_hours` | `DecimalField(8,2,null=True,blank=True)` | 否 | 标准工时 |
| `actual_work_hours` | `DecimalField(8,2,null=True,blank=True)` | 否 | 实际工时 |
| `result` | `CharField(24)` | 是 | 正常履历固定 `NORMAL` |
| `note` | `TextField(blank=True,default='')` | 否 | 说明 |
| `request_key` | `CharField(200,unique=True)` | 是 | 防重复履历和复位 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |

仅最终正常完成的工单创建履历。异常报工不创建最终履历。修模子工单可创建不复位的维修履历。

---

## 7. ClientRequestRecord

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `client_request_id` | `CharField(120,primary_key=True)` | 是 | 全局幂等ID |
| `action` | `CharField(80)` | 是 | 动作类型 |
| `object_id` | `CharField(80,blank=True,default='')` | 否 | 业务对象 |
| `request_hash` | `CharField(64)` | 是 | 规范化请求SHA-256 |
| `response_status` | `PositiveSmallIntegerField` | 是 | 首次成功HTTP状态 |
| `response_json` | `JSONField` | 是 | 首次成功响应 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 是 | 创建时间 |

HTML 表单的 `submission_id` 映射到 `client_request_id`。

---

## 8. 不建立的模型

```text
User / Role / Permission
MaintenanceRule
MaintenanceCycle
InspectionItem
KnowledgeSnapshot
NotificationRecord
RepairReferral
HistoryImport
AuditLog
PauseSegment
AnalyticsResult
```

暂停使用 `WorkOrder.pause_started_at + paused_seconds + WorkOrderEvent` 表示；知识、通知和点检使用 WorkOrder 字段。
