# 钣金与注塑模具自动保养触发规则确认记录

- **状态**：`INTERNAL_CONFIRMED`
- **规则版本**：`MAINT_TRIGGER_TONNAGE_V1`
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Server
- **适用模具类型**：注塑模具、钣金模具
- **确认来源**：项目负责人业务确认
- **权威级别**：当前实际业务规则
- **替代范围**：替代知识库及早期方案中用于“自动保养提醒/自动派单”的模具类别阈值、一级/二级/三级保养阈值和零件级周期阈值

---

## 1. 确认结论

当前实际业务**不区分一级、二级、三级保养**。

钣金模具和注塑模具的自动保养提醒，统一按照模具开发吨位执行：

| 开发吨位 | 自动保养提醒周期 |
|---:|---:|
| `< 1000T` | 每累计生产 `50,000` 模次触发一次 |
| `>= 1000T` | 每累计生产 `30,000` 模次触发一次 |

边界规则：

```text
999.99T 归入 <1000T，阈值 50,000 模次
1000.00T 归入 >=1000T，阈值 30,000 模次
```

---

## 2. 不作为自动触发条件的历史资料

以下内容继续保留在知识库中，但**不得用于当前系统自动提醒、自动生成计划或自动派单**：

- 按精密模具、普通模具、小型模具划分的 `30,000 / 50,000 / 100,000` 模次；
- 注塑模具二保、三保相关模次；
- 钣金模具一保、二保、三保相关模次；
- 零件级或模具编码级历史周期；
- 外部公司 A/B/C 或三级保养参考。

这些内容的系统用途限定为：

```text
HISTORICAL_REFERENCE
KNOWLEDGE_REFERENCE
MAINTENANCE_GUIDANCE
```

不得标记为：

```text
AUTOMATIC_TRIGGER
AUTO_PLAN_CREATION
AUTO_DISPATCH
```

原始 `authority` 和 `approval_status` 标签保持不变；Django通过独立字段 `automation_scope=REFERENCE_ONLY` 禁止其驱动业务状态变化。

---

## 3. Django规则编码

当前自动触发只建立两条正式规则：

### 3.1 小于1000T

```yaml
rule_id: INTERNAL-MAINT-TONNAGE-LT1000-V1
rule_family: MAINTENANCE_REMINDER
mold_types:
  - INJECTION
  - SHEET_METAL
trigger_type: COUNT
development_tonnage_min: null
development_tonnage_max_exclusive: 1000
count_threshold: 50000
maintenance_level: null
authority: INTERNAL_CONFIRMED
automation_scope: AUTOMATIC_TRIGGER
rule_version: V1.0
is_active: true
```

### 3.2 大于等于1000T

```yaml
rule_id: INTERNAL-MAINT-TONNAGE-GTE1000-V1
rule_family: MAINTENANCE_REMINDER
mold_types:
  - INJECTION
  - SHEET_METAL
trigger_type: COUNT
development_tonnage_min_inclusive: 1000
development_tonnage_max: null
count_threshold: 30000
maintenance_level: null
authority: INTERNAL_CONFIRMED
automation_scope: AUTOMATIC_TRIGGER
rule_version: V1.0
is_active: true
```

---

## 4. 当前周期模次口径

自动提醒使用“当前有效保养基准之后的累计生产模次”：

```python
cycle_count = current_count - maintenance_baseline_count
```

第一版中：

```text
maintenance_baseline_count 默认取 Mold.last_maintenance_count
```

触发判断：

```python
is_due = cycle_count >= count_threshold
remaining_count = max(count_threshold - cycle_count, 0)
overdue_count = max(cycle_count - count_threshold, 0)
```

同一模具已有未关闭预警、保养计划或工单时，后续扫描只更新超期模次和评估快照，不重复创建业务对象。

修模、换镶件、保养验收或上传历史记录是否更新 `maintenance_baseline_count`，仍由单独的周期复位决策确认；本规则记录不擅自扩大复位事件范围。

---

## 5. 对数据模型的影响

### 5.1 Mold必须具备

```text
mold_id
development_tonnage
current_count
last_maintenance_count
last_maintenance_time
mold_type
status
```

其中：

- `development_tonnage` 建议使用 `DecimalField`；
- 单位固定为 `T`；
- 开发吨位为空时不得自动触发，返回 `DEVELOPMENT_TONNAGE_NOT_CONFIGURED`；
- 当前累计模次小于保养基准时返回 `INVALID_COUNT_DATA`。

### 5.2 MaintenanceRule调整

当前自动保养提醒不再要求：

```text
maintenance_level
mold_category
mold_code_prefix
exact_mold_id
part_name
```

这些字段可继续存在，用于历史知识索引、P1扩展或其他规则族，但不得参与 `MAINT_TRIGGER_TONNAGE_V1` 的匹配。

### 5.3 WorkOrder调整

自动生成的保养计划和工单使用：

```text
maintenance_scope = PERIODIC_MAINTENANCE
maintenance_level = NOT_APPLICABLE
trigger_rule_id = INTERNAL-MAINT-TONNAGE-LT1000-V1
或
trigger_rule_id = INTERNAL-MAINT-TONNAGE-GTE1000-V1
```

不得要求智能体平台在创建计划或工单时选择一级、二级或三级保养。

---

## 6. 对API的影响

### 6.1 保养状态查询

```http
GET /api/v1/molds/{mold_id}/maintenance-status
```

至少返回：

```json
{
  "mold_id": "MOLD-2024-0891",
  "mold_type": "INJECTION",
  "development_tonnage": "850.00",
  "tonnage_band": "LT_1000T",
  "trigger_rule_id": "INTERNAL-MAINT-TONNAGE-LT1000-V1",
  "rule_authority": "INTERNAL_CONFIRMED",
  "count_threshold": 50000,
  "current_count": 250000,
  "maintenance_baseline_count": 205000,
  "cycle_count": 45000,
  "remaining_count": 5000,
  "overdue_count": 0,
  "is_due": false,
  "maintenance_level": "NOT_APPLICABLE"
}
```

### 6.2 预警扫描

```http
POST /api/v1/alerts/scan
```

扫描时：

1. 读取模具开发吨位；
2. 精确选择两条正式规则之一；
3. 计算当前周期模次；
4. 达到阈值时生成保养提醒和待确认计划；
5. 不读取精密/普通/小型分类阈值；
6. 不读取一级/二级/三级周期作为触发条件。

### 6.3 计划和工单

以下接口不再要求 `maintenance_level_code`：

```http
POST /api/v1/maintenance-plans
POST /api/v1/maintenance-plans/{plan_id}/create-work-order
```

服务端根据已确认触发规则保存规则快照和阈值快照。

---

## 7. 对知识库和智能体平台的影响

智能体平台收到 Django 返回的当前规则后，必须明确区分：

```text
CURRENT_TRIGGER_RULE
HISTORICAL_REFERENCE
MAINTENANCE_GUIDANCE
```

邮件和预警报告中的触发依据只能使用：

```text
开发吨位 <1000T，每50,000模次提醒
开发吨位 >=1000T，每30,000模次提醒
```

知识库中的3万、5万、10万和二保/三保资料可以用于：

- 解释历史标准；
- 补充保养项目；
- 提供点检和操作指导；
- 作为标准演进参考。

但不得在LLM输出中描述为“当前自动派单阈值”。

推荐平台提示约束：

```text
自动保养触发依据必须使用Django返回的trigger_rule_id、development_tonnage和count_threshold。
知识库中的模具类别阈值、一级/二级/三级周期仅作为历史或作业参考，不得覆盖Django当前规则。
```

---

## 8. 必须通过的测试

| 测试 | 预期 |
|---|---|
| 注塑模具 999.99T，周期模次49,999 | 不触发 |
| 注塑模具 999.99T，周期模次50,000 | 触发 |
| 钣金模具 850T，周期模次50,000 | 触发 |
| 注塑模具 1000T，周期模次29,999 | 不触发 |
| 注塑模具 1000T，周期模次30,000 | 触发 |
| 钣金模具 1600T，周期模次30,000 | 触发 |
| 开发吨位为空 | `DEVELOPMENT_TONNAGE_NOT_CONFIGURED` |
| 当前模次小于保养基准 | `INVALID_COUNT_DATA` |
| 命中历史类别3万规则 | 不得触发 |
| 命中二保/三保知识条目 | 不得触发 |
| 请求未传保养等级 | 正常处理，不报错 |
| 已存在未关闭计划/工单 | 不重复创建 |

---

## 9. 对负责人决策清单的影响

以下事项已由本确认记录解决：

| 决策 | 处理结果 |
|---|---|
| D02 注塑规则优先级 | 已确认：吨位规则是当前唯一自动触发规则，其他资料仅参考 |
| D04 注塑保养等级体系 | 已确认：当前实际业务不区分一级、二级、三级 |
| D05 钣金一/二/三保规则来源 | 已确认：不作为当前自动触发规则，钣金同样按开发吨位 |
| D06 边板/LC109冲突 | 不再阻塞自动触发；继续作为历史知识冲突保留 |

以下事项仍需单独确认：

- D03：每2个月提醒是否保留为独立信息提醒，以及是否生成待确认计划；
- D08：修模、换镶件、保养验收和历史记录上传的周期复位口径；
- D09：健康评分是否继续作为参赛展示字段；
- 其他未完成的负责人决策与平台Gate -1验证。

---

## 10. 最终业务表述

参赛材料和答辩应统一表述为：

> 当前系统对钣金和注塑模具不区分一级、二级、三级保养。自动保养提醒统一按照模具开发吨位执行：开发吨位小于1000T，每累计生产5万模次提醒一次；开发吨位大于等于1000T，每累计生产3万模次提醒一次。其他按精密、普通、小型模具划分的周期以及二保、三保相关模次，仅作为历史标准和保养作业知识参考，不参与当前系统自动派单。
