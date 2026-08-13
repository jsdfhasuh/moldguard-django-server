# 钣金与注塑模具自动保养触发规则确认记录

- **状态**：`INTERNAL_CONFIRMED`
- **版本**：V1.1
- **规则版本**：`MAINT_TRIGGER_TONNAGE_V1`
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server V4.0
- **适用模具类型**：注塑模具、钣金模具
- **确认来源**：项目负责人业务确认
- **替代范围**：替代知识库及早期方案中用于自动提醒、自动工单和自动派单的模具类别阈值、保养等级阈值和零件级周期

---

## 1. 确认结论

当前实际业务不区分一级、二级、三级保养。

| 开发吨位 | 自动保养提醒周期 |
|---:|---:|
| `<1000T` | 每累计生产50,000模次触发一次 |
| `>=1000T` | 每累计生产30,000模次触发一次 |

边界：

```text
999.99T → 50,000模次
1000.00T → 30,000模次
```

---

## 2. 历史知识的使用范围

以下内容继续保留在智能体知识库，但不得作为当前自动触发条件：

```text
精密/普通/小型模具的3万、5万、10万模次
一保、二保、三保周期
零件级历史周期
外部A/B/C参考
```

允许用途：

```text
历史标准说明
保养作业知识
点检和操作参考
```

禁止用途：

```text
覆盖Django当前阈值
自动创建提醒
自动创建工单
自动派工
```

---

## 3. Django测试服务器规则数据

当前只建立两条规则：

```yaml
- rule_id: MAINT-TONNAGE-LT1000-V1
  mold_type_scope: BOTH
  tonnage_min: null
  tonnage_max: 1000
  min_inclusive: true
  max_inclusive: false
  count_threshold: 50000
  authority: INTERNAL_CONFIRMED
  version: V1.0
  is_active: true

- rule_id: MAINT-TONNAGE-GTE1000-V1
  mold_type_scope: BOTH
  tonnage_min: 1000
  tonnage_max: null
  min_inclusive: true
  max_inclusive: false
  count_threshold: 30000
  authority: INTERNAL_CONFIRMED
  version: V1.0
  is_active: true
```

不建立复杂规则审批、保养等级、模具类别和零件级匹配模型。

---

## 4. 周期模次口径

```text
cycle_count = current_count - MaintenanceCycle.baseline_count
```

触发：

```text
is_due = cycle_count >= count_threshold
remaining_count = max(count_threshold - cycle_count, 0)
overdue_count = max(cycle_count - count_threshold, 0)
```

开发吨位为空时：

```text
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
```

当前累计模次小于周期基线时：

```text
INVALID_COUNT_DATA
```

---

## 5. V4.0测试服务器行为

`POST /api/v1/alerts/scan`：

1. 读取模拟模具；
2. 按开发吨位选择规则；
3. 计算周期模次；
4. 到期时创建 `MAINTENANCE_DUE_COUNT` 提醒；
5. 已存在相同周期未关闭提醒或工单时不重复创建；
6. 不创建单独的保养计划或送模记录。

平台选择提醒后，直接调用：

```http
POST /api/v1/work-orders
```

工单不要求一级、二级或三级保养字段。

---

## 6. API返回要求

`GET /api/v1/molds/{mold_id}/maintenance-status` 至少返回：

```json
{
  "mold_id": "MOLD-2024-0891",
  "mold_type": "INJECTION",
  "development_tonnage": "850.00",
  "trigger_rule_id": "MAINT-TONNAGE-LT1000-V1",
  "rule_authority": "INTERNAL_CONFIRMED",
  "count_threshold": 50000,
  "current_count": 251625,
  "cycle_baseline_count": 205000,
  "cycle_count": 46625,
  "usage_percent": 93.25,
  "remaining_count": 3375,
  "is_due": false
}
```

不返回或要求：

```text
maintenance_level
主管确认状态
规则审批人
API鉴权信息
```

---

## 7. 智能体平台约束

平台必须使用 Django 返回的：

```text
trigger_rule_id
development_tonnage
count_threshold
cycle_count
```

生成预警说明。

知识库中的历史周期不得被描述为当前自动派单规则。

---

## 8. 必测边界

| 场景 | 预期 |
|---|---|
| 999.99T，周期模次49,999 | 不到期 |
| 999.99T，周期模次50,000 | 到期 |
| 1000T，周期模次29,999 | 不到期 |
| 1000T，周期模次30,000 | 到期 |
| 注塑和钣金相同吨位 | 使用相同阈值 |
| 开发吨位为空 | 返回明确错误 |
| 知识命中历史等级周期 | 不改变自动触发结果 |
| 已有未关闭工单 | 不重复创建 |

---

## 9. 最终表述

> 当前系统对钣金和注塑模具不区分一级、二级、三级保养。自动保养提醒统一按照模具开发吨位执行：开发吨位小于1000T，每累计生产5万模次提醒一次；开发吨位大于等于1000T，每累计生产3万模次提醒一次。其他分类周期和保养等级周期仅作为历史标准及作业知识参考。

本确认记录与V4.0测试服务器实施计划共同构成当前触发规则基线。