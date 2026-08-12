# MoldGuard Django 完整业务服务器参赛实施计划

- **计划状态**：`FINAL_FROZEN_FOR_COMPETITION`
- **系统状态**：`NOT_IMPLEMENTED`
- **版本**：V3.1
- **日期**：2026-08-12
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **建议实施分支**：`agent/django-full-workflow-v1`
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **权威性**：本文件是 Django 开发、测试、部署、平台联调和参赛验收的唯一实施基线
- **配套文档**：
  - `docs/architecture/2026-08-12-agent-platform-django-relationship.md`
  - `docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md`
  - `docs/business/2026-08-12-moldguard-business-scenarios.md`

---

## 1. 最终实施决策

本项目保持原参赛材料中的完整业务范围，并结合知识库 V0.1 细化为：

```text
MES/模拟数据接入
→ 自动或手动制定保养计划
→ 模具管理人员确认计划
→ 计划部安排送模、分厂完成送模
→ 创建保养工单
→ 候选人员匹配、主管确认派工
→ 点检知识随任务邮件下发
→ 开工、暂停、恢复、异常记录
→ 逐项点检并报完工
→ 主管验收
→ 不合格转修模 / 合格归档
→ 更新模具履历与下一周期基准
→ 工时、完成率、超时、负荷和停机分析
```

最终系统采用：

> **一个比赛智能体平台 + 一个 MoldGuard Django 外部虚拟业务服务器。**

- 智能体平台负责自然语言交互、工作流编排、知识库/RAG、LLM 内容生成和邮件发送；
- Django 负责结构化数据、规则治理、计划与工单事务、状态机、点检结果、验收、修模分流、工时和审计；
- 所有业务状态变化必须通过 Django 接口生效；
- 邮件由平台发送，但知识快照和发送结果必须回写 Django；
- 知识库正文不重复存入 Django，Django只保存知识版本、条目引用、内容哈希和本次使用快照。

---

## 2. 知识库审查结论

知识包包含流程、触发规则、注塑/钣金保养标准、22 条点检、78 条故障工时、储放安全、外部三级保养参考、元数据规则和冲突清单。

结构化 JSONL 共 353 条：

| 类型 | 数量 |
|---|---:|
| 保养标准 | 99 |
| 故障与工时 | 79 |
| 知识说明 | 31 |
| 触发与寿命规则 | 27 |
| 外部参考 | 27 |
| 点检标准 | 26 |
| 知识库实施规则 | 24 |
| 数据治理 | 17 |
| 业务流程 | 13 |
| 储放与安全 | 10 |

当前条目没有 `INTERNAL_CONFIRMED`。主要状态为：

- `INTERNAL_SOURCE`：253 条；
- `PROJECT_REQUIREMENT`：56 条；
- `EXTERNAL_REFERENCE`：27 条；
- `PENDING_CONFIRMATION`：17 条。

因此冻结以下规则治理原则：

1. 知识库可用于检索、解释、邮件和现场指导；
2. `INTERNAL_SOURCE` 不能自动视为现行正式规则；
3. `PENDING_CONFIRMATION` 不得驱动自动预警、派工、验收或结单；
4. `EXTERNAL_REFERENCE` 只作为补充，不得覆盖内部标准；
5. 比赛演示建立独立 `DEMO_RULESET_V1` 和知识条目使用白名单；
6. 生产环境只允许 `INTERNAL_CONFIRMED` 规则自动执行；
7. 所有来源权威标签保持原样，演示批准通过独立审批记录实现，不篡改来源属性。

---

## 3. 原参赛应用与最终实现映射

| 原应用 | 智能体平台职责 | Django 职责 |
|---|---|---|
| MoldGuard-Warn | 用户查询、预警报告、告警通知 | 模具数据、规则匹配、评分、预警和计划生成 |
| MoldGuard-Plan | 流程触发、主管确认、知识邮件 | 计划确认、送模、工单创建、候选匹配、派工写入 |
| MoldGuard-Track | 催办话术、异常分析、验收知识 | 状态机、时间线、点检、异常、验收、转修模和升级记录 |
| MoldGuard-Analyze | 自然语言分析、图表与管理说明 | 工时、完成率、超时、负荷、停机和履历数据 |
| MoldGuard-KB | 保存知识正文并执行检索 | 返回规则和检索上下文，保存知识目录版本和工单知识快照 |

---

## 4. 业务角色

| 角色 | Django 权限与职责 |
|---|---|
| `ADMIN` | 演示数据、规则审批、全部业务操作 |
| `MOLD_MANAGER` | 确认/关闭计划、确认送模、创建工单、查看候选、派工 |
| `PLANNER` | 维护送模时间和要求交模时间 |
| `BRANCH_OPERATOR` | 确认分厂送模 |
| `MAINTAINER` | 接单、开工、暂停、恢复、点检、报完工和提交异常 |
| `MOLD_SUPERVISOR` | 派工、验收、退回、转修模、取消和升级 |
| `ANALYST` | 查询统计，不执行状态写入 |
| `PLATFORM_SERVICE` | 代表智能体平台调用 API，但每次动作仍需具体 actor_id |

自然语言中的姓名和工号不是身份凭证。Django必须按 `actor_id` 查询本地操作人并校验角色。

---

## 5. 总体架构

```text
┌─────────────────────────────────────────────────────┐
│                   比赛智能体平台                     │
│ 对话 │ 工作流 │ 知识库/RAG │ LLM │ 主管确认 │ 邮件  │
└────────────────────────┬────────────────────────────┘
                         │ HTTPS + JSON
                         │ API Key + Request-ID + Idempotency-Key
                         ▼
┌─────────────────────────────────────────────────────┐
│               MoldGuard Django Server               │
│ 模具 │ 规则 │ 预警 │ 计划 │ 送模 │ 工单 │ 派工     │
│ 点检 │ 异常 │ 修模 │ 验收 │ 履历 │ 统计 │ 审计     │
└────────────────────────┬────────────────────────────┘
                         ▼
                   PostgreSQL 16
```

---

## 6. 技术基线

| 项目 | 最终选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS，锁定实际补丁版本 |
| API | Django REST Framework 3.16 系列 |
| 过滤 | django-filter |
| OpenAPI | drf-spectacular |
| 数据库 | PostgreSQL 16 |
| 测试 | pytest + pytest-django |
| 质量 | Ruff |
| 运行 | Gunicorn |
| 入口 | Nginx HTTPS |
| 部署 | Docker Compose |
| 时区 | Asia/Shanghai |
| Django 内部端口 | 18080 |
| 公网入口 | 443 |

V3.1 包含计划、工单、点检、验收等并发写入，正式参赛部署不使用 SQLite。邮件和定时调度由平台完成，默认不部署 Redis、Celery、Mailpit 或 SMTP。

---

## 7. Django 工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── config/
├── apps/
│   ├── common/              # 响应、异常、认证、权限、幂等、request_id
│   ├── accounts/            # 操作人、角色、平台客户端
│   ├── molds/               # 模具台账、寿命、闲置和履历
│   ├── standards/           # 规则、等级、触发点、技能要求、审批
│   ├── alerts/              # 保养/寿命/闲置/日常检查提醒
│   ├── plans/               # 保养计划、确认、关闭和送模
│   ├── staff/               # 人员、技能、负荷和候选匹配
│   ├── workorders/          # 工单、派工、状态、点检、验收和转修模
│   ├── knowledge/           # 目录版本、知识快照和条目引用
│   ├── faults/              # 故障工时标准、候选匹配和修模分流
│   ├── notifications/       # 邮件发送结果回写
│   ├── analytics/           # 工时、完成率、超时、负荷和停机
│   └── audit/               # 审计和幂等记录
├── data/demo/
├── docs/
├── tests/
│   ├── unit/
│   ├── api/
│   ├── contract/
│   ├── integration/
│   └── state_machine/
├── scripts/
├── nginx/
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 8. 核心数据模型

## 8.1 Mold：模具台账

基础字段：

```text
mold_id、mold_name、mold_type、mold_level、mold_category
cavity_count、current_count、last_maintenance_count、last_maintenance_time
primary_location、secondary_location、production_line、status
data_source、created_at、updated_at
```

知识库对齐后增加：

```text
mold_code_prefix
part_name
model_code
development_tonnage
cavity_layout
material_tags
feature_tags
design_life_count
life_extension_count
last_production_at
production_count_updated_at
idle_since
has_backup_mold
```

用途：吨位规则、类别规则、LC 编码、零件级标准、玻纤/磨砂/薄细特征、寿命提醒、闲置管理和知识过滤。

扫描范围：

- `IN_PRODUCTION`：参与自动保养扫描；
- `IN_STORAGE`：可评估，但默认不自动建保养工单；
- `UNDER_REPAIR`：不自动建单；
- `DISABLED`：不参与；
- 两年未更新产量时，可按已批准规则禁用自动触发。

## 8.2 MaintenanceScheme 与 MaintenanceLevel

内部等级体系必须分开保存：

- 注塑：基础保养、全面精度维护、零件级二保/三保；
- 钣金：一保、二保、三保；
- 外部参考：A/B/C，只能标记 `EXTERNAL_REFERENCE`，不自动映射。

字段：

```text
scheme_code、scheme_name、mold_type、level_code、level_name
is_internal、is_active、description
```

## 8.3 MaintenanceRule

替代单一阈值表，至少包含：

```text
rule_id
rule_family
trigger_type
mold_type
mold_category
mold_code_prefix
exact_mold_id
part_name
tonnage_min
tonnage_max
maintenance_level
count_basis
count_threshold
time_threshold_days
standard_hours
reset_event
knowledge_profile_code
source_file
source_location
authority
approval_status
rule_version
effective_from
effective_to
priority
is_active
```

枚举：

```text
rule_family:
  MAINTENANCE_REMINDER
  LIFE_REMINDER
  DAILY_INSPECTION
  IDLE_MANAGEMENT
  RESET_RULE

trigger_type:
  COUNT
  TIME
  EVENT
  MANUAL
  COMPOSITE

approval_status:
  DRAFT
  PENDING_CONFIRMATION
  DEMO_APPROVED
  INTERNAL_CONFIRMED
  EXTERNAL_REFERENCE
  DISABLED
```

`MaintenanceTriggerPoint` 保存第一次/第二次提醒、二保/三保等多个触发点，避免把源表多个阈值压缩成一个字段。

`RuleConflict` 保存冲突编号、涉及规则、发现、处理建议和解决状态。

`RuleApprovalRecord` 保存批准人、环境、批准时间和依据。来源 authority 不可被审批记录覆盖。

## 8.4 AlertPolicy 与健康评分

健康评分是参赛展示层，不替代规则选择。

`DEMO_HEALTH_V1`：

```text
usage_ratio <= 0.90:
  score = 100 - (usage_ratio / 0.90) × 20

0.90 < usage_ratio < 1.00:
  score = 80 - ((usage_ratio - 0.90) / 0.10) × 25

usage_ratio >= 1.00:
  score = max(0, 55 - (usage_ratio - 1.00) × 100)
```

主演示数据 93.25% 得 71.875，展示 72 分。

该公式仅用于 `DEMO_RULESET_V1`，必须标记“非企业正式制度”。正式触发依据仍为已批准 `rule_id`。

## 8.5 MoldAlert

字段：

```text
alert_id
alert_type
mold
rule
rule_version
evaluated_at
count_snapshot
time_snapshot
trigger_basis
health_score
alert_level
status
recommended_priority
recommended_deadline
scan_batch_id
```

`alert_type`：

```text
MAINTENANCE_DUE
LIFE_REMINDER
IDLE_REVIEW
DAILY_INSPECTION
MANUAL_FINDING
```

保养提醒、寿命提醒和闲置评估禁止混用。

## 8.6 MaintenancePlan

工单前增加计划层：

```text
plan_id
source_type              # AUTO / MANUAL
alert
mold
requested_level
matched_rule
status
estimated_hours
planned_delivery_at
required_return_at
confirmed_by
confirmed_at
close_count
created_at
```

附属模型：

- `PlanCloseAttempt`：关闭人员、时间、原因、模次、规则版本和证据；
- `MoldDeliverySchedule`：计划送模、要求交模、实际送达、交接人员和状态。

两次关闭机会配置化。知识库未说明统计范围，比赛版在 `DEMO_RULESET_V1` 中明确口径并记录为演示规则。

## 8.7 Employee、Skill、StandardSkillRequirement

人员字段：

```text
employee_id、employee_name、email、team、production_line
skill_level、current_load、on_duty、available、is_active
```

标准技能要求使用关联表，不从知识正文临时猜测。

## 8.8 WorkOrder

字段：

```text
work_order_id
plan
mold
rule_snapshot
standard_snapshot
maintenance_level
maintenance_items_snapshot
standard_hours
priority
required_finish_at
status
assigned_employee
created_by
assigned_at
started_at
reported_at
accepted_at
dispatch_to_complete_duration
waiting_to_start_duration
actual_execution_duration
paused_duration
hours_variance
completion_summary
acceptance_result
```

附属模型：

```text
WorkOrderItem
DispatchRecord
WorkOrderEvent
PauseSegment
WorkOrderException
EscalationRecord
AcceptanceRecord
MaintenanceRecord
AuditLog
IdempotencyRecord
```

## 8.9 KnowledgeCatalogRelease 与 KnowledgeSnapshot

`KnowledgeCatalogRelease`：

```text
catalog_version
package_filename
package_sha256
entry_count
release_status
imported_at
```

`KnowledgeSnapshot` 与 `KnowledgeSnapshotItem` 保存：

```text
work_order
catalog_version
knowledge_id
title
knowledge_type
source_file
source_location
authority
approval_status
rule_version
content_hash
usage_type
retrieved_at
approved_override_by
```

Django不保存向量库全文，只保存工单实际使用的可追溯条目。

## 8.10 InspectionTemplateSnapshot 与 InspectionResult

知识库有注塑 11 条、钣金 11 条点检标准。

每项保存：

```text
knowledge_id
item
acceptance_criteria
method
period
result            # PASS / FAIL / NOT_APPLICABLE
abnormal_note
not_applicable_reason
photo_refs
performed_by
performed_at
```

约束：

- 未提交全部适用项不得报完工；
- `NOT_APPLICABLE` 必须人工选择并填写原因；
- `FAIL` 必须填写异常；
- 关键项失败进入转修模，不得直接完成。

## 8.11 FaultStandard 与 RepairReferral

导入 78 条故障工时标准：

```text
fault_standard_id
mold_type
fault_type
fault_description
standard_repair_hours
source_file
source_id
authority
approval_status
```

匹配必须同时考虑模具类型、故障类型和描述。相近词只返回候选，不自动合并；未命中不得默认 5 小时。

`RepairReferral` 保存失败点检、故障候选、人员确认结果、维修工时和后续复位状态。

---

## 9. 规则匹配与治理

匹配顺序：

1. `exact_mold_id + maintenance_level`；
2. `part_name + model_code + cavity_layout`；
3. `mold_type + mold_category + tonnage range + maintenance_level`；
4. `mold_code_prefix + category + maintenance_level`；
5. 允许明确配置的通用回退；
6. 同优先级多条命中返回 `RULE_AMBIGUOUS`；
7. 未命中返回 `RULE_NOT_FOUND`；
8. 命中未批准规则返回 `RULE_NOT_APPROVED`；
9. 任何回退必须在响应中返回 `match_strategy`。

生效条件：

```text
effective_from <= evaluated_at
且 effective_to 为空或 >= evaluated_at
```

自动执行许可：

```text
DEMO 环境：DEMO_APPROVED / INTERNAL_CONFIRMED
PRODUCTION 环境：INTERNAL_CONFIRMED
```

PENDING、INTERNAL_SOURCE、EXTERNAL_REFERENCE 可展示但不能自动驱动状态变化。

---

## 10. 状态机

## 10.1 保养计划状态

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

允许流程：

```text
DRAFT → PENDING_CONFIRMATION
PENDING_CONFIRMATION → CONFIRMED / CLOSED
CONFIRMED → PENDING_DELIVERY
PENDING_DELIVERY → DELIVERED
DELIVERED → WORK_ORDER_CREATED
```

## 10.2 工单状态

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

允许流程：

```text
PENDING_ASSIGNMENT → ASSIGNED
ASSIGNED → IN_PROGRESS
IN_PROGRESS → PAUSED → IN_PROGRESS
IN_PROGRESS → PENDING_INSPECTION
PENDING_INSPECTION → PENDING_ACCEPTANCE
PENDING_INSPECTION → TRANSFERRED_TO_REPAIR
PENDING_ACCEPTANCE → COMPLETED
PENDING_ACCEPTANCE → IN_PROGRESS
PENDING_ACCEPTANCE → TRANSFERRED_TO_REPAIR
```

约束：

- 计划未确认不得送模；
- 未送模不得开始需下机拆模的任务；
- 未派工不得开工；
- 未完成点检不得报完工；
- 点检失败不得直接验收完成；
- 已完成工单不得再次派工或修改关键结果；
- 所有状态变化写 `WorkOrderEvent` 和 `AuditLog`。

---

## 11. 候选人员与派工

候选资格：

```text
is_active=true
on_duty=true
available=true
current_load < 0.80
skill_match_ratio >= 0.80
email 已配置
```

排序：

高/紧急任务：

```text
eligible → 同产线 → 技能匹配率 → 技师等级 → 负荷 → 员工编号
```

普通任务：

```text
eligible → 同产线 → 技能匹配率 → 负荷 → 技师等级 → 员工编号
```

平台展示候选并由主管确认；Django在写入派工前再次校验资格。

---

## 12. 知识检索、知识包和邮件

检索顺序：

1. Django返回模具事实、已批准 `rule_id`、规则版本和 `knowledge_profile_code`；
2. 平台优先精确过滤规则/画像；
3. 按模具类型和保养等级检索保养项目和点检；
4. 补充安全、储放、完工和验收要求；
5. 有异常时查询故障工时候选；
6. 命中待确认条目时要求主管确认；
7. 平台回写知识快照；
8. 平台发送邮件并回写发送结果。

知识包至少包含：

```text
work_order_id
mold_id
rule_id
rule_authority
rule_version
trigger_basis
maintenance_items
inspection_items
safety_notes
completion_requirements
source_documents
knowledge_snapshot_version
```

邮件必须包含：工单信息、触发依据、保养项目、点检清单、安全要求、要求交模时间、完工判定、不合格转修模说明和知识版本。

`EXTERNAL_REFERENCE` 不得作为强制验收标准。`PENDING_CONFIRMATION` 条目需主管显式批准后才能进入正式邮件。

---

## 13. 工时与复位

保存：

```text
dispatch_to_complete_duration = 报工 - 派工
waiting_to_start_duration     = 开工 - 派工
actual_execution_duration     = 报工 - 开工 - 暂停时长
hours_variance                = 实际执行工时 - 标准工时
```

周期复位只在已批准 reset rule 满足时执行。默认至少要求：

- 保养或修模事件已完成；
- 点检已提交；
- 主管验收通过；
- 系统生成 MaintenanceRecord；
- 保存当前模次快照。

修模、换镶件和上传记录是否自动复位，以规则版本为准，不能硬编码。

---

## 14. API 契约

通用请求头：

```http
X-API-Key: <secret>
X-Request-ID: <optional>
Idempotency-Key: <required-for-write-actions>
Accept: application/json
```

统一成功：

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {},
  "meta": {
    "contract_version": "3.1",
    "source_type": "DEMO",
    "knowledge_catalog_version": "kb-v0.1"
  },
  "request_id": "req-..."
}
```

统一错误：

```json
{
  "code": "RULE_NOT_APPROVED",
  "message": "命中的规则尚未获准用于自动业务",
  "data": null,
  "errors": [],
  "request_id": "req-..."
}
```

---

## 15. 最终 API 清单

### 15.1 服务与元数据

```http
GET /api/v1/health
GET /api/v1/meta
GET /api/v1/knowledge-catalog/releases/current
```

### 15.2 模具、规则与标准

```http
GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/{mold_id}/life-status
GET /api/v1/molds/due
GET /api/v1/rules
GET /api/v1/rules/{rule_id}
GET /api/v1/rules/match
```

### 15.3 预警

```http
POST /api/v1/alerts/scan
GET  /api/v1/alerts
GET  /api/v1/alerts/{alert_id}
POST /api/v1/alerts/{alert_id}/acknowledge
```

### 15.4 保养计划与送模

```http
POST /api/v1/maintenance-plans
GET  /api/v1/maintenance-plans
GET  /api/v1/maintenance-plans/{plan_id}
POST /api/v1/maintenance-plans/{plan_id}/confirm
POST /api/v1/maintenance-plans/{plan_id}/close
POST /api/v1/maintenance-plans/{plan_id}/schedule-delivery
POST /api/v1/maintenance-plans/{plan_id}/mark-delivered
POST /api/v1/maintenance-plans/{plan_id}/create-work-order
```

### 15.5 人员与派工

```http
GET  /api/v1/staff
GET  /api/v1/staff/{employee_id}
GET  /api/v1/work-orders/{work_order_id}/candidates
POST /api/v1/work-orders/{work_order_id}/assign
```

### 15.6 工单执行

```http
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{work_order_id}
GET  /api/v1/work-orders/{work_order_id}/timeline
POST /api/v1/work-orders/{work_order_id}/start
POST /api/v1/work-orders/{work_order_id}/pause
POST /api/v1/work-orders/{work_order_id}/resume
POST /api/v1/work-orders/{work_order_id}/submit-for-inspection
POST /api/v1/work-orders/{work_order_id}/cancel
```

### 15.7 知识与点检

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge-snapshot
POST /api/v1/work-orders/{work_order_id}/inspection-template
GET  /api/v1/work-orders/{work_order_id}/inspection-template
POST /api/v1/work-orders/{work_order_id}/inspection-results
POST /api/v1/work-orders/{work_order_id}/report-complete
```

### 15.8 验收与修模

```http
POST /api/v1/work-orders/{work_order_id}/accept
POST /api/v1/work-orders/{work_order_id}/reject
POST /api/v1/work-orders/{work_order_id}/transfer-to-repair
GET  /api/v1/fault-standards/search
POST /api/v1/repair-referrals/{referral_id}/confirm-fault
POST /api/v1/repair-referrals/{referral_id}/complete
```

### 15.9 邮件、异常与升级

```http
POST /api/v1/work-orders/{work_order_id}/notifications
GET  /api/v1/work-orders/{work_order_id}/notifications
POST /api/v1/work-orders/{work_order_id}/exceptions
POST /api/v1/work-orders/{work_order_id}/escalations
GET  /api/v1/work-orders/overdue
POST /api/v1/work-orders/scan-overdue
```

### 15.10 分析

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
GET /api/v1/analytics/overdue-orders
GET /api/v1/analytics/mold-history
GET /api/v1/analytics/staff-load
GET /api/v1/analytics/downtime
GET /api/v1/analytics/repair-hours
```

---

## 16. 关键接口行为

### 16.1 扫描预警

- 只使用当前环境允许的已批准规则；
- 记录规则匹配策略和计算快照；
- 同一扫描批次幂等；
- 未批准或冲突规则返回明确状态，不静默选择。

### 16.2 计划关闭

- 记录关闭次数和证据；
- 超过配置次数时拒绝或强制升级；
- 不能通过删除计划绕过关闭次数。

### 16.3 创建工单

- 必须来自已确认并已送模的计划，除非任务类型明确允许在线日常保养；
- 复制模具、规则、标准和工时快照；
- 防止同模具、同等级重复未关闭工单；
- 返回现有工单编号而不是重复创建。

### 16.4 点检与报完工

- 工单必须存在点检模板快照；
- 所有适用项必须提交；
- FAIL 或关键异常进入转修模；
- 报完工只进入待验收，不直接完成。

### 16.5 验收完成

同一事务中：

1. 工单设为 `COMPLETED`；
2. 创建 MaintenanceRecord；
3. 更新模具保养基准；
4. 根据复位规则计算下一提醒；
5. 关闭关联预警和计划；
6. 更新人员负荷；
7. 写入事件和审计。

---

## 17. 催办规则

参赛演示配置：

| 场景 | 规则 |
|---|---|
| 红色预警未处理 | 2 小时升级主管 |
| 黄色计划未确认 | 24 小时提醒 |
| 已确认未送模 | 超过计划送模时间提醒计划部/分厂 |
| 已送模未派工 | 24 小时提醒，3 天升级 |
| 执行超时 | 超标准工时 50% 记录异常并升级 |
| 强制升级 | 超标准工时 100% |
| 暂停过久 | 超 4 小时或跨班次 |
| 待点检 | 任务执行结束后未提交点检 |
| 待验收 | 24 小时未验收 |

---

## 18. 演示数据

至少准备：

- 12 套模具；
- 10 条演示规则，覆盖注塑/钣金、模次、时间、寿命和手动触发；
- 8 名员工和 10 个技能；
- 12 条预警；
- 8 条计划；
- 10 张工单；
- 22 条点检标准的知识引用；
- 20 条历史保养记录；
- 知识快照、邮件记录、异常、转修模和验收退回场景。

固定主演示模具：

```text
MOLD-2024-0891
前壳体注塑模
A 类精密注塑模
4 腔
当前累计模次 386500
上次保养模次 200000
本周期运行 186500
演示阈值 200000
使用率 93.25%
健康评分 72
黄色预警
标准工时 8 小时
```

该阈值和健康公式标记为 `DEMO_APPROVED`，不宣称为企业正式规则。

管理命令：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
python manage.py import_fault_standards
python manage.py import_knowledge_catalog_manifest
python manage.py backup_demo_data
```

---

## 19. 安全、权限、事务与审计

- 平台使用 `X-API-Key`；
- 写操作必须带 `Idempotency-Key`；
- API Key、数据库密码和 SECRET_KEY 只从环境变量读取；
- 每次写入传 actor_id，由 Django校验角色；
- 状态变化使用事务和行锁；
- 重试使用同一幂等键并返回原结果；
- 日志记录 request_id、actor_id、对象、状态码和耗时；
- 不记录 API Key、密码或完整邮箱；
- 邮箱日志脱敏；
- Admin独立路径、强密码、限制来源 IP；
- `DEBUG=False`、HTTPS、HSTS、正确 ALLOWED_HOSTS 和代理配置；
- 普通业务接口不得删除审计日志、状态事件或知识快照。

---

## 20. 部署

Docker Compose：

```yaml
services:
  web:      # Django + Gunicorn，内部 18080
  db:       # PostgreSQL 16
  nginx:    # 80/443
```

服务器建议：Ubuntu LTS、2 核、4 GB、40 GB、公网 IP、主域名和备用域名，两个域名均有有效证书。

不部署 Redis、Celery、Mailpit、SMTP 和向量数据库。

---

## 21. 测试与质量门禁

必测：

- 规则审批、来源权威和环境限制；
- 多规则匹配、冲突、回退和未批准；
- 吨位、类别、编码、精确模具和零件级匹配；
- 保养提醒、寿命提醒和闲置提醒分离；
- 主演示 93.25%、72 分和黄色；
- 自动/手动计划；
- 两次关闭与超限；
- 送模状态；
- 重复工单防护；
- 候选资格和派工重校验；
- 知识快照权威状态和内容哈希；
- 22 条点检模板、PASS/FAIL/NA约束；
- 点检失败转修模；
- 78 条故障精确/候选匹配且不默认 5 小时；
- 状态机全部合法与非法流转；
- 工时、暂停和复位；
- 验收后履历和下一基准；
- 邮件失败不回滚派工；
- 权限、幂等、并发、错误响应和 OpenAPI。

自动化：

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy --settings=config.settings.production
pytest
python manage.py spectacular --file docs/contracts/openapi.yaml --validate
python manage.py verify_demo_data
docker compose build
python scripts/smoke_test.py
```

Phase 1 创建 GitHub Actions CI。

---

## 22. 开发阶段与 Stop Gate

### Gate -1：平台最小链路验证

验证 GET、POST、动态 actor、嵌套 JSON、知识过滤、动态邮箱、邮件发送、知识快照和邮件回写。

### Phase 0：规则与知识合同冻结

交付：规则字典、等级体系、审批状态、知识包 schema、业务场景、状态机和 API 合同。

### Phase 1：工程骨架、认证、幂等与 CI

### Phase 2：主数据、规则治理、Admin 和演示导入

### Phase 3：规则匹配、预警和健康评分

### Phase 4：计划确认、关闭和送模

### Phase 5：工单、候选人员和派工

### Phase 6：知识快照、邮件回写和点检模板

### Phase 7：执行、点检、报完工、验收和转修模

### Phase 8：履历、复位、异常、工时和分析

### Phase 9：部署、安全、备份和恢复

### Phase 10：比赛平台完整联调

连续完成 3 次：

```text
扫描预警
→ 计划确认
→ 送模
→ 创建工单
→ 候选与派工
→ 知识检索和邮件
→ 开工/暂停/点检/报完工
→ 验收或转修模
→ 履历和统计
```

---

## 23. P0 与 P1

### P0 参赛必需

- 自动/手动计划；
- 规则治理和主演示规则；
- 计划确认、关闭和送模；
- 工单、候选、派工；
- 知识随单、邮件回写；
- 开工、暂停、点检、报完工和验收；
- 点检失败转修模；
- 履历、实际工时、完成率和超时；
- Admin、OpenAPI、认证、幂等、测试和部署。

### P1

- 生产中日常保养；
- 模具调动、入库和恢复生产；
- 完整寿命提醒；
- 闲置模具分类和报废评估；
- 复杂修模业务；
- 备件、成本、同比、环比、预测和导出；
- 真实 MES/ERP 集成。

---

## 24. 参赛演示脚本

1. 平台调用 `/alerts/scan`；
2. 展示规则来源、93.25%、72 分和黄色预警；
3. 自动生成待确认计划；
4. 主管确认计划并模拟送模；
5. 创建工单，Django返回候选人员；
6. 主管确认派工；
7. 平台按 rule_id/knowledge_profile_code 检索知识；
8. 回写知识快照，发送含点检、安全和验收要求的邮件；
9. 回写邮件结果；
10. 保养人员开工，演示暂停和恢复；
11. 提交逐项点检；
12. 主路径全部合格，报完工并验收；
13. 异常路径展示一个 FAIL 项转修模；
14. Django更新履历和下一周期基准；
15. 平台查询工时、完成率和超时并生成分析。

---

## 25. Definition of Done

系统只有同时满足以下条件才可标记 `READY_FOR_COMPETITION`：

- 原参赛材料的完整闭环有真实模拟状态；
- 353 条知识目录版本可追溯；
- 未确认和外部参考条目不会自动驱动业务；
- 演示规则和正式规则边界清楚；
- 计划确认、关闭、送模、派工、点检、验收和转修模状态正确；
- 邮件包含任务与适用知识，快照和发送结果可追溯；
- 点检结果逐项保存，NA与FAIL约束生效；
- 修模、换件和记录上传不在未批准规则下自动复位；
- 候选人员可解释，派工时重新校验；
- 工时和统计可由明细复算；
- 所有写接口有权限、幂等、事务和审计；
- 所有 DEMO 数据和规则显式标识；
- README、计划、业务场景、关系说明、OpenAPI和代码一致；
- CI、测试、Docker、HTTPS和连续三次平台演示通过。

---

## 26. 尚待业务确认但不阻塞演示的事项

1. 注塑吨位规则、类别规则和零件明细的正式优先级；
2. 模次与时间条件的组合关系；
3. 注塑内部等级体系；
4. 钣金边板类 6 万与 40 万的适用边界；
5. LC109 编码；
6. 注塑明细缺失模具编码和异常触发值；
7. 两次关闭机会的统计范围；
8. 哪些事件允许周期复位；
9. 点检图片转写确认；
10. 钣金空白工时是否继承；
11. 闲置模具公式；
12. 标准工时按模具、零件、等级或故障的正式口径。

比赛通过 `DEMO_RULESET_V1` 和知识白名单运行，不得声称上述待确认项已经成为企业正式制度。

---

## 27. 最终冻结矩阵

| 决策项 | 结论 |
|---|---|
| 保持原参赛完整材料 | 是 |
| Django 是否只读 | 否 |
| Django 是否管理保养计划 | 是 |
| Django 是否管理送模 | 是，参赛可简化操作 |
| Django 是否保存工单与派工 | 是 |
| Django 是否保存点检结果 | 是 |
| 点检失败是否转修模 | 是 |
| Django 是否记录报工和验收 | 是 |
| Django 是否发送邮件 | 否 |
| 邮件由谁发送 | 智能体平台 |
| Django 是否记录邮件结果 | 是 |
| 知识库正文 | 智能体平台 |
| Django 是否保存知识快照 | 是 |
| 是否直接导入 JSONL 为业务规则 | 否 |
| 规则自动执行条件 | 已批准且环境允许 |
| 当前知识库是否有 INTERNAL_CONFIRMED | 否 |
| 参赛规则 | DEMO_RULESET_V1 / DEMO_APPROVED |
| 健康评分 | DEMO_HEALTH_V1，仅参赛展示 |
| 保养、寿命、闲置提醒是否分离 | 是 |
| 数据库 | PostgreSQL 16 |
| Redis/Celery | 默认不使用 |
| 部署 | Docker Compose + Nginx + Gunicorn |
| 权威计划 | 本文件 V3.1 |

---

## 28. 最终结论

MoldGuard Django Server 的参赛定位为：

> **模具保养智能体的外部虚拟业务服务器、版本化规则引擎、计划与工单状态中心、点检验收记录中心和统计事实源。**

智能体平台负责“理解、检索、生成、编排和通知”，Django负责“数据、规则、事务、状态、点检、验收和审计”。知识库 V0.1 为业务流程、操作知识、22 条点检、78 条故障工时和安全储放提供了充分素材；其规则冲突和未确认状态由 Django 的审批、版本、演示规则集和知识快照机制隔离，确保比赛可稳定演示且不把未确认资料冒充企业正式制度。