# MoldGuard Django 完整业务服务器参赛实施计划

- **计划状态**：`FINAL_FROZEN`
- **系统状态**：`NOT_IMPLEMENTED`
- **版本**：V3.0
- **日期**：2026-08-12
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **建议实施分支**：`agent/django-full-workflow-v1`
- **权威性**：本文件是 Django 服务器后续开发、测试、部署、智能体平台联调和参赛验收的唯一范围基线
- **替代关系**：本文件替代 V2.0“只读查询 API”方案；早期只读方案只作为历史记录，不再作为开发依据

---

## 1. 最终实施决策

本项目保持原参赛材料中的完整业务范围：

```text
模具健康监测
→ 保养预警
→ 自动生成保养工单
→ 智能候选人员匹配
→ 主管确认派工
→ 点检知识随任务邮件下发
→ 开工、暂停、恢复、报工
→ 主管验收
→ 工单归档与模具履历更新
→ 工时、完成率、超时和人员负荷分析
```

最终系统采用：

> **一个比赛智能体平台 + 一个 MoldGuard Django 外部虚拟业务服务器。**

两者不是重复建设，也不是彼此替代：

- **智能体平台**负责自然语言交互、流程编排、知识库检索、LLM 内容生成和邮件发送；
- **Django**负责结构化业务数据、确定性规则、业务事务、工单状态机、过程记录和统计口径；
- 所有会改变业务状态的动作，必须由智能体平台调用 Django 接口，并以 Django 返回结果为最终事实；
- 邮件由智能体平台发送，但发送结果必须回写 Django，保证全流程可追溯。

---

## 2. 原参赛应用与最终实现映射

| 原应用 | 原职责 | 智能体平台职责 | Django 职责 |
|---|---|---|---|
| MoldGuard-Warn | 模具健康监测与预警 | 接收用户查询、生成预警报告、发送告警 | 查询模具、匹配标准、计算健康评分和预警、保存预警记录 |
| MoldGuard-Plan | 自动工单与派工 | 触发流程、展示候选人、主管确认、发送派工邮件 | 创建工单、返回候选人、校验并保存最终派工 |
| MoldGuard-Track | 过程追踪与异常升级 | 生成催办、异常分析和验收检查项 | 状态机、时间线、暂停、异常、报工、验收、升级记录 |
| MoldGuard-Analyze | 工时统计与决策分析 | 理解自然语言分析需求、生成结论和图表说明 | 提供工时、完成率、超时、负荷和履历统计数据 |
| MoldGuard-KB | 模具保养知识库 | 保存点检标准、操作指导书、案例和验收要求，执行 RAG | 返回知识画像编码和过滤标签，保存本次下发知识快照 |

---

## 3. 最终职责边界

### 3.1 Django 最终负责

- 模具台账及当前累计模次；
- 上次保养模次、时间和模具履历；
- 保养标准、标准版本、保养等级和标准工时；
- 参赛健康评分、红黄绿预警和待保养清单；
- 预警扫描、预警记录、确认和处理状态；
- 模拟人员、班组、技能、技师等级、负荷、在岗状态和邮箱；
- 候选人员资格计算、排序和原因说明；
- 保养工单创建、去重、派工和状态机；
- 开工、暂停、恢复、异常、报工、验收、退回和取消；
- 知识下发快照和邮件发送结果记录；
- 工单时间线、异常升级和审计日志；
- 标准工时、实际执行工时、等待时长、暂停时长和工时偏差；
- 完成率、超时工单、人员负荷、模具历史和产线停机时长等结构化统计；
- Django Admin、演示数据初始化、重置、验证和备份；
- OpenAPI、API Key、幂等、权限、日志、测试和部署。

### 3.2 智能体平台最终负责

- 用户自然语言交互；
- Chatflow、Workflow、Agent 流程编排；
- 定时或手动触发 Django 预警扫描；
- 点检要求、操作指导书、故障案例、工时定额、备件手册等知识库；
- RAG 检索和来源引用；
- LLM 生成预警报告、任务说明、催办话术、异常分析、验收检查项和管理建议；
- 展示 Django 返回的候选人员，由主管完成最终确认；
- 组装任务与点检知识；
- 生成并发送邮件；
- 将知识快照和邮件发送结果回写 Django；
- 根据 Django 的统计数据生成可视化或汇报内容。

### 3.3 Django 明确不负责

- 自建 Embedding、Rerank 或向量数据库；
- 保存比赛平台完整知识库正文；
- 调用大模型；
- 自行生成自然语言报告；
- SMTP、Mailpit、邮件模板渲染和邮件发送；
- 企业微信、钉钉或短信发送；
- 独立 Vue、React 前端；
- 在未确认的情况下由大模型直接决定最终派工人员；
- 对真实 MES、ERP 或排产系统执行生产写入。

---

## 4. 总体业务闭环

```text
用户或每日 08:00 工作流触发
        ↓
平台调用 Django 扫描模具
        ↓
Django 保存预警记录并返回黄色/红色清单
        ↓
平台生成预警报告
        ↓
平台请求 Django 创建保养工单
        ↓
Django 返回候选人员及匹配依据
        ↓
主管在平台确认最终人员
        ↓
平台调用 Django 保存派工结果
        ↓
平台按工单知识画像检索点检要求
        ↓
平台回写知识快照并发送邮件
        ↓
平台回写邮件发送结果
        ↓
保养人员通过平台开工/暂停/恢复/报工
        ↓
Django执行状态校验并记录时间线
        ↓
主管通过平台验收或退回
        ↓
Django归档工单并更新模具履历
        ↓
平台查询 Django 统计接口并生成分析结论
```

---

## 5. 技术基线

| 项目 | 最终选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS，锁定实际安全补丁版本 |
| API 框架 | Django REST Framework 3.16 系列 |
| 查询过滤 | django-filter |
| API 文档 | drf-spectacular |
| 数据库 | PostgreSQL 16 |
| 测试 | pytest + pytest-django |
| 代码质量 | Ruff |
| 应用服务器 | Gunicorn |
| 反向代理 | Nginx |
| 部署 | Docker Compose |
| 时区 | Asia/Shanghai |
| Django 内部端口 | 18080 |
| 公网入口 | HTTPS 443 |

### 5.1 为什么完整业务版改用 PostgreSQL

V3.0 已恢复工单创建、状态流转、邮件回写、报工和验收等并发写入能力。SQLite 不再作为参赛正式部署数据库，避免多请求写入时出现锁冲突、备份不一致和状态更新风险。

SQLite 只允许用于本地单元测试或轻量开发；参赛部署使用 PostgreSQL。

### 5.2 不使用 Redis 和 Celery

邮件和定时流程由比赛平台实现，因此 V3.0 默认仍不部署 Redis 和 Celery。

超时扫描采用以下方式之一：

1. 比赛平台每 30 分钟调用 Django 超时扫描接口；
2. Linux cron 调用 Django management command。

优先使用比赛平台，避免重复调度。

---

## 6. Django 工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── config/
│   ├── urls.py
│   ├── wsgi.py
│   └── settings/
│       ├── base.py
│       ├── development.py
│       └── production.py
├── apps/
│   ├── common/             # 响应、异常、认证、权限、幂等、请求ID
│   ├── accounts/           # 模拟操作人、角色和平台客户端
│   ├── molds/              # 模具台账和履历
│   ├── standards/          # 保养标准、技能要求和预警策略
│   ├── alerts/             # 预警扫描和预警记录
│   ├── staff/              # 人员、技能、负荷和候选匹配
│   ├── workorders/         # 工单、派工、状态机、异常和验收
│   ├── notifications/      # 知识快照和邮件结果回写
│   ├── analytics/          # 工时、完成率、超时和人员负荷
│   └── audit/              # 审计日志和幂等记录
├── data/demo/
├── docs/
│   ├── plans/
│   ├── architecture/
│   ├── contracts/
│   ├── examples/
│   └── operations/
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

## 7. 核心数据模型

### 7.1 Mold：模具台账

| 字段 | 类型/说明 |
|---|---|
| `mold_id` | CharField，唯一 |
| `mold_name` | CharField |
| `mold_type` | Choice/CharField |
| `mold_level` | CharField |
| `mold_category` | CharField，可空 |
| `cavity_count` | PositiveIntegerField，可空 |
| `current_count` | PositiveBigIntegerField |
| `last_maintenance_count` | PositiveBigIntegerField |
| `last_maintenance_time` | DateTimeField，可空但必须显式报告缺失 |
| `primary_location` | CharField |
| `secondary_location` | CharField |
| `production_line` | CharField |
| `status` | `IN_PRODUCTION`、`IN_STORAGE`、`UNDER_REPAIR`、`DISABLED` |
| `data_source` | 参赛版固定为 `DEMO` |
| `created_at/updated_at` | 时间戳 |

默认待保养扫描范围：

- `IN_PRODUCTION`：参与；
- `IN_STORAGE`：可计算状态，但默认不进入自动建单清单；
- `UNDER_REPAIR`：不进入自动建单清单；
- `DISABLED`：不进入。

### 7.2 MaintenanceStandard：保养标准

| 字段 | 说明 |
|---|---|
| `standard_id` | 唯一编号 |
| `mold_type` | 模具类型 |
| `mold_level` | 模具等级 |
| `mold_category` | 可空，作为回退标准 |
| `maintenance_level_code` | `LEVEL_1`、`LEVEL_2`、`LEVEL_3` |
| `maintenance_level_name` | 一级/二级/三级保养 |
| `maintenance_threshold` | PositiveBigIntegerField |
| `maintenance_days` | 可选时间周期 |
| `standard_hours` | DecimalField(7,2) |
| `knowledge_profile_code` | 精确知识画像编码 |
| `knowledge_tags` | JSONField |
| `version` | 标准版本 |
| `effective_from/effective_to` | 生效区间 |
| `is_active` | 是否活动 |

### 7.3 StandardSkillRequirement：标准技能要求

| 字段 | 说明 |
|---|---|
| `standard` | 关联保养标准 |
| `skill` | 关联技能 |
| `is_required` | 是否必需 |

V1 不使用技能熟练度权重，只判断员工是否具备有效技能，避免无业务依据的复杂评分。

### 7.4 AlertPolicy：参赛预警策略

| 字段 | 示例 |
|---|---|
| `policy_code` | `DEMO_HEALTH_V1` |
| `version` | `V1.0` |
| `yellow_deadline_days` | `7` |
| `red_deadline_hours` | `4` |
| `is_active` | `true` |
| `description` | 参赛演示规则，非企业正式制度 |

### 7.5 MoldAlert：模具预警记录

保存：

- 预警编号；
- 模具；
- 匹配标准和规则版本；
- 评估时间；
- 当前模次、上次保养模次、本周期运行模次；
- 使用率、健康评分和预警等级；
- 推荐优先级和截止时间；
- 状态：`OPEN`、`ACKNOWLEDGED`、`WORK_ORDER_CREATED`、`RESOLVED`、`CANCELLED`；
- 幂等扫描批次号。

### 7.6 Employee、Skill、EmployeeSkill

Employee：

- `employee_id`；
- 姓名、邮箱、班组、产线；
- 技师等级；
- 当前负荷 `DecimalField(5,4)`；
- `on_duty`、`available`、`is_active`。

邮箱允许为空；邮箱为空时人员不具备邮件派工资格，返回 `EMAIL_NOT_CONFIGURED`，不保存格式错误邮箱作为演示数据。

### 7.7 WorkOrder：保养工单

保存：

- 工单编号；
- 关联预警和模具；
- 保养标准及版本快照；
- 保养等级；
- 保养项目快照；
- 标准工时；
- 优先级和要求完成时间；
- 当前状态；
- 最终派工人员；
- 创建人、确认人和关键时间；
- 派工至报工总历时；
- 开工至报工执行工时；
- 累计暂停时长；
- 工时偏差；
- 完成与验收结果。

### 7.8 工单附属模型

- `WorkOrderItem`：保养项目；
- `DispatchRecord`：派工和改派记录；
- `WorkOrderEvent`：不可变状态时间线；
- `PauseSegment`：暂停与恢复区间；
- `WorkOrderException`：异常记录；
- `EscalationRecord`：催办和升级；
- `AcceptanceRecord`：验收与退回；
- `KnowledgeSnapshot`：本次下发知识来源、版本、标签、摘要和内容哈希；
- `NotificationRecord`：平台邮件发送结果；
- `MaintenanceRecord`：验收完成后生成的模具保养履历；
- `AuditLog`：关键操作审计；
- `IdempotencyRecord`：写接口幂等。

MaintenanceRecord 同时保存：

- nullable `maintainer` 外键；
- `maintainer_employee_id_snapshot`；
- `maintainer_name_snapshot`。

避免同名人员和姓名变更影响历史统计。

---

## 8. 保养标准匹配规则

请求必须显式提供 `maintenance_level_code`，或由预警策略明确返回保养等级。系统不得在存在多个等级时静默猜测。

匹配顺序：

1. `mold_type + mold_level + mold_category + maintenance_level_code` 完全匹配；
2. 未命中时，允许 `mold_category` 为空的同类型、同等级、同保养等级标准；
3. 标准必须满足 `effective_from <= evaluated_at`，且 `effective_to` 为空或 `effective_to >= evaluated_at`；
4. 同一匹配范围只能存在一个活动且生效的标准；
5. 未找到返回 `STANDARD_NOT_FOUND`；
6. 多条冲突返回 `STANDARD_AMBIGUOUS`；
7. 未提供保养等级且策略无法确定时返回 `MAINTENANCE_LEVEL_REQUIRED`。

通过模型校验、Admin 表单、验证命令和测试共同防止活动标准重叠。

---

## 9. 参赛健康评分与预警规则

原参赛材料给出：

- 使用率 93.25%；
- 健康评分 72 分；
- 72 分为黄色；
- 小于 60 分红色；
- 小于 80 分黄色；
- 其余绿色。

原材料没有提供评分公式。为保持原参赛材料的表现形式，V3.0 冻结以下**参赛演示公式**，并必须在系统和答辩中标注“非企业正式制度”。

### 9.1 计算基础

所有计算使用 `Decimal`，预警判断使用未舍入原值；展示百分比保留两位小数。

```python
run_count_since_last = current_count - last_maintenance_count
usage_ratio = run_count_since_last / maintenance_threshold
usage_percent = usage_ratio * 100
```

### 9.2 DEMO_HEALTH_V1

```text
当 usage_ratio <= 0.90：
health_score = 100 - (usage_ratio / 0.90) × 20

当 0.90 < usage_ratio < 1.00：
health_score = 80 - ((usage_ratio - 0.90) / 0.10) × 25

当 usage_ratio >= 1.00：
health_score = max(0, 55 - (usage_ratio - 1.00) × 100)
```

最终显示分数四舍五入到整数。

主演示数据：

```text
usage_ratio = 0.9325
health_score = 71.875
显示为 72 分
预警等级 = YELLOW
```

### 9.3 预警等级

| 健康评分 | 等级 | 推荐动作 |
|---:|---|---|
| `<60` | `RED` | 紧急处理，建议 4 小时内确认并安排；真实排产锁定仍需主管确认 |
| `>=60 且 <80` | `YELLOW` | 高优先级，建议 7 日内完成保养 |
| `>=80` | `GREEN` | 正常监控，不自动创建工单 |

### 9.4 时间周期

`maintenance_days` 在 V1 中单独返回 `time_cycle_status`，不参与 `DEMO_HEALTH_V1`。后续取得企业正式规则后再升级公式版本，禁止无依据混入评分。

### 9.5 异常数据

- 当前累计模次小于上次保养模次：`INVALID_COUNT_DATA`；
- 阈值为空或小于等于零：`INVALID_STANDARD`；
- 关键字段缺失：`INCOMPLETE_MOLD_DATA`；
- 不得自行补值或让 LLM 猜测。

---

## 10. 候选人员规则

### 10.1 候选资格

员工必须同时满足：

- `is_active=true`；
- `on_duty=true`；
- `available=true`；
- `current_load < 0.80`；
- 技能匹配率 `>= 0.80`；
- 邮箱已配置且格式有效。

技能匹配率：

```python
skill_match_ratio = matched_required_skills / total_required_skills
```

标准未配置技能时返回 `SKILL_REQUIREMENT_NOT_CONFIGURED`，不得认定全部人员合格。

### 10.2 排序

高/紧急优先级：

```text
eligible
→ 同产线
→ 技能匹配率
→ 技师等级
→ 当前负荷
→ 员工编号
```

中/低优先级：

```text
eligible
→ 同产线
→ 技能匹配率
→ 当前负荷
→ 技师等级
→ 员工编号
```

排序必须稳定、可解释。Django 返回候选，不自动写入最终派工；最终人员由主管确认后调用派工接口。

---

## 11. 工单状态机

状态：

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
PENDING_ACCEPTANCE
COMPLETED
CANCELLED
```

允许流转：

```text
PENDING_ASSIGNMENT → ASSIGNED → IN_PROGRESS
IN_PROGRESS → PAUSED → IN_PROGRESS
IN_PROGRESS → PENDING_ACCEPTANCE
PENDING_ACCEPTANCE → COMPLETED
PENDING_ACCEPTANCE → IN_PROGRESS      # 验收退回
PENDING_ASSIGNMENT/ASSIGNED → CANCELLED
```

禁止：

- 未派工直接开工；
- 未开工直接报工；
- 未报工直接验收；
- 已完成工单再次派工或修改关键结果；
- 暂停不填写原因；
- 非派工人员操作工单，除非主管授权；
- 非主管执行派工、改派、验收或取消。

每次流转必须：

- 在数据库事务中完成；
- 校验当前状态和操作人角色；
- 写入 WorkOrderEvent 和 AuditLog；
- 使用 Idempotency-Key 防止平台重试重复执行。

---

## 12. 工时口径

同时保存三个口径：

```text
dispatch_to_complete_duration
= 报工时间 - 派工时间

waiting_to_start_duration
= 开工时间 - 派工时间

actual_execution_duration
= 报工时间 - 开工时间 - 累计暂停时长
```

工时偏差：

```text
hours_variance = actual_execution_hours - standard_hours
variance_ratio = hours_variance / standard_hours
```

原材料中的“报工时间 - 派工时间”保留为总历时；分析实际保养效率时使用 `actual_execution_duration`。

---

## 13. 最终 API 契约

### 13.1 通用请求头

```http
X-API-Key: <secret>
X-Request-ID: <optional>
Idempotency-Key: <required-for-write-actions>
Accept: application/json
```

所有写请求必须携带操作人：

```json
{
  "actor_id": "SUPERVISOR-001",
  "actor_role": "SUPERVISOR"
}
```

Django 根据本地操作人记录校验角色，不只相信自然语言中的姓名和工号。

### 13.2 统一成功响应

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {},
  "meta": {
    "contract_version": "3.0",
    "source_type": "DEMO",
    "generated_at": "2026-08-12T15:30:00+08:00"
  },
  "request_id": "req-20260812-0001"
}
```

### 13.3 统一错误响应

```json
{
  "code": "STANDARD_NOT_FOUND",
  "message": "未找到适用于该模具的保养标准",
  "data": null,
  "errors": [],
  "request_id": "req-20260812-0002"
}
```

业务上无候选人员仍使用成功响应：

```json
{
  "code": "SUCCESS",
  "data": {
    "candidates": [],
    "candidate_status": "NO_ELIGIBLE_STAFF"
  }
}
```

---

## 14. 最终 API 清单

### 14.1 服务和元数据

```http
GET /api/v1/health
GET /api/v1/meta
```

### 14.2 模具和标准

```http
GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/due
GET /api/v1/molds/{mold_id}/task-context
GET /api/v1/maintenance-standards
GET /api/v1/maintenance-standards/{standard_id}
GET /api/v1/maintenance-standards/match
```

`task-context` 返回模具、预警、标准、知识画像、候选人员和推荐截止时间，但不表示已创建或已派工。

### 14.3 预警

```http
POST /api/v1/alerts/scan
GET  /api/v1/alerts
GET  /api/v1/alerts/{alert_id}
POST /api/v1/alerts/{alert_id}/acknowledge
```

### 14.4 人员

```http
GET /api/v1/staff
GET /api/v1/staff/{employee_id}
GET /api/v1/staff/available
```

### 14.5 工单和派工

```http
POST /api/v1/work-orders
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{work_order_id}
GET  /api/v1/work-orders/{work_order_id}/timeline
GET  /api/v1/work-orders/{work_order_id}/candidates
POST /api/v1/work-orders/{work_order_id}/assign
POST /api/v1/work-orders/{work_order_id}/cancel
```

### 14.6 执行、报工与验收

```http
POST /api/v1/work-orders/{work_order_id}/start
POST /api/v1/work-orders/{work_order_id}/pause
POST /api/v1/work-orders/{work_order_id}/resume
POST /api/v1/work-orders/{work_order_id}/complete
POST /api/v1/work-orders/{work_order_id}/accept
POST /api/v1/work-orders/{work_order_id}/reject
```

### 14.7 知识与邮件回写

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge-snapshot
POST /api/v1/work-orders/{work_order_id}/notifications
GET  /api/v1/work-orders/{work_order_id}/notifications
```

### 14.8 异常、催办和升级

```http
POST /api/v1/work-orders/{work_order_id}/exceptions
POST /api/v1/work-orders/{work_order_id}/escalations
GET  /api/v1/work-orders/overdue
POST /api/v1/work-orders/scan-overdue
```

### 14.9 统计分析

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
GET /api/v1/analytics/overdue-orders
GET /api/v1/analytics/mold-history
GET /api/v1/analytics/staff-load
GET /api/v1/analytics/downtime
```

---

## 15. 关键接口行为

### 15.1 创建工单

`POST /work-orders` 必须：

- 以 `alert_id` 为主要输入；
- 复制模具、标准和工时快照；
- 根据预警等级确定优先级和截止时间；
- 防止同一模具、同一保养等级存在重复未关闭工单；
- 返回 `DUPLICATE_OPEN_WORK_ORDER` 时附现有工单编号；
- 创建后将预警状态更新为 `WORK_ORDER_CREATED`。

### 15.2 派工

`POST /work-orders/{id}/assign` 必须：

- 校验工单为待派工；
- 校验主管角色；
- 重新校验被选人员资格，不能只相信此前候选查询；
- 保存 DispatchRecord；
- 更新状态为 `ASSIGNED`；
- 返回邮件发送所需的工单事实和人员邮箱。

### 15.3 知识快照

平台检索知识库后回写：

- `knowledge_profile_code`；
- 来源文档名称和版本；
- 章节或片段标识；
- 使用的知识标签；
- 内容摘要；
- 内容哈希；
- 检索时间。

Django 不保存整个知识库，只保存本次工单实际使用的可追溯快照。

### 15.4 邮件结果回写

平台发送邮件后回写：

- 渠道 `EMAIL`；
- 收件员工和脱敏邮箱快照；
- 平台消息 ID；
- 状态 `PENDING`、`SENT`、`FAILED`、`DELIVERED`；
- 发送时间；
- 失败原因；
- 使用的知识快照。

邮件失败不回滚已经完成的派工，但必须可重试并保留记录。

### 15.5 报工和验收

报工后进入 `PENDING_ACCEPTANCE`，不直接完成。

验收通过后，Django在同一事务中：

1. 将工单设为 `COMPLETED`；
2. 生成 MaintenanceRecord；
3. 更新 Mold.last_maintenance_count；
4. 更新 Mold.last_maintenance_time；
5. 关闭关联预警；
6. 重新计算人员负荷；
7. 写入事件和审计日志。

验收退回则回到 `IN_PROGRESS`，并记录退回原因。

---

## 16. 催办和升级规则

参赛演示规则：

| 场景 | 规则 | 动作 |
|---|---|---|
| 红色预警未处理 | 2 小时未确认或建单 | 升级主管 |
| 黄色预警未安排 | 24 小时未派工提醒，3 天未安排升级 | 发送催办 |
| 执行超时 | 实际执行时长超过标准工时 50% | 记录异常并升级 |
| 强制升级 | 实际执行时长超过标准工时 100% | 必须升级 |
| 暂停过久 | 暂停超过 4 小时或跨班次 | 生成异常提醒 |
| 待验收 | 24 小时未验收 | 提醒主管 |

原材料中的“待派工超过 7 天”不再直接采用，因为与“黄色 7 日内完成”冲突。

---

## 17. 平台能力预验证 Gate -1

正式编码前必须用最小接口验证比赛平台：

- 能访问公网 HTTPS；
- 能设置 `X-API-Key`、`X-Request-ID` 和 `Idempotency-Key`；
- 能传递动态 `mold_id`、`actor_id` 和 `employee_id`；
- 能解析嵌套 JSON 和候选人员数组；
- 能把 Django 返回的邮箱作为动态邮件收件人；
- 能用 `knowledge_profile_code` 和标签过滤知识库；
- 能执行 POST 并读取错误码；
- 能回写邮件发送结果；
- 能在节点重试时保持幂等键不变。

最小联调链路：

```text
查询测试模具
→ 查询测试候选人
→ 检索一条知识
→ 发送一封测试邮件
→ 回写邮件结果
```

Gate -1 未通过，不得冻结详细 API 合同或开始全量编码。

---

## 18. 演示数据

至少准备：

- 12 套模具；
- 6 条保养标准；
- 8 名员工；
- 10 个技能；
- 12 条预警记录；
- 10 张工单；
- 20 条历史保养记录；
- 知识快照和邮件记录；
- 绿色、黄色、红色、标准缺失、模次异常、无候选、邮件失败、暂停、验收退回等场景。

主演示模具固定：

```text
MOLD-2024-0891
前壳体注塑模
A 类精密注塑模
4 腔
当前累计模次 386500
上次保养模次 200000
本周期运行 186500
标准阈值 200000
使用率 93.25%
健康评分 72
黄色预警
标准工时 8 小时
注塑车间 / A区模具库
```

其他模拟数据必须标记 `data_source=DEMO`。

管理命令：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
python manage.py backup_demo_data
```

---

## 19. 安全与审计

- 平台使用 `X-API-Key` 认证；
- 写接口要求 Idempotency-Key；
- API Key、数据库密码和 Django SECRET_KEY 只从环境变量读取；
- 操作人必须在 Django 中存在且角色合法；
- 关键操作使用数据库事务和行锁；
- 日志记录 request_id、路径、状态码、耗时、actor_id 和业务对象；
- 不记录 API Key、管理员密码或完整敏感数据；
- 邮箱日志脱敏；
- `DEBUG=False`、HTTPS、HSTS、正确 ALLOWED_HOSTS 和 SECURE_PROXY_SSL_HEADER；
- Admin 使用独立路径并限制来源 IP；
- 审计日志原则上不可通过普通业务接口删除。

---

## 20. 部署方案

Docker Compose：

```yaml
services:
  web:       # Django + Gunicorn，内部 18080
  db:        # PostgreSQL 16
  nginx:     # 80/443
```

不部署：

```text
Redis
Celery
Mailpit
SMTP
向量数据库
```

服务器建议：

- Ubuntu 22.04/24.04 LTS；
- 2 核 CPU；
- 4 GB 内存；
- 40 GB 磁盘；
- 公网 IP；
- 主域名和备用域名；
- 两个域名均配置有效 HTTPS 证书。

不要使用“公网 IP HTTPS”作为域名解析失败的主要备用方案，以免证书主机名不匹配。

---

## 21. 测试与质量门禁

### 21.1 必测内容

- 健康评分公式和主演示 72 分；
- 60、80 分预警边界；
- 标准精确匹配、类别回退、缺失和冲突；
- 预警扫描幂等；
- 重复工单防护；
- 候选人员技能、负荷、产线和技师等级排序；
- 派工时重新校验资格；
- 所有状态合法和非法流转；
- 暂停区间和实际工时；
- 报工后待验收；
- 验收通过后履历与模具基准更新；
- 验收退回；
- 知识快照和邮件结果回写；
- 邮件失败不回滚派工；
- 超时扫描和升级；
- 统计值可由明细复算；
- API Key、权限、幂等、并发和统一错误响应；
- OpenAPI 与实现一致。

### 21.2 自动化门禁

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
docker compose up -d
python scripts/smoke_test.py
```

Phase 1 增加 `.github/workflows/ci.yml`，PR 自动执行静态检查、迁移检查、测试、OpenAPI 校验和 Docker 构建。

---

## 22. 开发阶段与 Stop Gate

### Gate -1：平台能力验证

完成最小 GET、POST、知识检索、动态邮箱、邮件发送和回写链路。

### Phase 0：合同与业务规则冻结

交付 API 合同、数据字典、状态机、错误码、健康评分说明和演示数据清单。

### Phase 1：工程骨架与 CI

完成 Django、DRF、认证、权限、幂等、统一响应、OpenAPI、pytest、Ruff 和 GitHub Actions。

### Phase 2：主数据与 Admin

完成模具、标准、预警策略、人员、技能、操作人、种子数据和验证命令。

### Phase 3：健康评分与预警

完成标准匹配、健康评分、扫描、预警保存、确认和待保养清单。

### Phase 4：工单创建和派工

完成工单去重、候选人、主管确认、派工、改派和任务上下文。

### Phase 5：知识与邮件审计

完成知识快照、邮件结果回写和通知查询。

### Phase 6：过程追踪

完成开工、暂停、恢复、异常、报工、验收、退回、取消和时间线。

### Phase 7：归档与分析

完成模具履历、工时、完成率、超时、人员负荷和停机统计。

### Phase 8：部署与安全

完成 PostgreSQL、Docker、Nginx、HTTPS、备份、恢复和外网冒烟测试。

### Phase 9：比赛平台完整联调

连续完成 3 次：

```text
扫描预警
→ 创建工单
→ 候选匹配
→ 主管派工
→ 知识检索
→ 邮件发送与回写
→ 开工/暂停/报工
→ 验收归档
→ 查询统计
```

无 5xx、无重复工单、无错误状态、邮件到达测试邮箱。

---

## 23. P0 与 P1 范围

### P0 参赛必需

- 模具、标准、健康评分和预警；
- 预警扫描和保存；
- 工单创建和去重；
- 候选人员和主管派工；
- 知识快照和邮件回写；
- 开工、暂停、恢复、报工和验收；
- 工单时间线和模具履历；
- 总体工时、完成率和超时统计；
- Admin、种子数据、OpenAPI、认证、测试和部署。

### P1 可在 P0 稳定后实现

- 工单改派；
- 多级升级策略；
- 复杂同比、环比和趋势预测数据；
- 备件消耗；
- 成本分析；
- Excel/Word 导出；
- 真实 MES/ERP 适配器。

---

## 24. 参赛演示脚本

1. 平台调用 `/alerts/scan` 执行今日巡检；
2. 展示黄色和红色模具；
3. 为 MOLD-2024-0891 创建工单；
4. Django 返回候选人员及技能、负荷、产线和等级依据；
5. 主管确认派工；
6. 平台使用知识画像检索点检要求；
7. 平台发送含任务、点检要求、安全事项和验收标准的邮件；
8. 平台回写知识快照和邮件成功记录；
9. 保养人员开工，演示一次暂停和恢复；
10. 保养人员报工，工单进入待验收；
11. 主管根据知识库验收标准完成验收；
12. Django更新模具保养基准和履历；
13. 平台查询工时、完成率和超时统计并生成分析结论。

---

## 25. Definition of Done

系统只有同时满足以下条件才可标记 `READY_FOR_COMPETITION`：

- 原参赛材料中的预警、工单、派工、追踪、报工、验收、归档和统计闭环均有真实模拟状态；
- 智能体平台与 Django 职责无重复、无缺口；
- 主演示模具返回 93.25%、72 分和黄色；
- 写接口具有权限、幂等和状态校验；
- 候选人员可解释且派工时重新校验；
- 知识快照和邮件结果可追溯；
- 实际工时口径明确；
- 验收后模具履历正确更新；
- 所有统计可由明细复算；
- 所有模拟数据标记 DEMO；
- API 合同、OpenAPI、README 和实现一致；
- 全量测试、CI、Docker 和 HTTPS 冒烟测试通过；
- 连续 3 次完整平台演示成功。

---

## 26. Git 管理要求

实施分支：

```text
agent/django-full-workflow-v1
```

要求：

- 不直接在 main 开发业务代码；
- 每个 Phase 独立提交；
- 每个 Stop Gate 汇报测试、提交 SHA 和剩余风险；
- 创建 Draft PR；
- 未完成平台联调前不标记 Ready for Review；
- 未经负责人明确批准不合并；
- 任何范围扩展必须先修改本计划并重新审阅。

---

## 27. 最终冻结矩阵

| 决策项 | 结论 |
|---|---|
| 是否保持原参赛完整业务材料 | 是 |
| Django 是否只读 | 否 |
| Django 是否保存工单与过程状态 | 是 |
| Django 是否执行最终派工写入 | 是，经主管确认 |
| Django 是否记录报工与验收 | 是 |
| Django 是否发送邮件 | 否 |
| 邮件由谁发送 | 比赛智能体平台 |
| Django 是否记录邮件结果 | 是 |
| 知识库正文存放位置 | 比赛智能体平台 |
| Django 是否保存知识快照 | 是 |
| Django 是否调用 LLM | 否 |
| 是否实现健康评分 | 是，参赛演示公式 DEMO_HEALTH_V1 |
| 数据库 | PostgreSQL 16 |
| Redis/Celery | 默认不使用 |
| 部署 | Docker Compose + Nginx + Gunicorn |
| 公网入口 | HTTPS 443 |
| 认证 | X-API-Key + 操作人校验 |
| 数据性质 | DEMO |
| 权威计划 | 本文件 V3.0 |

---

## 28. 最终结论

MoldGuard Django Server 的最终参赛定位为：

> **模具保养智能预警与管理智能体的外部虚拟业务服务器、规则引擎和工单状态中心。**

智能体平台负责“理解、检索、生成和通知”，Django 负责“事实、规则、事务、状态和审计”。两者共同完成原参赛材料所要求的完整业务闭环。
