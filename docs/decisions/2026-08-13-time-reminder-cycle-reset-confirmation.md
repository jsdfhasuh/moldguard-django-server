# MoldGuard 每2个月提醒与保养周期复位规则确认

- **确认状态**：`INTERNAL_CONFIRMED`
- **版本**：V1.0
- **确认日期**：2026-08-13
- **适用项目**：MoldGuard 模具保养智能预警与管理智能体
- **关联决策**：D03、D08
- **关联基线**：
  - `docs/decisions/2026-08-13-maintenance-trigger-rule-confirmation.md`
  - `docs/plans/2026-08-13-moldguard-django-v3.2-trigger-rule-amendment.md`

---

## 1. D03：每2个月提醒

### 1.1 确认结论

每2个月提醒继续保留，但只作为信息提醒：

```text
每2个月达到提醒时间
→ 生成时间提醒记录
→ 智能体平台发送提醒
→ 不自动创建保养计划
→ 不自动创建工单
→ 不自动派工
```

该提醒不能覆盖或替代当前已确认的吨位模次触发规则：

```text
开发吨位 <1000T：每累计生产50,000模次触发保养提醒
开发吨位 >=1000T：每累计生产30,000模次触发保养提醒
```

### 1.2 适用范围

本确认沿用 D03 的原业务语境，当前适用于注塑模具的每2个月提醒。

钣金模具是否启用相同时间提醒，未在本次确认中扩大适用范围；如后续需要启用，必须新增独立业务确认记录。

### 1.3 Django行为

Django生成独立提醒类型：

```text
alert_type = TIME_REMINDER
business_action = REMIND_ONLY
```

时间提醒满足以下约束：

1. 只生成提醒记录，不生成 `MaintenancePlan`；
2. 只允许确认、关闭或记录通知结果；
3. 同一模具、同一周期基线和同一到期日只生成一条有效提醒；
4. 时间提醒不得作为自动建单、自动派工或排产锁定依据；
5. 智能体平台生成提醒文案时，必须明确写明“仅提醒，不代表模次保养已到期”。

### 1.4 时间计算基准

每2个月从当前保养周期基线时间开始计算：

```text
next_time_reminder_at = cycle_baseline_time + 2 calendar months
```

采用自然月计算，不固定换算为60天。

周期发生有效复位后，下一次时间提醒从新的 `cycle_baseline_time` 重新计算。

---

## 2. D08：允许复位保养周期的事件

### 2.1 确认结论

以下四类事件均允许复位保养周期：

1. 保养完成；
2. 修模完成；
3. 换镶件完成；
4. 上传历史记录。

复位同时更新：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type
last_reset_event_id
```

下一次吨位模次提醒和每2个月时间提醒均从新的周期基线重新计算。

### 2.2 事件生效条件

#### A. 保养完成

只有在保养工单完成全部适用点检，并经主管验收通过、生成保养履历后复位。

```text
reset_type = MAINTENANCE_COMPLETED
baseline_count = 验收时模具累计模次快照
baseline_time = 验收通过时间
```

#### B. 修模完成

只有修模记录完成并经授权人员确认后复位。

```text
reset_type = REPAIR_COMPLETED
baseline_count = 修模完成时模具累计模次快照
baseline_time = 修模完成确认时间
```

#### C. 换镶件完成

只有换镶件事件完成并经授权人员确认后复位。

```text
reset_type = INSERT_REPLACED
baseline_count = 换镶件完成时模具累计模次快照
baseline_time = 换镶件完成确认时间
```

#### D. 上传历史记录

上传历史记录允许复位，但必须先通过字段校验、模具归属校验和权限确认，不能因为任意文件上传就直接清零周期。

```text
reset_type = HISTORY_RECORD_IMPORTED
baseline_count = 历史记录中的保养/修模/换镶件发生模次
baseline_time = 历史记录中的实际业务发生时间
```

上传时间不作为周期基线时间。

### 2.3 历史记录技术保护

为防止历史导入破坏当前周期，冻结以下实现约束：

1. 导入记录早于当前周期基线时，只保存历史履历，不自动把基线倒退；
2. 如确需纠正当前基线，必须由 `ADMIN` 或 `MOLD_SUPERVISOR` 执行显式强制修正，并记录原因；
3. 同一来源记录、模具和业务发生时间不得重复复位；
4. 导入记录缺少发生时间或发生模次时，不允许自动复位；
5. 所有导入和复位动作必须记录来源文件、记录标识、操作人、request_id 和内容哈希。

以上属于数据完整性保护，不改变“上传有效历史记录可以复位周期”的业务结论。

---

## 3. 周期复位审计模型

Django新增或冻结 `CycleResetEvent`：

```text
reset_event_id
mold_id
reset_type
source_object_type
source_object_id
baseline_count_before
baseline_time_before
baseline_count_after
baseline_time_after
cycle_version_before
cycle_version_after
business_occurred_at
confirmed_by
confirmed_at
source_file
source_record_id
content_hash
idempotency_key
request_id
remarks
created_at
```

每次复位必须：

1. 在数据库事务中执行；
2. 对模具记录加行锁；
3. 使用 `Idempotency-Key`；
4. 写入 `CycleResetEvent`、`AuditLog` 和模具履历；
5. 关闭或重新评估旧周期下尚未处理的时间提醒；
6. 重新计算下一模次阈值和下一次2个月提醒时间。

---

## 4. 与当前吨位触发规则的关系

当前自动保养触发仍仅使用：

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 50,000模次 |
| `>=1000T` | 30,000模次 |

周期模次计算改为：

```text
cycle_count = current_count - cycle_baseline_count
```

而不是依赖固定字段名 `last_maintenance_count`。

原因是当前周期基线可能来自：

```text
保养完成
修模完成
换镶件完成
有效历史记录导入
```

时间提醒计算为：

```text
next_time_reminder_at = cycle_baseline_time + 2 calendar months
```

吨位模次到期可以驱动保养计划；每2个月时间提醒只能通知。

---

## 5. 状态与错误码

建议错误码：

```text
RESET_SOURCE_NOT_CONFIRMED
RESET_EVENT_DUPLICATE
RESET_BASELINE_DATA_INCOMPLETE
RESET_BASELINE_REGRESSION_BLOCKED
HISTORY_RECORD_INVALID
HISTORY_RECORD_MOLD_MISMATCH
TIME_REMINDER_SCOPE_NOT_ENABLED
```

时间提醒状态：

```text
OPEN
ACKNOWLEDGED
CLOSED
SUPERSEDED_BY_RESET
```

复位完成后，旧周期中尚未处理的时间提醒更新为：

```text
SUPERSEDED_BY_RESET
```

---

## 6. 必测边界

### 6.1 每2个月提醒

- 基线时间加2个自然月准确；
- 1月31日等月末日期采用稳定自然月规则；
- 同一到期日重复扫描不重复创建；
- 提醒不创建计划、工单或派工；
- 周期复位后旧提醒失效，新提醒重新计算；
- 钣金模具在未单独确认前不自动生成该时间提醒。

### 6.2 周期复位

- 保养验收完成复位；
- 修模完成确认复位；
- 换镶件完成确认复位；
- 合法历史记录导入复位；
- 无效上传不复位；
- 旧历史记录不倒退当前基线；
- 同一事件重试不重复复位；
- 复位后3万/5万阈值重新从零累计；
- 复位后2个月提醒重新计时；
- 复位前后审计数据完整。

---

## 7. 权威结论

```text
D03 = 已确认
每2个月提醒继续保留，仅提醒，不自动生成计划、工单或派工。

D08 = 已确认
保养、修模、换镶件、有效历史记录导入均可复位保养周期。
```

本确认记录状态为 `INTERNAL_CONFIRMED`，后续实施计划、API合同、数据模型、测试和比赛平台流程必须遵守。