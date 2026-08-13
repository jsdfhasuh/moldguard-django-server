# MoldGuard Django 测试服务器模型字段审查表

- **状态**：`OWNER_FIELD_REVIEW_REQUIRED`
- **版本**：V1.0
- **日期**：2026-08-13
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.0
- **服务器定位**：无角色、无鉴权、仅使用 DEMO 数据的比赛测试服务器
- **目的**：把后续准备建立的全部 Django 模型与字段一次列清，供负责人判断“保留、可选、删除或延期”

---

## 1. 审查标记

| 标记 | 含义 |
|---|---|
| `P0保留` | 参赛主链路需要，建议本次实现 |
| `P1可选` | 有展示价值，但删除后不影响主链路 |
| `派生` | API需要返回，但不建议作为数据库字段重复保存 |
| `删除` | 当前测试服务器不建立 |
| `待决策` | 字段是否需要取决于尚未确认的负责人决策 |

字段设计遵循：

1. 不建立用户、角色、权限和登录模型；
2. 不为可计算数据重复建字段；
3. 保留足够的业务快照，避免修改模拟主数据后历史工单失真；
4. JSON 字段只用于测试服务器的技能、知识条目等轻量结构，不设计复杂生产级范式；
5. 所有业务主键对外使用字符串编号，内部主键使用 Django 默认 `BigAutoField`；
6. 分析接口直接查询现有业务表，不单独建立“统计结果表”。

---

## 2. 模型总览

建议 P0 建立 14 个持久化模型：

| 应用 | 模型 | 用途 | 结论 |
|---|---|---|---|
| `molds` | `Mold` | 模具基础资料和当前累计模次 | P0保留 |
| `molds` | `MaintenanceRule` | 两条开发吨位触发规则 | P0保留 |
| `molds` | `MaintenanceCycle` | 当前及历史保养周期基线 | P0保留 |
| `molds` | `CycleResetEvent` | 保养、修模、换镶件、历史记录复位记录 | P0保留 |
| `molds` | `Alert` | 模次到期和注塑2个月提醒 | P0保留 |
| `staff` | `Employee` | 模拟人员、技能、负荷和测试邮箱 | P0保留 |
| `workorders` | `WorkOrder` | 工单主表和当前状态 | P0保留 |
| `workorders` | `WorkOrderEvent` | 状态时间线和演示操作记录 | P0保留 |
| `workorders` | `InspectionItemResult` | 逐项点检快照和执行结果 | P0保留 |
| `workorders` | `KnowledgeSnapshot` | 本工单实际使用的知识条目快照 | P0保留 |
| `workorders` | `NotificationRecord` | 比赛平台邮件发送结果 | P0保留 |
| `workorders` | `RepairReferral` | 点检不合格转修模记录 | P0保留 |
| `workorders` | `MaintenanceRecord` | 保养、修模、换镶件、历史导入履历 | P0保留 |
| `common` | `IdempotencyRecord` | 防止平台重试导致重复写入 | P0保留 |

不单独建立：

```text
User
Role
Permission
Supervisor
APIClient
MaintenancePlan
DeliverySchedule
Skill
EmployeeSkill
AlertPolicy
RuleApprovalRecord
RuleConflict
KnowledgeCatalogRelease
FaultStandard
PauseSegment
AuditLog
AnalyticsResult
```

其中部分能力通过字段、JSON 或 `WorkOrderEvent` 合并实现。

---

# 3. Mold 模具台账

模型：`apps.molds.models.Mold`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | Django内部主键，不对平台展示 |
| `mold_id` | `CharField(64, unique=True)` | 否 | P0保留 | 模具业务编号 |
| `mold_name` | `CharField(200)` | 否 | P0保留 | 邮件、工单和预警展示 |
| `mold_type` | `CharField(32, choices)` | 否 | P0保留 | `INJECTION` / `SHEET_METAL`，决定是否计算2个月提醒和点检知识 |
| `development_tonnage` | `DecimalField(10,2)` | 否 | P0保留 | 当前正式30,000/50,000模次规则的唯一分组依据，单位T |
| `current_count` | `PositiveBigIntegerField` | 否 | P0保留 | 当前累计生产模次 |
| `primary_location` | `CharField(120)` | 是 | P0保留 | 原方案“模具一级位置”，用于邮件和展示 |
| `secondary_location` | `CharField(120)` | 是 | P0保留 | 原方案“模具二级位置” |
| `production_line` | `CharField(120)` | 是 | P0保留 | 候选人员同产线排序 |
| `status` | `CharField(32, choices)` | 否 | P0保留 | `IN_PRODUCTION` / `IN_STORAGE` / `UNDER_REPAIR` / `DISABLED` |
| `knowledge_profile_code` | `CharField(100)` | 是 | P0保留 | 平台知识库精确过滤编码，例如 `KB-INJECTION-PERIODIC-V1` |
| `knowledge_tags_json` | `JSONField(default=list)` | 否 | P1可选 | 额外知识检索标签；只用 profile code 时可删除 |
| `mold_level` | `CharField(32)` | 是 | P1可选 | 原方案展示字段；当前不参与自动触发 |
| `mold_category` | `CharField(100)` | 是 | P1可选 | 历史标准和知识过滤；当前不参与自动触发 |
| `cavity_count` | `PositiveIntegerField` | 是 | P1可选 | 原方案展示字段；当前规则不使用 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P0保留 | 更新时间 |

### 不建议在 Mold 重复保存

| 原字段或候选字段 | 处理方式 | 原因 |
|---|---|---|
| `last_maintenance_count` | 派生自当前 `MaintenanceCycle.baseline_count` | 周期也可能由修模、换镶件或历史记录复位，不一定是保养 |
| `last_maintenance_time` | 派生自当前 `MaintenanceCycle.baseline_time` | 避免双字段不同步 |
| `maintenance_threshold` | 派生自活动 `MaintenanceRule` | 阈值属于规则，不属于模具主数据 |
| `remaining_count` | 动态计算 | `threshold - cycle_count` |
| `overdue_count` | 动态计算 | `cycle_count - threshold` |
| `health_score` | 动态计算或不实现 | D09尚未确认，不建议落库 |
| `standard_hours` | 存在 `WorkOrder` | 工时属于本次任务，不属于模具固定属性 |

### Mold 字段待负责人审查

- `mold_level`、`mold_category`、`cavity_count` 是否为了原方案展示而保留？
- `knowledge_tags_json` 是否需要，还是只保留 `knowledge_profile_code`？

---

# 4. MaintenanceRule 自动触发规则

模型：`apps.molds.models.MaintenanceRule`

测试版只保存当前两条正式吨位规则，不建立复杂版本审批体系。

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `rule_id` | `CharField(100, unique=True)` | 否 | P0保留 | 如 `MAINT-TONNAGE-LT1000-V1` |
| `rule_name` | `CharField(200)` | 否 | P0保留 | 管理和接口展示 |
| `mold_type_scope` | `CharField(32)` | 否 | P0保留 | 当前固定 `BOTH`，保留便于解释适用范围 |
| `tonnage_min` | `DecimalField(10,2)` | 是 | P0保留 | 下限；小吨位规则为空，大吨位规则为1000 |
| `tonnage_max` | `DecimalField(10,2)` | 是 | P0保留 | 上限；小吨位规则为1000，大吨位规则为空 |
| `min_inclusive` | `BooleanField(default=True)` | 否 | P0保留 | 下限是否包含 |
| `max_inclusive` | `BooleanField(default=False)` | 否 | P0保留 | 确保1000T进入大吨位规则 |
| `count_threshold` | `PositiveBigIntegerField` | 否 | P0保留 | 50,000或30,000 |
| `authority` | `CharField(32)` | 否 | P0保留 | 固定 `INTERNAL_CONFIRMED` |
| `version` | `CharField(32)` | 否 | P0保留 | `V1.0` |
| `is_active` | `BooleanField(default=True)` | 否 | P0保留 | 仅活动规则参与扫描 |
| `notes` | `TextField` | 是 | P1可选 | 记录历史规则只作参考等说明 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P0保留 | 更新时间 |

### 建议删除的复杂字段

```text
maintenance_level
mold_category
mold_code_prefix
exact_mold_id
part_name
approval_status
approved_by
rule_priority
effective_from/effective_to
```

当前自动触发只有两条已确认规则，上述字段会增加开发量但不参与比赛主链路。

---

# 5. MaintenanceCycle 保养周期

模型：`apps.molds.models.MaintenanceCycle`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `cycle_id` | `CharField(64, unique=True)` | 否 | P0保留 | 周期业务编号 |
| `mold` | `ForeignKey(Mold)` | 否 | P0保留 | 所属模具 |
| `cycle_version` | `PositiveIntegerField` | 否 | P0保留 | 每次复位递增 |
| `baseline_count` | `PositiveBigIntegerField` | 否 | P0保留 | 当前周期起始模次 |
| `baseline_time` | `DateTimeField` | 否 | P0保留 | 当前周期起始时间 |
| `trigger_rule` | `ForeignKey(MaintenanceRule)` | 否 | P0保留 | 本周期采用的吨位规则 |
| `count_threshold_snapshot` | `PositiveBigIntegerField` | 否 | P0保留 | 周期建立时冻结30,000或50,000，避免后续规则修改改变历史 |
| `next_time_reminder_at` | `DateTimeField` | 是 | P0保留 | 注塑模具下一次2个月提醒；钣金为空 |
| `status` | `CharField(24, choices)` | 否 | P0保留 | `ACTIVE` / `CLOSED` / `SUPERSEDED` |
| `opened_at` | `DateTimeField` | 否 | P0保留 | 周期建立时间 |
| `closed_at` | `DateTimeField` | 是 | P0保留 | 复位后关闭旧周期 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P0保留 | 更新时间 |

### 建议派生而不落库

```text
cycle_count = mold.current_count - baseline_count
next_due_count = baseline_count + count_threshold_snapshot
remaining_count
overdue_count
usage_percent
```

每套模具只能存在一个 `ACTIVE` 周期。

---

# 6. CycleResetEvent 周期复位事件

模型：`apps.molds.models.CycleResetEvent`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `reset_event_id` | `CharField(64, unique=True)` | 否 | P0保留 | 对外事件编号 |
| `mold` | `ForeignKey(Mold)` | 否 | P0保留 | 复位模具 |
| `old_cycle` | `ForeignKey(MaintenanceCycle, related_name=...)` | 否 | P0保留 | 被关闭周期 |
| `new_cycle` | `ForeignKey(MaintenanceCycle, related_name=...)` | 否 | P0保留 | 新周期 |
| `reset_type` | `CharField(40, choices)` | 否 | P0保留 | `MAINTENANCE_COMPLETED` / `REPAIR_COMPLETED` / `INSERT_REPLACED` / `HISTORY_RECORD_IMPORTED` / `TEST_CORRECTION` |
| `source_object_type` | `CharField(60)` | 否 | P0保留 | 来源对象类型 |
| `source_object_id` | `CharField(100)` | 否 | P0保留 | 工单、转修模或历史记录编号 |
| `baseline_count_before` | `PositiveBigIntegerField` | 否 | P0保留 | 复位前模次基线 |
| `baseline_time_before` | `DateTimeField` | 否 | P0保留 | 复位前时间基线 |
| `baseline_count_after` | `PositiveBigIntegerField` | 否 | P0保留 | 复位后模次基线 |
| `baseline_time_after` | `DateTimeField` | 否 | P0保留 | 复位后时间基线 |
| `business_occurred_at` | `DateTimeField` | 否 | P0保留 | 真实业务发生时间；历史导入不使用上传时间 |
| `operator_id` | `CharField(64)` | 是 | P1可选 | 仅演示日志，不鉴权 |
| `operator_name` | `CharField(100)` | 是 | P1可选 | 仅演示日志 |
| `source_file` | `CharField(255)` | 是 | P1可选 | 历史记录导入来源 |
| `source_record_id` | `CharField(100)` | 是 | P1可选 | 外部记录唯一标识 |
| `remarks` | `TextField` | 是 | P1可选 | 复位说明 |
| `idempotency_key` | `CharField(200, unique=True)` | 是 | P0保留 | 防止重复复位 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 记录时间 |

历史记录早于当前基线时，只创建 `MaintenanceRecord`，不创建 `CycleResetEvent`。

---

# 7. Alert 提醒记录

模型：`apps.molds.models.Alert`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `alert_id` | `CharField(64, unique=True)` | 否 | P0保留 | 提醒业务编号 |
| `mold` | `ForeignKey(Mold)` | 否 | P0保留 | 对应模具 |
| `cycle` | `ForeignKey(MaintenanceCycle)` | 否 | P0保留 | 对应周期 |
| `alert_type` | `CharField(40, choices)` | 否 | P0保留 | `MAINTENANCE_DUE_COUNT` / `MAINTENANCE_TIME_REMINDER` |
| `rule` | `ForeignKey(MaintenanceRule)` | 是 | P0保留 | 时间提醒可为空，模次提醒必填 |
| `current_count_snapshot` | `PositiveBigIntegerField` | 否 | P0保留 | 扫描时当前模次 |
| `cycle_count_snapshot` | `PositiveBigIntegerField` | 否 | P0保留 | 扫描时周期模次 |
| `threshold_snapshot` | `PositiveBigIntegerField` | 是 | P0保留 | 模次提醒为30,000/50,000；时间提醒为空 |
| `usage_percent` | `DecimalField(7,2)` | 是 | P0保留 | 模次提醒展示比例 |
| `alert_level` | `CharField(20)` | 否 | P0保留 | 建议 `INFO` / `YELLOW` / `RED`；具体分级仍受D09影响 |
| `remind_at` | `DateTimeField` | 是 | P0保留 | 时间提醒到期时间 |
| `status` | `CharField(24, choices)` | 否 | P0保留 | `OPEN` / `ACKNOWLEDGED` / `CLOSED` / `SUPERSEDED` |
| `dedupe_key` | `CharField(200, unique=True)` | 否 | P0保留 | 防止重复扫描生成相同提醒 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `acknowledged_at` | `DateTimeField` | 是 | P1可选 | 是否需要展示确认时间 |
| `closed_at` | `DateTimeField` | 是 | P0保留 | 关闭时间 |

### 不建议保存

```text
recommended_action
current_status_text
estimated_downtime_text
suggested_team_text
```

这些自然语言内容由智能体平台根据 Django 事实和知识库生成。

---

# 8. Employee 模拟人员

模型：`apps.staff.models.Employee`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `employee_id` | `CharField(64, unique=True)` | 否 | P0保留 | 员工编号 |
| `employee_name` | `CharField(100)` | 否 | P0保留 | 姓名 |
| `email` | `EmailField` | 是 | P0保留 | 平台动态邮件收件人；为空则不能作为有效候选 |
| `team` | `CharField(120)` | 是 | P1可选 | 邮件和候选说明 |
| `production_line` | `CharField(120)` | 是 | P0保留 | 同产线排序 |
| `skills_json` | `JSONField(default=list)` | 否 | P0保留 | 技能代码或名称数组，测试版不建立Skill关联表 |
| `technician_level` | `CharField(32)` | 是 | P1可选 | `JUNIOR` / `INTERMEDIATE` / `SENIOR` / `EXPERT`，用于高级技师排序 |
| `current_load` | `DecimalField(5,4)` | 否 | P0保留 | 0—1；低于0.80才满足候选条件 |
| `on_duty` | `BooleanField(default=True)` | 否 | P0保留 | 是否在岗 |
| `available` | `BooleanField(default=True)` | 否 | P0保留 | 是否可派工 |
| `is_active` | `BooleanField(default=True)` | 否 | P0保留 | 是否保留在人员池 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P1可选 | 调试用途 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P1可选 | 调试用途 |

### 不建立

```text
username
password
role
permissions
last_login
```

---

# 9. WorkOrder 工单主表

模型：`apps.workorders.models.WorkOrder`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `work_order_id` | `CharField(64, unique=True)` | 否 | P0保留 | 工单编号 |
| `alert` | `ForeignKey(Alert)` | 否 | P0保留 | P0工单必须来源于模次到期提醒 |
| `mold` | `ForeignKey(Mold)` | 否 | P0保留 | 便于查询；必须与alert.mold一致 |
| `status` | `CharField(40, choices)` | 否 | P0保留 | 工单状态机 |
| `priority` | `CharField(20)` | 否 | P0保留 | `LOW` / `MEDIUM` / `HIGH` / `URGENT`；D10未确认时可固定演示值 |
| `standard_hours` | `DecimalField(7,2)` | 否 | P0保留 | 预计停机时长和工时偏差基础 |
| `required_finish_at` | `DateTimeField` | 是 | P0保留 | 邮件截止时间和超时统计 |
| `required_skills_json` | `JSONField(default=list)` | 否 | P0保留 | 候选人员匹配依据；创建工单时由测试数据或平台传入 |
| `knowledge_profile_code` | `CharField(100)` | 是 | P0保留 | 知识库过滤编码，通常复制自Mold |
| `assigned_employee` | `ForeignKey(Employee, null=True)` | 是 | P0保留 | 最终被选人员 |
| `assigned_at` | `DateTimeField` | 是 | P0保留 | 派工时间 |
| `started_at` | `DateTimeField` | 是 | P0保留 | 开工时间 |
| `pause_started_at` | `DateTimeField` | 是 | P0保留 | 当前暂停起点；恢复后清空 |
| `reported_at` | `DateTimeField` | 是 | P0保留 | 报完工时间 |
| `accepted_at` | `DateTimeField` | 是 | P0保留 | 验收通过时间 |
| `cancelled_at` | `DateTimeField` | 是 | P1可选 | 取消时间 |
| `paused_seconds` | `PositiveBigIntegerField(default=0)` | 否 | P0保留 | 累计暂停秒数，不另建PauseSegment模型 |
| `completion_summary` | `TextField` | 是 | P0保留 | 报完工说明 |
| `acceptance_result` | `CharField(24)` | 是 | P1可选 | 可由最终状态和事件派生；需要报表展示时保留 |
| `trigger_rule_id_snapshot` | `CharField(100)` | 否 | P0保留 | 创建时冻结规则ID |
| `threshold_snapshot` | `PositiveBigIntegerField` | 否 | P0保留 | 创建时冻结阈值 |
| `cycle_count_snapshot` | `PositiveBigIntegerField` | 否 | P0保留 | 创建时冻结周期模次 |
| `development_tonnage_snapshot` | `DecimalField(10,2)` | 否 | P0保留 | 创建时冻结开发吨位 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P0保留 | 更新时间 |

### 建议派生

```text
dispatch_to_report_duration = reported_at - assigned_at
waiting_to_start_duration = started_at - assigned_at
actual_execution_duration = reported_at - started_at - paused_seconds
hours_variance = actual_execution_duration - standard_hours
```

不需要单独存 `assigned_name` 和 `assigned_email`，通过 `assigned_employee` 获取。

---

# 10. WorkOrderEvent 工单时间线

模型：`apps.workorders.models.WorkOrderEvent`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `work_order` | `ForeignKey(WorkOrder)` | 否 | P0保留 | 所属工单 |
| `event_type` | `CharField(50)` | 否 | P0保留 | `CREATED` / `ASSIGNED` / `STARTED` / `PAUSED` / `RESUMED` / `REPORTED` / `ACCEPTED` 等 |
| `from_status` | `CharField(40)` | 是 | P0保留 | 变化前状态 |
| `to_status` | `CharField(40)` | 是 | P0保留 | 变化后状态 |
| `operator_id` | `CharField(64)` | 是 | P1可选 | 展示用，不鉴权 |
| `operator_name` | `CharField(100)` | 是 | P1可选 | 展示用 |
| `remarks` | `TextField` | 是 | P0保留 | 暂停原因、退回原因、异常说明 |
| `payload_json` | `JSONField(default=dict)` | 否 | P1可选 | 保存额外演示信息；不需要时删除 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 事件时间 |

该模型是测试服务器唯一的通用操作时间线，不另建生产级 `AuditLog`。

---

# 11. InspectionItemResult 点检项与结果

模型：`apps.workorders.models.InspectionItemResult`

点检模板和结果合并为一个模型，减少表数量。

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `work_order` | `ForeignKey(WorkOrder)` | 否 | P0保留 | 所属工单 |
| `sequence` | `PositiveIntegerField` | 否 | P0保留 | 邮件和页面排序 |
| `knowledge_id` | `CharField(100)` | 是 | P0保留 | 知识库条目标识 |
| `item_name` | `CharField(255)` | 否 | P0保留 | 点检项目 |
| `acceptance_criteria` | `TextField` | 否 | P0保留 | 合格判定标准 |
| `inspection_method` | `TextField` | 是 | P1可选 | 操作方法；邮件需要时保留 |
| `is_critical` | `BooleanField(default=False)` | 否 | P0保留 | 关键项FAIL可直接转修模 |
| `result` | `CharField(24, choices, default=PENDING)` | 否 | P0保留 | `PENDING` / `PASS` / `FAIL` / `NOT_APPLICABLE` |
| `abnormal_note` | `TextField` | 是 | P0保留 | FAIL必填 |
| `not_applicable_reason` | `TextField` | 是 | P0保留 | NOT_APPLICABLE必填 |
| `performed_by` | `CharField(100)` | 是 | P1可选 | 无登录，仅展示填写人 |
| `performed_at` | `DateTimeField` | 是 | P0保留 | 点检时间 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 模板快照创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 否 | P0保留 | 结果更新时间 |
| `photo_refs_json` | `JSONField(default=list)` | 否 | P1可选 | 当前不做文件上传时可删除 |

唯一约束建议：`work_order + sequence`。

---

# 12. KnowledgeSnapshot 知识快照

模型：`apps.workorders.models.KnowledgeSnapshot`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `snapshot_id` | `CharField(64, unique=True)` | 否 | P0保留 | 对外快照编号 |
| `work_order` | `ForeignKey(WorkOrder)` | 否 | P0保留 | 所属工单 |
| `catalog_version` | `CharField(64)` | 否 | P0保留 | 如 `kb-v0.1` |
| `version_no` | `PositiveIntegerField(default=1)` | 否 | P0保留 | 同一工单允许重新检索生成新快照 |
| `knowledge_items_json` | `JSONField(default=list)` | 否 | P0保留 | 实际使用知识条目及来源，不保存向量库全文 |
| `content_hash` | `CharField(64)` | 否 | P0保留 | 快照内容SHA-256 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |

每个知识条目建议包含：

```text
knowledge_id
title
knowledge_type
source_file
source_location
authority
approval_status
content_hash
```

不单独建立 `KnowledgeCatalogRelease`，目录版本直接记录在快照中。

---

# 13. NotificationRecord 邮件结果

模型：`apps.workorders.models.NotificationRecord`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `notification_id` | `CharField(64, unique=True)` | 否 | P0保留 | 记录编号 |
| `work_order` | `ForeignKey(WorkOrder)` | 否 | P0保留 | 所属工单 |
| `knowledge_snapshot` | `ForeignKey(KnowledgeSnapshot)` | 是 | P0保留 | 本次邮件使用的知识版本 |
| `attempt_no` | `PositiveIntegerField(default=1)` | 否 | P0保留 | 区分失败和重试 |
| `recipient_email` | `EmailField` | 否 | P0保留 | 收件人 |
| `cc_emails_json` | `JSONField(default=list)` | 否 | P1可选 | D17确认需要抄送时保留 |
| `subject` | `CharField(255)` | 是 | P1可选 | 演示发送记录时有价值 |
| `platform_message_id` | `CharField(255)` | 是 | P0保留 | 比赛平台返回的消息ID |
| `status` | `CharField(24, choices)` | 否 | P0保留 | `PENDING` / `SENT` / `FAILED` / `DELIVERED` |
| `sent_at` | `DateTimeField` | 是 | P0保留 | 发送时间 |
| `error_message` | `TextField` | 是 | P0保留 | 失败原因 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 回写时间 |

不保存邮件正文和附件，正文由比赛平台负责。

---

# 14. RepairReferral 转修模记录

模型：`apps.workorders.models.RepairReferral`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `referral_id` | `CharField(64, unique=True)` | 否 | P0保留 | 转修模编号 |
| `work_order` | `OneToOneField(WorkOrder)` | 否 | P0保留 | 来源工单 |
| `reason` | `TextField` | 否 | P0保留 | 点检失败或验收不合格原因 |
| `fault_summary` | `TextField` | 是 | P1可选 | 故障简述 |
| `status` | `CharField(24, choices)` | 否 | P0保留 | `OPEN` / `COMPLETED` / `CANCELLED` |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `completed_at` | `DateTimeField` | 是 | P0保留 | 修模完成时间，完成后可复位周期 |
| `completed_count` | `PositiveBigIntegerField` | 是 | P0保留 | 修模完成时累计模次 |
| `completion_note` | `TextField` | 是 | P1可选 | 修模完成说明 |

P0只保存分流和完成结果，不实现完整维修工单、备件和维修步骤。

---

# 15. MaintenanceRecord 模具业务履历

模型：`apps.workorders.models.MaintenanceRecord`

该模型统一保存保养、修模、换镶件和历史导入记录，避免建立四张相似表。

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `record_id` | `CharField(64, unique=True)` | 否 | P0保留 | 履历编号 |
| `mold` | `ForeignKey(Mold)` | 否 | P0保留 | 所属模具 |
| `work_order` | `ForeignKey(WorkOrder, null=True)` | 是 | P0保留 | 保养工单生成的履历关联工单 |
| `repair_referral` | `ForeignKey(RepairReferral, null=True)` | 是 | P1可选 | 修模完成记录关联转修模 |
| `record_type` | `CharField(40, choices)` | 否 | P0保留 | `MAINTENANCE` / `REPAIR` / `INSERT_REPLACEMENT` / `HISTORY_IMPORT` |
| `occurred_at` | `DateTimeField` | 否 | P0保留 | 实际业务发生时间 |
| `occurred_count` | `PositiveBigIntegerField` | 否 | P0保留 | 发生时累计模次 |
| `actual_hours` | `DecimalField(7,2)` | 是 | P0保留 | 有工时时保存 |
| `result` | `CharField(24)` | 否 | P0保留 | `PASSED` / `FAILED` / `RECORDED` |
| `summary` | `TextField` | 是 | P0保留 | 记录说明 |
| `source_file` | `CharField(255)` | 是 | P1可选 | 历史导入来源文件 |
| `source_record_id` | `CharField(100)` | 是 | P1可选 | 防止外部记录重复导入 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 入库时间 |

是否发生周期复位，由关联的 `CycleResetEvent` 判断，不在本模型重复保存 `is_reset`。

---

# 16. IdempotencyRecord 幂等记录

模型：`apps.common.models.IdempotencyRecord`

| 字段 | Django类型建议 | 是否为空 | 级别 | 用途与说明 |
|---|---|---:|---|---|
| `id` | `BigAutoField` | 否 | P0保留 | 内部主键 |
| `key` | `CharField(200, unique=True)` | 否 | P0保留 | 平台同一次动作重试使用相同键 |
| `method` | `CharField(10)` | 否 | P0保留 | POST等 |
| `path` | `CharField(255)` | 否 | P0保留 | 接口路径 |
| `request_hash` | `CharField(64)` | 否 | P0保留 | 防止相同key对应不同请求内容 |
| `response_status` | `PositiveIntegerField` | 否 | P0保留 | 首次响应HTTP状态 |
| `response_body_json` | `JSONField` | 否 | P0保留 | 重试时返回原结果 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 否 | P0保留 | 创建时间 |
| `expires_at` | `DateTimeField` | 是 | P1可选 | 测试数据少，可暂不清理 |

该模型不包含用户、API Key 或权限信息。

---

# 17. 不建立数据库模型的内容

## 17.1 API派生字段

以下字段通过服务层计算后返回，不落库：

```text
cycle_count
remaining_count
overdue_count
usage_percent
next_due_count
health_score（若D09选择保留）
current_status_text
recommended_action
estimated_downtime_text
suggested_team
actual_execution_hours
hours_variance
completion_rate
overdue_order_count
```

## 17.2 明确删除的模型

| 旧模型/设计 | 当前处理 |
|---|---|
| `User / Role / Permission` | 删除，无登录和鉴权 |
| `MaintenancePlan` | 删除，提醒后直接创建工单 |
| `MoldDeliverySchedule` | 删除，不展示计划部和送模流程 |
| `Skill / EmployeeSkill` | 删除，合并为 `Employee.skills_json` |
| `AlertPolicy` | 删除，分级算法放代码配置；D09未确认 |
| `RuleApprovalRecord / RuleConflict` | 删除，测试版只装载两条已确认规则 |
| `KnowledgeCatalogRelease` | 删除，版本存在 `KnowledgeSnapshot.catalog_version` |
| `FaultStandard` | P1；当前由知识库提供异常参考 |
| `PauseSegment` | 删除，使用 `pause_started_at + paused_seconds + WorkOrderEvent` |
| `AuditLog` | 删除，使用 `WorkOrderEvent` 和 `CycleResetEvent` |
| `AnalyticsResult` | 删除，实时聚合现有数据 |
| `NotificationTemplate` | 删除，邮件由平台生成 |

---

# 18. 模型关系

```text
Mold
├─ MaintenanceCycle
│  ├─ Alert
│  └─ CycleResetEvent
├─ MaintenanceRecord
└─ WorkOrder
   ├─ Alert
   ├─ Employee（assigned_employee）
   ├─ WorkOrderEvent
   ├─ InspectionItemResult
   ├─ KnowledgeSnapshot
   │  └─ NotificationRecord
   ├─ RepairReferral
   └─ MaintenanceRecord

MaintenanceRule
├─ MaintenanceCycle
└─ Alert

IdempotencyRecord
└─ 独立记录所有写接口的重试结果
```

---

# 19. 建议的最小字段删除方案

若还要进一步压缩开发量，可以删除以下 P1 字段，而不影响主链路：

```text
Mold.knowledge_tags_json
Mold.mold_level
Mold.mold_category
Mold.cavity_count
MaintenanceRule.notes
CycleResetEvent.operator_id
CycleResetEvent.operator_name
CycleResetEvent.source_file
CycleResetEvent.source_record_id
CycleResetEvent.remarks
Alert.acknowledged_at
Employee.team
Employee.technician_level
Employee.created_at
Employee.updated_at
WorkOrder.cancelled_at
WorkOrder.acceptance_result
WorkOrderEvent.operator_id
WorkOrderEvent.operator_name
WorkOrderEvent.payload_json
InspectionItemResult.inspection_method
InspectionItemResult.performed_by
InspectionItemResult.photo_refs_json
NotificationRecord.cc_emails_json
NotificationRecord.subject
RepairReferral.fault_summary
RepairReferral.completion_note
MaintenanceRecord.repair_referral
MaintenanceRecord.source_file
MaintenanceRecord.source_record_id
IdempotencyRecord.expires_at
```

不建议删除的关键字段：

```text
development_tonnage
current_count
MaintenanceCycle.baseline_count
MaintenanceCycle.baseline_time
MaintenanceCycle.count_threshold_snapshot
Alert.dedupe_key
Employee.skills_json
Employee.current_load
Employee.email
WorkOrder.required_skills_json
WorkOrder.standard_hours
WorkOrder.required_finish_at
WorkOrder.paused_seconds
WorkOrder触发快照字段
InspectionItemResult.result
KnowledgeSnapshot.content_hash
NotificationRecord.status
CycleResetEvent前后基线
IdempotencyRecord.key
```

---

# 20. 负责人字段决策清单

请重点确认下列项目：

- [ ] F01｜`mold_level`、`mold_category`、`cavity_count` 是否为了原方案展示保留？
- [ ] F02｜知识检索只用 `knowledge_profile_code`，还是同时保留 `knowledge_tags_json`？
- [ ] F03｜是否保留 `Employee.team` 和 `technician_level` 用于候选解释与排序？
- [ ] F04｜工单是否必须保存 `priority` 和 `required_finish_at`？建议保留，用于邮件和超时统计。
- [ ] F05｜是否允许一个工单生成多个知识快照版本？建议允许，并保留 `version_no`。
- [ ] F06｜邮件记录是否需要 `cc_emails_json` 和 `subject`？取决于D17邮件规则。
- [ ] F07｜点检是否需要照片引用？比赛版可删除 `photo_refs_json`。
- [ ] F08｜转修模完成是否在P0演示？如不演示，可删除 `completed_count` 和 `completion_note`。
- [ ] F09｜历史记录导入是否需要保留来源文件和来源记录编号？建议保留，便于防重复。
- [ ] F10｜D09若不保留健康评分，数据库无需任何健康评分字段，只返回周期使用率。

推荐最简选择：

```text
F01=保留，但允许为空
F02=profile_code为主，tags_json保留为可选
F03=保留team和technician_level
F04=保留
F05=允许多个版本
F06=保留subject，cc_emails_json待D17
F07=删除
F08=保留completed_count，completion_note可选
F09=保留
F10=不落库
```

---

# 21. 审查结论

按本文件建议，测试服务器保持：

```text
14个模型
无账号与角色模型
无保养计划和送模模型
无复杂规则审批模型
无生产级审计模型
```

字段设计足以支撑：

```text
吨位模次提醒
注塑2个月提醒
工单创建
候选人员与派工
知识随单和邮件回写
开工/暂停/点检/报完工
验收或转修模
四类周期复位
工时和完成率统计
```

负责人确认 F01—F10 后，可将本文件状态改为 `FIELD_SCOPE_FROZEN`，并据此开始编写 Django models 和迁移。