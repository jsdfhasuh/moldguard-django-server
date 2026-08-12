# 智能体平台与 Django 服务器关系说明

- **版本**：V1.1
- **日期**：2026-08-12
- **适用项目**：MoldGuard 模具保养智能预警与管理智能体
- **实施计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`
- **业务场景**：`docs/business/2026-08-12-moldguard-business-scenarios.md`
- **知识对齐**：`docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md`

---

## 1. 一句话说明

> **智能体平台负责“理解、检索、生成、编排和通知”，Django 负责“数据、规则、计划、事务、状态、点检和审计”。**

智能体平台是用户入口和智能流程层；Django 是业务事实源、规则治理中心以及计划和工单全生命周期状态中心。

两者共同完成：

```text
预警
→ 保养计划
→ 计划确认与送模
→ 工单与派工
→ 知识随单邮件
→ 执行与逐项点检
→ 报完工与验收
→ 不合格转修模 / 合格归档
→ 履历与统计分析
```

---

## 2. 总体架构

```text
┌────────────────────────────────────────────────────┐
│                    比赛智能体平台                   │
│                                                    │
│ 对话 │ Workflow │ 知识库/RAG │ LLM │ 确认 │ 邮件  │
└────────────────────────┬───────────────────────────┘
                         │ HTTPS + JSON
                         │ X-API-Key
                         │ X-Request-ID
                         │ Idempotency-Key
                         ▼
┌────────────────────────────────────────────────────┐
│              MoldGuard Django Server               │
│                                                    │
│ 模具 │ 版本化规则 │ 预警 │ 计划 │ 送模 │ 工单     │
│ 人员 │ 派工校验   │ 点检 │ 验收 │ 修模 │ 履历     │
│ 知识快照 │ 邮件回写 │ 工时 │ 统计 │ 审计          │
└────────────────────────┬───────────────────────────┘
                         ▼
                    PostgreSQL 16
```

---

## 3. 两者为什么必须配合

智能体平台适合：

- 自然语言理解；
- 多节点流程编排；
- 知识库检索；
- 预警、任务和催办内容生成；
- 邮件生成与发送；
- 对话式数据分析。

Django适合：

- 精确模次和工时计算；
- 多版本规则匹配与审批；
- 预警和计划持久化；
- 工单去重；
- 角色与权限；
- 合法状态跳转；
- 数据库事务和并发控制；
- 点检结果、验收和修模分流；
- 可复算统计与审计。

智能体平台不能只依赖会话变量管理业务状态；Django也不重复建设向量知识库和邮件系统。

---

## 4. 权威数据与知识边界

| 内容 | 权威系统 |
|---|---|
| 模具编号、模次、位置、状态 | Django |
| 规则 ID、阈值、工时、版本和审批状态 | Django |
| 健康评分、预警和计划状态 | Django |
| 人员、技能、负荷、在岗状态和邮箱 | Django |
| 送模、工单、派工和状态时间线 | Django |
| 点检执行结果、验收、修模和履历 | Django |
| 点检、操作、安全、储放和故障文档正文 | 智能体平台知识库 |
| 本次实际使用的知识条目快照 | Django，由平台回写 |
| 邮件正文和附件 | 智能体平台 |
| 邮件发送结果审计 | Django，由平台回写 |
| 自然语言分析结论 | 智能体平台 |

发生冲突时，以权威系统数据为准。

---

## 5. 知识库治理关系

知识库 V0.1 有 353 条结构化条目，但当前没有 `INTERNAL_CONFIRMED` 条目，且存在多套注塑、钣金阈值及术语体系。

因此两端分工如下。

### 5.1 智能体平台

- 保存 Markdown 和 JSONL 知识内容；
- 按 `rule_id`、`knowledge_profile_code`、模具类型和保养等级进行检索；
- 返回点检、操作、安全、验收、储放和故障工时知识；
- 保留来源文件、来源位置、authority、approval_status 和 rule_version；
- 不自行选择冲突规则；
- 命中待确认条目时引导主管确认。

### 5.2 Django

- 保存可执行的结构化规则；
- 保存规则审批和环境许可；
- 保存知识目录版本和包哈希；
- 校验本次工单知识条目是否允许使用；
- 保存 `KnowledgeSnapshot` 和 `InspectionTemplateSnapshot`；
- 阻止待确认和外部参考条目自动成为强制验收依据。

### 5.3 自动执行许可

```text
DEMO 环境：DEMO_APPROVED、INTERNAL_CONFIRMED
生产环境：INTERNAL_CONFIRMED
```

来源标签和使用审批是两个不同概念。比赛批准不能把原始 `INTERNAL_SOURCE` 篡改成企业已确认标准。

---

## 6. 业务环节职责矩阵

| 业务环节 | 智能体平台 | Django |
|---|---|---|
| MES/模拟数据查询 | 调用接口、展示 | 保存或适配模具事实 |
| 自动巡检 | 定时/手动触发 | 匹配已批准规则并保存预警 |
| 手动保养申请 | 理解原因、采集信息 | 创建手动计划和审计 |
| 计划确认 | 引导主管确认 | 保存确认、关闭次数和原因 |
| 计划送模 | 提醒计划部/分厂 | 保存计划、要求交模和实际送达 |
| 工单创建 | 调用接口、展示结果 | 创建、去重和保存快照 |
| 候选人员 | 展示并让主管选择 | 按技能、负荷、产线和等级筛选 |
| 最终派工 | 接收主管选择 | 再校验并保存派工结果 |
| 知识检索 | RAG检索正文 | 返回规则/画像/标签 |
| 知识随单 | 组装任务和知识 | 保存实际使用条目快照 |
| 邮件 | 生成并发送 | 保存发送结果 |
| 开工/暂停/恢复 | 接收人员操作 | 校验状态和角色，记录时间线 |
| 逐项点检 | 展示知识点检模板 | 保存 PASS/FAIL/NA 和证据 |
| 报完工 | 引导提交 | 校验点检完整性，进入待验收 |
| 验收 | 检索验收标准、引导主管 | 保存验收、更新履历或转修模 |
| 修模分流 | 生成异常说明 | 保存 RepairReferral 和故障候选 |
| 超时催办 | 生成话术、发通知 | 识别超时并保存升级记录 |
| 分析 | 理解问题、生成图表和结论 | 提供可复算统计数据 |

---

## 7. 核心交互时序

## 7.1 自动巡检和计划生成

```text
平台
  │ POST /api/v1/alerts/scan
  ▼
Django
  │ 读取模具
  │ 匹配已批准规则
  │ 区分保养/寿命/闲置提醒
  │ 保存预警和待确认计划
  ▼
平台
  │ 展示来源、阈值、健康评分和建议
  │ 生成预警报告
```

规则冲突、未批准或缺失时，Django返回明确错误或待确认状态，平台不得让 LLM 自行取值。

## 7.2 计划确认、关闭和送模

```text
平台：主管确认是否需要保养
  │ POST /maintenance-plans/{id}/confirm 或 /close
  ▼
Django：保存确认或关闭次数、原因和证据

平台：计划部确定送模和要求交模时间
  │ POST /maintenance-plans/{id}/schedule-delivery
  ▼
Django：进入 PENDING_DELIVERY

平台：分厂确认送模
  │ POST /maintenance-plans/{id}/mark-delivered
  ▼
Django：进入 DELIVERED
```

“两次关闭机会”必须由 Django 计数，不能只在平台变量中计算。

## 7.3 创建工单与派工

```text
平台
  │ POST /maintenance-plans/{id}/create-work-order
  ▼
Django
  │ 检查计划确认和送模状态
  │ 防止重复工单
  │ 创建 PENDING_ASSIGNMENT 工单
  ▼
平台
  │ GET /work-orders/{id}/candidates
  ▼
Django
  │ 返回候选、匹配技能、负荷、产线、等级和邮箱
  ▼
平台
  │ 主管选择人员
  │ POST /work-orders/{id}/assign
  ▼
Django
  │ 重新校验
  │ 保存派工和 ASSIGNED 状态
```

候选查询不表示派工成功。

## 7.4 知识检索与邮件

```text
平台
  │ GET /work-orders/{id}/knowledge-context
  ▼
Django
  │ 返回 rule_id、知识画像、规则版本、过滤标签
  ▼
平台
  │ 检索保养项目、22条点检、安全、验收和故障工时
  │ 组装知识包
  │ POST /work-orders/{id}/knowledge-snapshot
  ▼
Django
  │ 校验条目来源和使用许可
  │ 保存知识快照与点检模板快照
  ▼
平台
  │ 发送任务邮件
  │ POST /work-orders/{id}/notifications
  ▼
Django
  │ 保存发送状态、消息ID和时间
```

邮件失败不回滚派工，但必须记录并重试。

## 7.5 开工、点检和报完工

```text
平台：保养人员开工
  │ POST /work-orders/{id}/start
  ▼
Django：ASSIGNED → IN_PROGRESS

平台：暂停/恢复
  │ POST /pause /resume
  ▼
Django：保存暂停区间和原因

平台：执行人员逐项点检
  │ POST /inspection-results
  ▼
Django：保存 PASS / FAIL / NOT_APPLICABLE

平台：提交报完工
  │ POST /report-complete
  ▼
Django：校验全部适用项已填写
         无失败 → PENDING_ACCEPTANCE
         关键失败 → TRANSFERRED_TO_REPAIR
```

`NOT_APPLICABLE` 必须由人员选择并说明原因，不能由模型自动决定。

## 7.6 验收、修模和归档

```text
平台：主管依据知识库验收
  │ POST /accept
  ▼
Django
  │ COMPLETED
  │ 生成 MaintenanceRecord
  │ 更新模具保养基准
  │ 关闭计划和预警
  │ 计算下一提醒
```

不合格：

```text
POST /reject 或 /transfer-to-repair
→ Django创建 RepairReferral
→ 保存失败点检和故障候选
→ 转入修模业务
```

故障知识只提供分类、描述和标准工时；资料没有根因和维修步骤时，平台不得编造确定性维修方案。

---

## 8. 知识包数据契约

平台回写的知识包至少包含：

```json
{
  "work_order_id": "WO-...",
  "catalog_version": "kb-v0.1",
  "rule_id": "DEMO-RULE-...",
  "rule_authority": "DEMO_APPROVED",
  "rule_version": "V1.0",
  "trigger_basis": {},
  "maintenance_items": [],
  "inspection_items": [],
  "safety_notes": [],
  "completion_requirements": [],
  "source_documents": []
}
```

每个条目至少包含：

```text
knowledge_id
title
knowledge_type
source_file
source_location
authority
approval_status
rule_version
content_hash
```

Django校验：

- 工单、模具和规则一致；
- 规则在当前环境获准执行；
- 条目有来源和版本；
- PENDING 条目有主管 override；
- EXTERNAL_REFERENCE 不作为强制验收；
- 内容哈希和目录版本可追溯。

---

## 9. 状态权威原则

平台可以展示状态，但不得自行维护业务状态。以下状态只以 Django 为准：

### 保养计划

```text
DRAFT
PENDING_CONFIRMATION
CONFIRMED
CLOSED
PENDING_DELIVERY
DELIVERED
WORK_ORDER_CREATED
CANCELLED
```

### 工单

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
PENDING_INSPECTION
PENDING_ACCEPTANCE
TRANSFERRED_TO_REPAIR
COMPLETED
CANCELLED
```

平台必须使用接口响应更新界面，不得假设请求成功。

---

## 10. 权限、幂等和失败处理

### 10.1 权限

`X-API-Key` 只证明调用方是受信任平台。具体动作仍按 actor_id 和角色校验。

### 10.2 幂等

所有写接口携带稳定 `Idempotency-Key`。网络超时重试时使用相同键，Django返回首次结果，不重复创建计划、工单、派工、状态事件或通知记录。

### 10.3 失败原则

| 失败 | 处理 |
|---|---|
| 规则未批准 | 停止自动动作，提示主管确认 |
| 规则冲突 | 返回冲突，不静默选择 |
| 知识无召回 | 不发送缺少安全/验收内容的正式邮件 |
| 邮件失败 | 保留派工，回写 FAILED 并重试 |
| 点检不完整 | 拒绝报完工 |
| 点检失败 | 转修模，不直接结单 |
| Django超时但可能已执行 | 使用同一幂等键重试 |
| LLM输出与Django冲突 | 以Django事实为准 |

---

## 11. 主要业务场景

完整业务场景见配套文档。参赛主流程包括：

1. 自动巡检和保养计划；
2. 计划确认与两次关闭机会；
3. 计划部排产和分厂送模；
4. 候选人员匹配和主管派工；
5. 点检知识随任务邮件下发；
6. 开工、暂停、恢复和异常；
7. 逐项点检、报完工和验收；
8. 不合格转修模；
9. 履历更新和工时分析。

扩展场景包括生产中日常保养、入库储放、跨基地调动、闲置模恢复、故障工时、寿命提醒和闲置模具管理。

---

## 12. 答辩说明

可采用以下表述：

> 我们没有让大模型直接修改制造业务数据。智能体平台负责理解用户需求、检索点检知识、生成任务说明和发送邮件；Django负责模具数据、规则版本、计划确认、送模、工单状态、人员资格、逐项点检、验收、修模分流、实际工时和审计。知识库中的规则存在多版本和待确认项，因此系统使用规则审批和演示规则集隔离：未批准规则不会自动触发业务。每次创建计划、派工、点检、报工或验收都必须调用 Django，由 Django 校验后才能生效。

---

## 13. 不允许的实现方式

- LLM自行选择冲突阈值；
- 把全部 INTERNAL_SOURCE 直接当成已确认规则；
- 将外部 A/B/C 自动映射为内部一/二/三保；
- 将寿命提醒当成日常保养提醒；
- 平台显示已派工但未写入 Django；
- 计划关闭次数只保存在平台变量；
- 未送模直接开始拆模保养；
- 未逐项点检就报完工；
- 点检失败直接验收完成；
- 邮件发送后不回写；
- 未确认故障时默认使用 5 小时；
- 用户仅声明姓名工号就获得主管权限；
- 验收完成后不更新模具履历和下一周期基准。

---

## 14. 最终关系总结

```text
智能体平台
= 智能交互层
+ 流程编排层
+ 知识检索层
+ 内容生成层
+ 邮件通知层

Django
= 业务数据层
+ 规则治理层
+ 计划工单层
+ 状态事务层
+ 点检验收层
+ 修模分流层
+ 统计审计层
```

智能体平台让系统“会理解、会检索、会表达、会通知”；Django让系统“规则可控、动作有效、状态一致、点检可核验、过程可追溯”。