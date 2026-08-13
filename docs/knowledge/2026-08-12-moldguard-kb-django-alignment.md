# MoldGuard 知识库与 Django 测试服务器对齐说明

- **版本**：V2.0
- **日期**：2026-08-13
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **适用计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.0
- **服务器定位**：无角色、无鉴权、仅使用 DEMO 数据的比赛测试服务器
- **模型字段审查**：`docs/models/2026-08-13-django-model-field-review.md`

---

## 1. 对齐结论

知识库与 Django 不重复建设：

```text
知识库负责：
保养做什么、检查什么、如何判定、安全要求和异常参考

Django负责：
什么时候提醒、当前周期是多少、工单处于什么状态、派给谁、点检结果和周期是否复位
```

智能体平台保存知识正文、执行 RAG、生成任务内容并发送邮件；Django只保存模拟业务事实、工单状态和本次实际使用的知识快照。

本版本已经删除早期生产级设计中的角色、权限、规则审批、送模计划和复杂知识目录模型。

---

## 2. 知识库内容概览

上传包包含 14 个文件和 353 条结构化知识条目，主要内容为：

| 内容 | 数量或规模 |
|---|---:|
| 结构化知识条目 | 353 条 |
| 注塑点检 | 11 条 |
| 钣金点检 | 11 条 |
| 注塑故障与维修工时 | 38 条 |
| 钣金故障与维修工时 | 40 条 |
| 保养标准和历史周期 | 多套来源 |
| 储放、安全、履历和流程说明 | 多份文档 |

知识库仍可用于：

- 保养项目；
- 点检清单；
- 操作方法；
- 安全注意事项；
- 验收标准；
- 故障与维修工时参考；
- 历史标准解释。

---

## 3. 当前自动业务规则

当前实际业务已经单独确认，不能由知识库中的历史周期覆盖。

### 3.1 自动保养提醒

```text
钣金和注塑模具当前不区分一级、二级、三级保养。

开发吨位 <1000T：每累计生产50,000模次触发一次。
开发吨位 >=1000T：每累计生产30,000模次触发一次。
```

状态：

```text
MAINT_TRIGGER_TONNAGE_V1
INTERNAL_CONFIRMED
```

以下知识只作参考，不参与自动提醒、自动建单或自动派工：

```text
精密/普通/小型模具的3万、5万、10万周期
一保、二保、三保周期
零件级历史周期
外部A/B/C参考
```

### 3.2 每2个月提醒

当前适用于注塑模具：

```text
cycle_baseline_time + 2 calendar months
→ 只生成提醒
→ 不自动创建工单
→ 不自动派工
```

状态：

```text
TWO_MONTH_REMINDER_V1
INTERNAL_CONFIRMED
```

### 3.3 周期复位

以下事件复位周期：

```text
保养完成
修模完成
换镶件完成
有效历史记录导入
```

状态：

```text
MAINTENANCE_CYCLE_RESET_V1
INTERNAL_CONFIRMED
```

---

## 4. 知识库与 Django 的数据边界

| 内容 | 智能体平台知识库 | Django测试服务器 |
|---|---:|---:|
| 保养项目正文 | 保存 | 不保存全文 |
| 点检标准正文 | 保存 | 保存本工单点检项快照和结果 |
| 安全要求正文 | 保存 | 只保存知识快照引用 |
| 验收标准正文 | 保存 | 保存本工单使用的条目引用 |
| 历史周期资料 | 保存并解释 | 不参与当前自动触发 |
| 当前30,000/50,000规则 | 可用于说明 | 作为当前计算规则 |
| 工单状态 | 不作为事实源 | 权威保存 |
| 候选人员、负荷和邮箱 | 只展示 | 权威保存 |
| 邮件正文 | 生成和发送 | 不保存正文 |
| 邮件发送结果 | 回写 | 保存结果记录 |
| 点检执行结果 | 采集 | 保存逐项结果 |
| 周期基线和复位 | 展示 | 权威保存 |

---

## 5. Django 为知识协同需要的最小字段

### 5.1 Mold

```text
mold_id
mold_name
mold_type
development_tonnage
knowledge_profile_code
knowledge_tags_json（可选）
```

`knowledge_profile_code` 用于平台精确选择知识集合，例如：

```text
KB-INJECTION-PERIODIC-V1
KB-SHEET-METAL-PERIODIC-V1
```

### 5.2 WorkOrder

```text
work_order_id
required_skills_json
knowledge_profile_code
trigger_rule_id_snapshot
threshold_snapshot
cycle_count_snapshot
```

`required_skills_json` 是候选人员匹配的依据，不从大模型临时猜测。

### 5.3 KnowledgeSnapshot

```text
snapshot_id
work_order
catalog_version
version_no
knowledge_items_json
content_hash
created_at
```

平台可以对同一工单重新检索并生成新版本快照。

### 5.4 InspectionItemResult

```text
work_order
sequence
knowledge_id
item_name
acceptance_criteria
inspection_method（可选）
is_critical
result
abnormal_note
not_applicable_reason
performed_at
```

点检项结果：

```text
PENDING
PASS
FAIL
NOT_APPLICABLE
```

### 5.5 NotificationRecord

```text
work_order
knowledge_snapshot
recipient_email
platform_message_id
status
sent_at
error_message
```

Django只记录平台发送结果，不负责 SMTP。

---

## 6. 知识检索流程

```text
1. 平台查询 Django 工单知识上下文
2. Django返回：
   mold_type
   knowledge_profile_code
   trigger_rule_id
   rule_version
   required_skills
3. 平台在知识库中检索保养、点检、安全和验收知识
4. 平台组装知识包
5. 平台回写 KnowledgeSnapshot
6. 平台发送邮件
7. 平台回写 NotificationRecord
8. 平台将适用点检项写入 InspectionItemResult
```

Django返回的当前触发规则优先于知识库中的历史阈值。

---

## 7. 知识快照数据格式

建议平台回写：

```json
{
  "catalog_version": "kb-v0.1",
  "knowledge_items": [
    {
      "knowledge_id": "KB-INSPECTION-INJECTION-001",
      "title": "注塑模具点检项目",
      "knowledge_type": "INSPECTION_STANDARD",
      "source_file": "05_模具保养点检标准.md",
      "source_location": "注塑模具点检",
      "authority": "INTERNAL_SOURCE",
      "approval_status": "原文录入待确认",
      "content_hash": "sha256..."
    }
  ]
}
```

测试服务器不校验复杂审批角色，但必须保留来源、条目标识和内容哈希，便于答辩说明知识来源。

---

## 8. 点检知识的处理

知识库中的注塑和钣金点检项可完整用于邮件和现场演示。

Django约束：

1. 所有适用项填写后才能报完工；
2. `FAIL` 必须填写异常说明；
3. `NOT_APPLICABLE` 必须填写原因；
4. 关键项失败可以转修模；
5. Django保存结果，不判断自然语言内容是否正确；
6. 智能体平台负责展示点检方法和验收知识。

不需要把353条知识全部导入 Django。

---

## 9. 故障与维修工时

知识库包含78条故障与维修工时，可用于异常说明和转修模参考。

测试服务器 P0：

- 不建立 `FaultStandard` 模型；
- 平台直接在知识库中检索故障与工时；
- Django只保存 `RepairReferral.reason` 和可选 `fault_summary`；
- 不自动生成确定性维修步骤；
- 修模完成后通过接口写入记录并复位周期。

完整故障标准数据库放到 P1。

---

## 10. 已删除的早期复杂设计

V4.0测试服务器不建立：

```text
MaintenanceScheme
MaintenanceLevel
MaintenanceTriggerPoint
RuleSource
RuleConflict
RuleApprovalRecord
KnowledgeCatalogRelease
KnowledgeSnapshotItem独立表
FaultStandard
FaultMatchCandidate
MaintenancePlan
MoldDeliverySchedule
用户、角色和权限模型
```

原因：

- 当前自动规则已收敛为两条开发吨位规则；
- 当前不区分保养等级；
- 服务器只用于比赛演示；
- 知识正文和检索由智能体平台完成；
- 复杂模型不会提升主链路展示效果。

---

## 11. P0与P1边界

### P0

```text
当前吨位触发规则
注塑2个月提醒
知识上下文
知识快照
点检项快照与结果
邮件结果回写
点检失败转修模
周期复位
```

### P1

```text
完整故障标准数据库
故障同义词匹配
知识目录发布审批
图片附件上传
外部A/B/C规则映射
备件、供应商和成本
```

---

## 12. 字段审查入口

Django所有建议模型和字段已经集中列在：

- [`docs/models/2026-08-13-django-model-field-review.md`](../models/2026-08-13-django-model-field-review.md)

负责人应先审查该文件中的 F01—F10，再开始编写 `models.py` 和数据库迁移。

---

## 13. 最终结论

知识库 V0.1 足以支持比赛中的：

```text
保养项目
点检清单
安全要求
验收标准
异常和维修工时参考
```

Django测试服务器不重复建设知识库，只保存：

```text
知识检索上下文
本工单使用的知识快照
逐项点检结果
邮件发送结果
```

当前30,000/50,000吨位规则、注塑2个月提醒和四类周期复位由 Django 按已确认规则执行；知识库中的历史周期不得覆盖这些当前业务规则。