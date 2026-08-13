# MoldGuard 每2个月提醒与保养周期复位规则确认

- **确认状态**：`INTERNAL_CONFIRMED`
- **版本**：V1.1
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server V4.0
- **关联决策**：D03、D08
- **服务器边界**：无主管角色、无登录、无API鉴权，仅使用DEMO数据

---

## 1. 每2个月提醒

### 1.1 确认结论

当前按原业务语境适用于注塑模具：

```text
cycle.baseline_time + 2 calendar months
→ 生成时间提醒
→ 智能体平台发送提醒
→ 不自动创建工单
→ 不自动派工
```

钣金模具不自动生成2个月提醒，除非后续另行确认。

### 1.2 Django行为

```text
alert_type = MAINTENANCE_TIME_REMINDER
alert_level = INFO
business_action = REMIND_ONLY
```

约束：

1. 同一模具、同一周期、同一到期日只生成一条提醒；
2. 时间提醒不能作为 `POST /work-orders` 的自动来源；
3. 提醒可以确认或关闭；
4. 周期复位后，旧提醒设为 `SUPERSEDED`；
5. 下一提醒从新周期基线重新计算；
6. 采用自然月计算，不固定换算为60天。

### 1.3 提醒文案要求

平台生成内容时必须说明：

> 本提醒仅表示距当前周期基线已满2个月，不代表模次保养条件已达到。

---

## 2. 允许复位周期的事件

以下事件均允许复位：

```text
MAINTENANCE_COMPLETED
REPAIR_COMPLETED
INSERT_REPLACED
HISTORY_RECORD_IMPORTED
```

复位后：

```text
关闭旧MaintenanceCycle
创建新MaintenanceCycle
cycle_version + 1
baseline_count = 业务发生时累计模次
baseline_time = 业务实际发生时间
重新计算30,000/50,000模次到期点
重新计算注塑模具下一次2个月提醒
```

---

## 3. 四类复位条件

### 3.1 保养完成

```text
工单点检完整
→ 报完工
→ 平台选择验收通过
→ 创建MaintenanceRecord
→ 创建CycleResetEvent
→ 复位周期
```

Django只检查状态和数据完整性，不检查操作者角色。

### 3.2 修模完成

```text
RepairReferral状态改为COMPLETED
→ 写入completed_at和completed_count
→ 创建MaintenanceRecord(REPAIR)
→ 复位周期
```

创建转修模记录时不立即复位。

### 3.3 换镶件完成

平台调用：

```http
POST /api/v1/molds/{mold_id}/insert-replaced
```

请求必须包含：

```text
occurred_at
occurred_count
summary（可选）
idempotency_key（建议）
```

Django创建 `MaintenanceRecord(INSERT_REPLACEMENT)` 和复位事件。

### 3.4 有效历史记录导入

平台调用：

```http
POST /api/v1/molds/{mold_id}/history-records
```

必须提供：

```text
record_type
occurred_at
occurred_count
source_record_id（建议）
source_file（可选）
summary（可选）
```

规则：

1. 使用历史记录中的实际发生时间和模次，不使用上传时间；
2. 早于当前周期基线的记录只归档，不自动倒退当前周期；
3. 缺少发生时间或发生模次时拒绝复位；
4. 同一来源记录不得重复导入；
5. 测试服务器不做角色校验，只做字段、模具和基线一致性校验。

---

## 4. 数据模型

### 4.1 MaintenanceCycle

```text
cycle_id
mold
cycle_version
baseline_count
baseline_time
trigger_rule
count_threshold_snapshot
next_time_reminder_at
status
opened_at
closed_at
```

### 4.2 CycleResetEvent

```text
reset_event_id
mold
old_cycle
new_cycle
reset_type
source_object_type
source_object_id
baseline_count_before
baseline_time_before
baseline_count_after
baseline_time_after
business_occurred_at
operator_id（可选，仅展示）
operator_name（可选，仅展示）
source_file（可选）
source_record_id（可选）
remarks（可选）
idempotency_key
created_at
```

### 4.3 MaintenanceRecord

统一保存：

```text
MAINTENANCE
REPAIR
INSERT_REPLACEMENT
HISTORY_IMPORT
```

字段以模型字段审查表为准：

- `docs/models/2026-08-13-django-model-field-review.md`

---

## 5. API

### 提醒扫描和查询

```http
POST /api/v1/alerts/scan
GET  /api/v1/alerts?alert_type=MAINTENANCE_TIME_REMINDER
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/alerts/{alert_id}/close
```

### 周期与复位

```http
GET  /api/v1/molds/{mold_id}/maintenance-cycle
GET  /api/v1/molds/{mold_id}/cycle-reset-events
POST /api/v1/molds/{mold_id}/repair-completed
POST /api/v1/molds/{mold_id}/insert-replaced
POST /api/v1/molds/{mold_id}/history-records
```

没有用户登录、主管确认或权限接口。

---

## 6. 幂等和数据保护

即使测试服务器无鉴权，仍保留：

1. 相同 `Idempotency-Key` 只执行一次；
2. 同一来源记录、模具和业务发生时间不得重复复位；
3. 当前模次小于新基线模次时拒绝；
4. 旧历史记录不倒退当前基线；
5. 复位前后均保存周期快照；
6. 旧周期未处理的时间提醒设为 `SUPERSEDED`；
7. 已执行中的工单不因其他复位事件自动删除。

这些是数据稳定性保护，不是安全鉴权。

---

## 7. 错误码

```text
TIME_REMINDER_NOT_WORK_ORDER_SOURCE
RESET_EVENT_DUPLICATE
RESET_BASELINE_DATA_INCOMPLETE
RESET_BASELINE_REGRESSION_BLOCKED
INVALID_COUNT_DATA
HISTORY_RECORD_INVALID
HISTORY_RECORD_MOLD_MISMATCH
```

---

## 8. 必测场景

### 每2个月提醒

- 注塑模具满2个自然月创建提醒；
- 未满2个月不提醒；
- 钣金模具不创建该提醒；
- 重复扫描不重复创建；
- 时间提醒不能自动创建工单；
- 周期复位后旧提醒失效；
- 月末日期计算稳定。

### 周期复位

- 保养验收通过复位；
- 修模完成复位；
- 换镶件复位；
- 有效历史记录复位；
- 无效历史记录不复位；
- 旧记录不倒退周期；
- 重复请求不重复复位；
- 复位后30,000/50,000阈值重新累计；
- 注塑2个月提醒重新计时。

---

## 9. 权威结论

```text
D03 = INTERNAL_CONFIRMED
注塑模具每2个月提醒继续保留，只提醒，不自动创建工单或派工。

D08 = INTERNAL_CONFIRMED
保养完成、修模完成、换镶件完成、有效历史记录导入均复位周期。
```

本文件已经按V4.0无角色、无鉴权测试服务器范围更新。