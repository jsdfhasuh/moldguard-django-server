# MoldGuard Django 实施计划 V3.2——自动保养触发规则修订

- **状态**：`NORMATIVE_AMENDMENT`
- **版本**：V3.2
- **日期**：2026-08-13
- **上位计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`（V3.1）
- **确认依据**：`docs/decisions/2026-08-13-maintenance-trigger-rule-confirmation.md`
- **适用范围**：自动保养提醒、自动保养计划、自动工单触发
- **优先级**：本修订在冲突处优先于V3.1

---

## 1. 修订目的

V3.1依据知识库V0.1保留了模具类别、吨位、编码、零件级、一保/二保/三保等多种规则模型。项目负责人现已确认当前实际业务规则：

1. 注塑和钣金模具不区分一级、二级、三级保养；
2. 自动保养提醒统一按开发吨位判断；
3. `<1000T` 每累计生产50,000模次触发；
4. `>=1000T` 每累计生产30,000模次触发；
5. 其他分类周期、二保和三保模次只作为历史标准或作业知识参考；
6. 该结论状态为 `INTERNAL_CONFIRMED`。

因此，本修订收缩自动规则匹配面，避免知识库中的历史标准或冲突条目参与自动计划和派单。

---

## 2. 对V3.1的替代关系

以下V3.1设计不再适用于当前自动保养触发：

- 按精密、普通、小型模具匹配3万、5万、10万模次；
- 按LC编码、零件名称或边板/连续模类型选择自动提醒阈值；
- 根据一保、二保、三保周期自动生成不同等级计划；
- 要求创建计划或工单时传入 `maintenance_level_code`；
- 在自动触发时执行“精确模具 → 类别 → 吨位 → 通用”的多级规则回退。

这些内容仍可保留在数据模型与知识库中，但必须设置：

```text
automation_scope = REFERENCE_ONLY
```

---

## 3. 当前自动规则集

规则集名称：

```text
INTERNAL_MAINT_TRIGGER_TONNAGE_V1
```

规则：

| 规则ID | 模具类型 | 开发吨位 | 阈值 | 权威状态 |
|---|---|---:|---:|---|
| `INTERNAL-MAINT-TONNAGE-LT1000-V1` | 注塑、钣金 | `<1000T` | 50,000模次 | `INTERNAL_CONFIRMED` |
| `INTERNAL-MAINT-TONNAGE-GTE1000-V1` | 注塑、钣金 | `>=1000T` | 30,000模次 | `INTERNAL_CONFIRMED` |

该规则集允许在比赛环境和后续正式环境自动执行，不需要再复制为 `DEMO_APPROVED` 规则。

主演示数据若沿用20万模次阈值，只能作为原方案历史演示样例，不得再宣称为当前实际自动保养触发规则。新的主演示模具应按开发吨位配置为3万或5万周期。

---

## 4. 数据模型修订

### 4.1 Mold

P0必需字段：

```text
mold_id
mold_name
mold_type
development_tonnage
current_count
last_maintenance_count
last_maintenance_time
status
primary_location
secondary_location
production_line
```

`development_tonnage`：

```python
DecimalField(max_digits=10, decimal_places=2)
```

约束：

- 不得为负；
- 自动扫描对象必须配置开发吨位；
- 单位固定为T；
- 1000T边界使用Decimal比较。

### 4.2 MaintenanceRule

当前自动触发需要的字段：

```text
rule_id
rule_family
trigger_type
mold_types
tonnage_min_inclusive
tonnage_max_exclusive
count_threshold
count_basis
authority
automation_scope
rule_version
effective_from
effective_to
is_active
```

以下字段对当前规则为可空或不参与匹配：

```text
maintenance_level
mold_category
mold_code_prefix
exact_mold_id
part_name
model_code
cavity_layout
```

### 4.3 MaintenancePlan与WorkOrder

新增或冻结：

```text
maintenance_scope = PERIODIC_MAINTENANCE
maintenance_level = NOT_APPLICABLE
trigger_rule_id
trigger_rule_version
trigger_threshold_snapshot
trigger_tonnage_snapshot
cycle_count_snapshot
```

历史知识中出现的保养等级可保存在：

```text
reference_labels
knowledge_snapshot
```

但不得写入当前业务等级字段或改变状态机。

---

## 5. 规则计算服务

服务：

```text
MaintenanceTriggerService
```

处理流程：

```text
读取模具
→ 校验开发吨位
→ 选择吨位区间规则
→ 读取有效保养基准
→ 计算本周期模次
→ 判断是否达到阈值
→ 返回规则快照和计算结果
```

算法：

```python
cycle_count = current_count - maintenance_baseline_count
is_due = cycle_count >= count_threshold
remaining_count = max(count_threshold - cycle_count, 0)
overdue_count = max(cycle_count - count_threshold, 0)
```

禁止：

- 从知识库正文解析阈值；
- 按模具类别覆盖吨位规则；
- 按保养等级覆盖吨位规则；
- 在规则冲突时让LLM决定阈值；
- 开发吨位缺失时使用默认阈值。

---

## 6. 预警、计划和工单行为

### 6.1 扫描

`POST /api/v1/alerts/scan`：

- 注塑、钣金使用同一吨位规则集；
- 达到阈值时生成 `MAINTENANCE_DUE` 预警；
- 不要求保养等级；
- 已有未关闭预警/计划/工单时不重复创建；
- 保存规则ID、吨位、阈值和周期模次快照。

### 6.2 计划

自动计划内容：

```text
source_type = AUTO
maintenance_scope = PERIODIC_MAINTENANCE
requested_level = NOT_APPLICABLE
```

计划确认、关闭、送模和工单流程保持V3.1设计。

### 6.3 工单

工单的具体保养项目、点检要求和安全要求由智能体平台从知识库检索后形成知识快照；触发规则只回答“为什么现在需要保养”，不直接决定全部作业步骤。

---

## 7. API契约修订

### 7.1 maintenance-status

返回新增字段：

```text
development_tonnage
tonnage_band
trigger_rule_id
trigger_rule_version
rule_authority
count_threshold
maintenance_baseline_count
cycle_count
remaining_count
overdue_count
is_due
maintenance_scope
maintenance_level
```

其中：

```text
maintenance_scope = PERIODIC_MAINTENANCE
maintenance_level = NOT_APPLICABLE
```

### 7.2 rules/match

当前自动保养规则匹配只接受：

```text
mold_id
或
mold_type + development_tonnage
```

不再要求：

```text
maintenance_level_code
mold_category
```

响应必须包含：

```text
match_strategy = DEVELOPMENT_TONNAGE
```

### 7.3 knowledge-context

知识上下文返回两类信息：

```json
{
  "current_trigger_rule": {
    "rule_id": "INTERNAL-MAINT-TONNAGE-LT1000-V1",
    "authority": "INTERNAL_CONFIRMED",
    "count_threshold": 50000
  },
  "reference_knowledge_filters": {
    "mold_type": "INJECTION",
    "usage_scope": "MAINTENANCE_GUIDANCE"
  }
}
```

历史周期不得出现在 `current_trigger_rule` 中。

---

## 8. 知识治理修订

知识条目增加或派生以下字段：

```text
automation_scope:
  AUTOMATIC_TRIGGER
  MANUAL_REVIEW
  REFERENCE_ONLY

business_usage:
  TRIGGER_RULE
  MAINTENANCE_GUIDANCE
  INSPECTION_GUIDANCE
  HISTORICAL_STANDARD
```

本次确认产生的两条规则：

```text
automation_scope = AUTOMATIC_TRIGGER
business_usage = TRIGGER_RULE
authority = INTERNAL_CONFIRMED
```

其他3万/5万/10万、二保/三保周期：

```text
automation_scope = REFERENCE_ONLY
business_usage = HISTORICAL_STANDARD 或 MAINTENANCE_GUIDANCE
```

保留原始来源，不对知识包V0.1做静默覆盖；后续知识包V0.2应增加本确认记录和使用范围字段。

---

## 9. 健康评分处理

健康评分如果继续用于参赛展示，只能基于当前实际阈值计算周期使用率：

```text
usage_ratio = cycle_count / 50000
或
usage_ratio = cycle_count / 30000
```

健康评分不得改变自动触发结果；自动触发唯一依据为：

```text
cycle_count >= count_threshold
```

负责人决策D09未完成前，健康评分保持独立展示功能，不作为P0业务状态机的阻塞条件。

---

## 10. 演示数据修订

至少准备：

| 场景 | 模具类型 | 吨位 | 周期模次 | 结果 |
|---|---|---:|---:|---|
| 绿色 | 注塑 | 850T | 35,000 | 未到期 |
| 黄色/临界展示 | 注塑 | 850T | 46,625 | 93.25% |
| 到期 | 钣金 | 850T | 50,000 | 触发 |
| 未到期 | 注塑 | 1000T | 29,999 | 未触发 |
| 到期 | 注塑 | 1000T | 30,000 | 触发 |
| 超期 | 钣金 | 1600T | 36,000 | 超期6,000 |
| 异常 | 任意 | 空 | 任意 | 吨位未配置 |

若要继续演示“93.25%”场景，应把周期模次改为：

```text
46,625 / 50,000 = 93.25%
```

原方案中的：

```text
186,500 / 200,000 = 93.25%
```

可保留在历史方案说明中，但不作为当前实际规则的主演示数据。

---

## 11. 测试门禁修订

P0必须增加：

- 注塑和钣金均按吨位匹配；
- 999.99T与1000.00T边界；
- 49,999/50,000边界；
- 29,999/30,000边界；
- Decimal精度；
- 吨位缺失；
- 类别规则不得覆盖；
- 一保/二保/三保资料不得触发；
- 创建计划和工单不要求保养等级；
- 已存在未关闭业务对象时扫描幂等；
- API和知识上下文明确区分当前规则与历史参考。

---

## 12. 已解决和仍待确认的决策

已解决：

```text
D02 注塑规则优先级
D04 注塑保养等级体系
D05 钣金保养等级和规则来源
D06 边板/LC109冲突对自动触发的影响
```

仍待确认：

```text
D03 每2个月提醒的业务作用
D07 两次关闭机会口径
D08 周期复位事件
D09 健康评分展示
D10—D18
P01—P05 平台能力验证
M01—M05 参赛材料口径
```

---

## 13. 实施顺序调整

Phase 0优先交付：

1. 两条 `INTERNAL_CONFIRMED` 吨位规则；
2. `development_tonnage` 数据字典；
3. 当前周期模次口径；
4. 规则与历史知识隔离；
5. API响应样例；
6. 边界测试；
7. 新主演示数据。

完成后，才进入预警扫描、保养计划和工单编码。

---

## 14. 当前权威基线

当前开发基线由以下文件共同组成：

1. V3.1完整实施计划；
2. 本V3.2触发规则修订；
3. `2026-08-13-maintenance-trigger-rule-confirmation.md`；
4. 最新负责人决策清单；
5. 智能体平台与Django关系说明；
6. 知识库与Django对齐说明。

发生冲突时，本修订对自动保养触发、保养等级和当前周期阈值拥有更高优先级。
