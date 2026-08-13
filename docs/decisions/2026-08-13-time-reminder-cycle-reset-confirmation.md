# MoldGuard 每2个月提醒与周期复位规则确认

- **确认状态**：`INTERNAL_CONFIRMED`
- **版本**：V1.2
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server V4.1
- **关联决策**：D03、D08
- **服务器边界**：无角色、无鉴权、无历史导入，仅使用 DEMO 数据

---

## 1. 每2个月提醒

当前适用于注塑模具：

```text
cycle_baseline_time + 2 calendar months
→ 生成 MAINTENANCE_TIME_REMINDER
→ 智能体平台发送信息提醒
→ 不自动创建工单
→ 不自动派工
```

采用自然月计算，不固定换算为 60 天。

Django 只保存提醒记录。提醒可以关闭，但不能作为自动工单来源。

---

## 2. 周期复位

V4.1 最终保留三类复位：

```text
MAINTENANCE_COMPLETED
REPAIR_COMPLETED
INSERT_REPLACED
```

删除：

```text
HISTORY_RECORD_IMPORTED
历史记录上传
历史导入批次
历史导入确认
历史基线修正
```

### 2.1 保养完成

工单点检完成并验收通过后：

```text
baseline_count = 当前累计模次
baseline_time = 验收完成时间
cycle_version += 1
last_reset_type = MAINTENANCE
```

同时创建 `MaintenanceRecord(record_type=MAINTENANCE)`。

### 2.2 修模完成

调用修模完成接口后：

```text
baseline_count = 请求中的完成模次
baseline_time = 请求中的完成时间
cycle_version += 1
last_reset_type = REPAIR
```

同时创建 `MaintenanceRecord(record_type=REPAIR)`。

### 2.3 换镶件完成

调用换镶件完成接口后：

```text
baseline_count = 请求中的完成模次
baseline_time = 请求中的完成时间
cycle_version += 1
last_reset_type = INSERT_REPLACEMENT
```

同时创建 `MaintenanceRecord(record_type=INSERT_REPLACEMENT)`。

---

## 3. 数据模型简化

不建立 `MaintenanceCycle` 和 `CycleResetEvent`。

当前周期字段直接保存于 `Mold`：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type
last_reset_at
```

每次复位的业务记录统一保存于 `MaintenanceRecord`。

---

## 4. 与吨位触发规则的关系

```text
cycle_count = current_count - cycle_baseline_count
```

| 开发吨位 | 阈值 |
|---:|---:|
| `<1000T` | 50,000模次 |
| `>=1000T` | 30,000模次 |

复位后，从新的基线重新计算模次到期点和注塑模具下一次2个月提醒。

---

## 5. API

```http
POST /api/v1/molds/{mold_id}/repair-completed
POST /api/v1/molds/{mold_id}/insert-replaced
```

保养完成通过：

```http
POST /api/v1/work-orders/{work_order_id}/accept
```

明确删除：

```http
POST /api/v1/molds/{mold_id}/history-records
POST /api/v1/maintenance-history/imports
```

---

## 6. 稳定性要求

- 同一个 `request_key` 不能重复复位；
- 完成模次不得小于当前周期基线；
- 完成时间不能为空；
- 复位后旧周期的开放提醒必须关闭；
- 复位和履历创建必须处于同一数据库事务；
- 无需验证操作者角色。

---

## 7. 最终结论

```text
D03：注塑模具每2个月提醒继续保留，只提醒。
D08：保养完成、修模完成、换镶件完成复位周期。
历史记录导入及其复位能力全部删除。
```