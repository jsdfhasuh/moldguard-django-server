# 钣金与注塑模具自动保养触发规则确认记录

- **状态**：`INTERNAL_CONFIRMED`
- **版本**：V1.2
- **规则版本**：`MAINT_TRIGGER_TONNAGE_V1`
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server V4.1
- **适用模具类型**：注塑模具、钣金模具

---

## 1. 当前规则

当前不区分一级、二级、三级保养。

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 50,000模次 |
| `>=1000T` | 30,000模次 |

边界：

```text
999.99T → 50,000
1000.00T → 30,000
```

---

## 2. 当前实现方式

V4.1不建立 `MaintenanceRule` 数据表。

在规则服务中使用两个常量：

```text
MAINT-TONNAGE-LT1000-V1
MAINT-TONNAGE-GTE1000-V1
```

计算：

```text
cycle_count = current_count - cycle_baseline_count
is_due = cycle_count >= threshold
remaining_count = max(threshold - cycle_count, 0)
overdue_count = max(cycle_count - threshold, 0)
```

开发吨位为空返回：

```text
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
```

当前模次小于周期基线返回：

```text
INVALID_COUNT_DATA
```

---

## 3. 不参与自动触发的资料

```text
精密、普通、小型模具3万、5万、10万模次
一保、二保、三保周期
零件级历史周期
外部A/B/C保养体系
```

这些内容只在智能体平台知识库中用于作业说明，不导入 Django 规则表。

---

## 4. Django字段

Mold必须具备：

```text
mold_id
mold_type
development_tonnage
current_count
cycle_baseline_count
cycle_baseline_time
cycle_version
```

Alert保存本次扫描快照：

```text
cycle_count_snapshot
threshold_snapshot
usage_percent_snapshot
```

---

## 5. 扫描行为

```http
POST /api/v1/alerts/scan
```

扫描时：

1. 选择吨位阈值；
2. 计算当前周期模次；
3. 达到阈值时创建模次到期提醒；
4. 使用 `dedupe_key` 防止同一周期重复提醒；
5. 已有未关闭工单时不得重复创建工单。

扫描只创建提醒，不创建保养计划或送模记录。

---

## 6. 测试

- 999.99T / 49,999：不触发；
- 999.99T / 50,000：触发；
- 1000T / 29,999：不触发；
- 1000T / 30,000：触发；
- 开发吨位为空：返回错误；
- 历史分类和保养等级资料不得改变阈值；
- 重复扫描不得重复创建提醒。

---

## 7. 最终表述

> 当前钣金和注塑模具不区分一级、二级、三级保养。自动保养提醒统一按照模具开发吨位执行：开发吨位小于1000T，每累计生产5万模次提醒一次；开发吨位大于等于1000T，每累计生产3万模次提醒一次。其他历史周期仅作为知识参考。