# MoldGuard Django V3.3 每2个月提醒与周期复位修订

- **修订状态**：`NORMATIVE_AMENDMENT`
- **版本**：V3.3
- **日期**：2026-08-13
- **适用基线**：
  - V3.1完整业务服务器实施计划
  - V3.2吨位触发规则修订
- **权威确认**：`docs/decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md`
- **决策状态**：D03、D08均为 `INTERNAL_CONFIRMED`

---

## 1. 修订摘要

本修订冻结两项业务规则：

1. 注塑模具每2个月提醒继续保留，但只生成提醒，不自动生成保养计划、工单或派工；
2. 保养完成、修模完成、换镶件完成和有效历史记录导入均可复位保养周期。

V3.3与V3.2共同构成当前规则实施基线。

---

## 2. 触发体系调整

### 2.1 自动保养触发

自动保养触发仍仅依据当前已确认吨位规则：

```text
开发吨位 <1000T：周期模次达到50,000
开发吨位 >=1000T：周期模次达到30,000
```

该触发可以：

```text
生成保养预警
→ 生成待确认保养计划
→ 进入后续工单流程
```

### 2.2 时间提醒

注塑模具保留每2个月提醒：

```text
cycle_baseline_time + 2 calendar months
```

时间提醒只能：

```text
保存提醒记录
→ 由智能体平台生成并发送提醒
→ 用户确认或关闭提醒
```

时间提醒不能：

```text
自动创建MaintenancePlan
自动创建WorkOrder
自动派工
触发排产锁定
覆盖吨位模次触发结果
```

### 2.3 提醒类型分离

`MoldAlert.alert_type`至少支持：

```text
MAINTENANCE_DUE_COUNT
MAINTENANCE_TIME_REMINDER
LIFE_REMINDER
IDLE_REVIEW
DAILY_INSPECTION
MANUAL_FINDING
```

`MAINTENANCE_TIME_REMINDER`固定：

```text
business_action = REMIND_ONLY
```

---

## 3. 周期基线模型调整

原计划中以“上次保养模次/时间”作为单一基线的表达不再足够。

`Mold`或独立周期模型必须保存：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type
last_reset_event_id
last_reset_confirmed_by
last_reset_confirmed_at
next_count_threshold
next_time_reminder_at
```

建议新增：

```text
MaintenanceCycle
CycleResetEvent
```

### 3.1 MaintenanceCycle

```text
cycle_id
mold
cycle_version
baseline_count
baseline_time
trigger_rule_id
count_threshold
next_due_count
next_time_reminder_at
status
opened_at
closed_at
created_at
updated_at
```

状态：

```text
ACTIVE
SUPERSEDED
CLOSED
```

### 3.2 CycleResetEvent

保存复位来源、复位前后基线、操作人、幂等键和审计信息。

复位类型：

```text
MAINTENANCE_COMPLETED
REPAIR_COMPLETED
INSERT_REPLACED
HISTORY_RECORD_IMPORTED
ADMIN_CORRECTION
```

---

## 4. 四类复位行为

### 4.1 保养完成复位

触发点：保养工单验收通过且生成 `MaintenanceRecord`。

同一数据库事务中：

1. 工单设为 `COMPLETED`；
2. 创建保养履历；
3. 创建 `CycleResetEvent(MAINTENANCE_COMPLETED)`；
4. 关闭旧 `MaintenanceCycle`；
5. 创建新周期；
6. 重算下一模次阈值；
7. 重算下一次2个月提醒；
8. 将旧周期未处理时间提醒设为 `SUPERSEDED_BY_RESET`。

### 4.2 修模完成复位

触发点：`RepairReferral`或修模记录完成，并经有权限人员确认。

不得在“创建转修模记录”时立即复位，只有修模完成确认后生效。

### 4.3 换镶件完成复位

新增或复用事件模型：

```text
InsertReplacementEvent
```

只有事件状态为 `COMPLETED_CONFIRMED` 时复位。

建议接口：

```http
POST /api/v1/molds/{mold_id}/insert-replacements
POST /api/v1/molds/{mold_id}/insert-replacements/{event_id}/confirm-complete
```

### 4.4 上传历史记录复位

历史记录导入必须经过：

```text
文件/记录解析
→ 字段校验
→ 模具归属校验
→ 时间与模次校验
→ 权限确认
→ 入库
→ 复位
```

建议模型：

```text
MaintenanceHistoryImportBatch
MaintenanceHistoryImportRow
```

建议接口：

```http
POST /api/v1/maintenance-history/imports
GET  /api/v1/maintenance-history/imports/{batch_id}
POST /api/v1/maintenance-history/imports/{batch_id}/confirm
```

历史记录使用业务发生时间和发生模次复位，不使用上传时间。

旧于当前基线的记录默认只归档、不倒退周期；管理员显式执行 `ADMIN_CORRECTION` 才允许修正。

---

## 5. API修订

### 5.1 时间提醒

现有扫描接口继续使用：

```http
POST /api/v1/alerts/scan
```

响应分组：

```json
{
  "maintenance_due": [],
  "time_reminders": [],
  "life_reminders": [],
  "idle_reviews": []
}
```

新增查询过滤：

```http
GET /api/v1/alerts?alert_type=MAINTENANCE_TIME_REMINDER
```

时间提醒确认/关闭：

```http
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/alerts/{alert_id}/close
```

禁止对时间提醒执行：

```http
POST /api/v1/maintenance-plans
```

除非由主管主动发起手动计划，并明确 `source_type=MANUAL`，不得把时间提醒当作自动计划来源。

### 5.2 周期与复位查询

```http
GET /api/v1/molds/{mold_id}/maintenance-cycle
GET /api/v1/molds/{mold_id}/cycle-reset-events
```

必要时提供显式修正：

```http
POST /api/v1/molds/{mold_id}/cycle-reset-corrections
```

该接口只允许 `ADMIN` 或 `MOLD_SUPERVISOR`，必须填写原因和证据。

---

## 6. 智能体平台流程修订

### 6.1 每2个月提醒流程

```text
平台定时调用 /alerts/scan
→ Django返回MAINTENANCE_TIME_REMINDER
→ 平台生成“仅提醒”内容
→ 发送提醒邮件/消息
→ 回写通知结果
→ 不调用自动计划或自动建单接口
```

提醒文案必须包含：

```text
本提醒基于距当前周期基线已满2个月。
该提醒仅用于人工关注，不表示模次触发条件已达到。
是否创建手动保养计划由模具管理人员决定。
```

### 6.2 周期复位流程

平台发生以下成功动作后，以Django结果为准：

```text
保养验收通过
修模完成确认
换镶件完成确认
历史记录导入确认
```

Django返回：

```text
reset_event_id
old_cycle_version
new_cycle_version
baseline_count
baseline_time
next_due_count
next_time_reminder_at
```

平台不得只修改流程变量来模拟复位。

---

## 7. 数据与状态约束

1. 周期模次：

```text
cycle_count = current_count - cycle_baseline_count
```

2. 下一模次到期点：

```text
next_due_count = cycle_baseline_count + threshold
```

3. 下一时间提醒：

```text
next_time_reminder_at = cycle_baseline_time + 2 calendar months
```

4. 同一业务事件只能生成一次有效复位；
5. 复位后旧周期提醒和待评估记录必须标记为已被新周期替代；
6. 已创建并执行中的工单不得因复位自动删除，需进入人工冲突处理；
7. 历史记录导入不得静默回退当前基线；
8. 所有复位都必须记录规则版本、业务来源和操作人。

---

## 8. 错误码补充

```text
TIME_REMINDER_NOT_PLAN_SOURCE
TIME_REMINDER_SCOPE_NOT_ENABLED
RESET_SOURCE_NOT_CONFIRMED
RESET_EVENT_DUPLICATE
RESET_BASELINE_DATA_INCOMPLETE
RESET_BASELINE_REGRESSION_BLOCKED
RESET_CONFLICT_WITH_OPEN_WORK_ORDER
HISTORY_IMPORT_VALIDATION_FAILED
HISTORY_RECORD_MOLD_MISMATCH
```

---

## 9. 测试补充

### 时间提醒

- 注塑模具满2个自然月创建一次提醒；
- 未满2个月不提醒；
- 重复扫描幂等；
- 月末日期处理稳定；
- 时间提醒不生成计划、工单或派工；
- 时间提醒可以确认和关闭；
- 钣金模具未启用时不产生相同提醒；
- 周期复位后下一提醒时间重新计算。

### 周期复位

- 保养验收通过复位；
- 修模完成确认复位；
- 换镶件完成确认复位；
- 历史记录校验确认后复位；
- 重复事件不重复复位；
- 旧历史记录不倒退基线；
- 缺少模次/时间拒绝复位；
- 复位前后周期版本递增；
- 复位后3万/5万阈值正确重算；
- 复位后旧时间提醒失效；
- 开放工单冲突可审计；
- API、审计和履历一致。

---

## 10. 实施优先级

V3.3调整后，Phase顺序保持不变，但以下内容必须进入P0：

```text
MaintenanceCycle
CycleResetEvent
MAINTENANCE_TIME_REMINDER
四类复位事件
历史记录导入确认
时间提醒仅提醒约束
复位幂等与审计
```

历史批量导入的复杂映射UI可放P1，但P0至少要支持结构化JSON/CSV模拟导入和确认。

---

## 11. 冻结结论

```text
D03 = INTERNAL_CONFIRMED
注塑模具每2个月提醒继续保留，提醒仅通知，不自动生成计划、工单或派工。

D08 = INTERNAL_CONFIRMED
保养完成、修模完成、换镶件完成、有效历史记录导入均复位周期。
```

本修订与V3.1、V3.2共同构成当前开发基线；发生冲突时，以最新确认记录和V3.3为准。