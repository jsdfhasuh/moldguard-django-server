# MoldGuard Django 查询 API 参赛最终实施计划

- **状态**：`FINAL_FROZEN`
- **版本**：V2.0
- **日期**：2026-08-12
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **实施分支**：`agent/django-query-api-v1`
- **权威性**：本文件是 Django 服务器后续开发、测试、部署和比赛验收的唯一范围基线
- **系统定位**：外部模拟业务数据查询服务器
- **最终边界**：Django 只提供结构化查询 API；知识库、LLM、工作流、最终人员确认和邮件发送均由比赛平台或其他外部渠道完成

---

## 1. 最终决策摘要

本项目采用以下最终架构：

> **一个比赛智能体平台 + 一个 Django 外部查询服务器。**

### 1.1 Django 最终负责

- 模具台账查询；
- 模具当前累计模次和上次保养信息查询；
- 保养标准及标准版本查询；
- 距上次保养运行模次、保养周期使用率、剩余模次和预警等级等确定性计算；
- 黄色、红色待保养模具清单查询；
- 人员、技能、技师等级、当前负荷、在岗状态和邮箱查询；
- 按固定规则返回候选保养人员；
- 为比赛平台知识库检索提供结构化标签和推荐检索文本；
- 历史保养记录和基础统计查询；
- Django Admin 演示数据维护；
- 演示数据初始化、重置和校验；
- OpenAPI 契约、API Key 认证、请求日志、测试和部署。

### 1.2 比赛平台或其他外部渠道最终负责

- 用户自然语言交互；
- 智能体工作流编排；
- 点检要求、操作指导书、故障案例等知识库；
- RAG 检索；
- LLM 生成预警报告和任务说明；
- 展示候选人员并完成最终人员确认；
- 组装派工任务；
- 生成并发送邮件；
- 邮件正文、附件和送达状态；
- 后续任务互动。

### 1.3 Django 明确不负责

- 自然语言理解；
- 大模型调用；
- Embedding、Rerank、向量数据库或知识库正文；
- 邮件、SMTP、Mailpit、附件和邮件回写；
- 企业微信、钉钉或短信通知；
- 工单创建；
- 最终派工写入；
- 开工、暂停、恢复、报工、验收和归档；
- 生产排程锁定；
- Celery、Redis 和后台任务；
- 定时巡检；
- 独立 Vue、React 或其他前端。

### 1.4 公共 API 方法约束

比赛平台访问 `/api/v1` 时只允许：

```text
GET
HEAD
OPTIONS
```

公共 API 对 `POST`、`PUT`、`PATCH`、`DELETE` 一律返回：

```text
405 Method Not Allowed
```

模拟数据仅通过以下两种方式维护：

1. Django Admin；
2. Django management command。

---

## 2. 需求依据与来源边界

本计划依据以下原始材料整理：

1. 《基于 Dify 平台的模具保养 AI 智能体系统设计方案》；
2. 《模具保养智能预警与管理智能体——应用场景说明书》；
3. 已确认的比赛实施决策：比赛平台能够发送邮件，Django 只提供查询 API。

### 2.1 原始方案明确支持的数据

原方案中的模具状态查询涉及：

- 模具编码；
- 模具名称；
- 模具类型；
- 模具等级；
- 模具类别；
- 腔数；
- 当前累计模次；
- 保养模次；
- 模具一级位置；
- 模具二级位置；
- 保养标准工时；
- 上次保养模次；
- 上次保养时间。

原方案中的人员匹配事实包括：

- 员工编号；
- 员工姓名；
- 所需技能；
- 技能匹配度；
- 当前负荷；
- 所在产线；
- 技师等级；
- 是否在岗。

本计划增加 `email` 字段，仅用于将候选人员邮箱返回给比赛平台。Django 不发送邮件。

原方案中的知识库包括：

- 保养标准库；
- 故障案例库；
- 工时定额库；
- 备件手册；
- 操作指导书。

Django 不保存这些文档正文，只返回适合知识库检索的结构化标签。

### 2.2 原始材料未完整定义的内容

以下内容不得在代码中自行猜测：

1. 健康评分的计算公式；
2. 93.25% 保养周期使用率为何对应健康评分 72 分；
3. 图片中所有注塑模具、钣金模具等级对应的完整准确阈值；
4. 时间周期是否参与最终预警，以及如何与生产模次合并；
5. 人员匹配各项因素的综合权重；
6. “模具寿命缩短 30%—50%”的数据来源；
7. “2—4 小时压缩到 10 秒以内”的测量方法和测试记录。

这些内容不能作为服务器已实现效果或验收指标。

### 2.3 参赛版演示规则与生产规则的区别

为了让服务器可以稳定参赛，本计划冻结一套**参赛演示规则**。该规则只用于比赛演示，不代表企业正式生产制度。

正式接入企业时，必须使用经过业务审批的保养标准和预警规则替换演示配置。

---

## 3. 项目目标

### 3.1 核心目标

向比赛智能体平台提供稳定、结构化、可解释、可验证的模具业务查询 API，使平台可以完成：

```text
用户查询模具或执行巡检
        ↓
平台调用 Django 查询模具和保养状态
        ↓
Django 返回确定性预警结果和知识检索标签
        ↓
平台检索对应点检要求
        ↓
平台查询候选人员和邮箱
        ↓
平台生成派工任务并发送邮件
```

### 3.2 参赛版必须具备的能力

- 查询单套模具完整资料；
- 查询单套模具保养状态；
- 批量查询黄色和红色待保养模具；
- 查询匹配的保养标准；
- 查询知识库检索上下文；
- 查询符合条件的候选人员；
- 一次接口返回平台生成任务邮件所需的全部结构化上下文；
- 查询历史保养记录；
- 查询基础统计；
- 通过 Admin 或命令一键恢复演示数据；
- 通过公网 HTTPS 被比赛平台稳定访问。

### 3.3 非目标

本服务器不追求替代真实 MES、ERP、EAM 或邮件系统。其目标是提供一个可验证的模拟业务数据源，并保持未来替换真实数据适配器的可能性。

---

## 4. 总体架构

```text
┌───────────────────────────────────────────┐
│              比赛智能体平台                │
│                                           │
│ 对话 │ 工作流 │ 知识库 │ LLM │ 邮件发送    │
└────────────────────┬──────────────────────┘
                     │ HTTPS + JSON
                     │ X-API-Key
                     ▼
┌───────────────────────────────────────────┐
│        MoldGuard Django Query API          │
│                                           │
│ 模具查询 │ 标准匹配 │ 状态计算 │ 人员候选   │
│ 知识标签 │ 历史记录 │ 基础统计 │ OpenAPI    │
└────────────────────┬──────────────────────┘
                     │
                     ▼
          SQLite 参赛演示数据库
                     ▲
                     │
          Django Admin / 管理命令
```

### 4.1 技术基线

| 项目 | 最终选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS 最新安全补丁版本 |
| API 框架 | Django REST Framework 3.16 系列 |
| 查询过滤 | django-filter |
| API 文档 | drf-spectacular |
| 数据库 | SQLite，比赛演示使用持久化卷 |
| 测试 | pytest + pytest-django |
| 代码质量 | Ruff |
| 应用服务器 | Gunicorn |
| 反向代理 | Nginx |
| 部署 | Docker Compose |
| 时区 | Asia/Shanghai |
| Django 内部端口 | 18080 |
| 公网入口 | HTTPS 443 |

### 4.2 为什么最终选择 SQLite

参赛版以只读查询为主，数据规模小，写入仅发生在 Admin 或重置命令中。SQLite 可以减少 PostgreSQL 容器、账号、备份和网络配置等额外复杂度，提高现场稳定性。

数据访问层不得使用 SQLite 专有业务逻辑，后续应可通过配置切换 PostgreSQL。

### 4.3 为什么不使用 Redis 和 Celery

参赛版没有邮件发送、后台任务、异步工单或定时巡检，因此 Redis 和 Celery 不在范围内。增加它们只会提高部署复杂度和故障点数量。

---

## 5. Django 工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── uv.lock                         # 若采用 uv
├── .env.example
├── config/
│   ├── __init__.py
│   ├── urls.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── development.py
│       └── production.py
├── apps/
│   ├── common/
│   │   ├── authentication.py
│   │   ├── exceptions.py
│   │   ├── middleware.py
│   │   ├── pagination.py
│   │   ├── permissions.py
│   │   └── responses.py
│   ├── molds/
│   ├── standards/
│   ├── staff/
│   ├── maintenance/
│   ├── analytics/
│   └── workorders/                 # 可选，只读快照
├── data/
│   └── demo/
│       ├── molds.json
│       ├── standards.json
│       ├── staff.json
│       ├── maintenance_records.json
│       └── work_order_snapshots.json
├── docs/
│   ├── plans/
│   ├── contracts/
│   │   └── openapi.yaml
│   ├── examples/
│   └── operations/
├── tests/
│   ├── unit/
│   ├── api/
│   ├── contract/
│   └── integration/
├── scripts/
│   └── smoke_test.py
├── Dockerfile
├── docker-compose.yml
├── nginx/
│   └── default.conf
└── README.md
```

第一版不开发独立前端。管理人员通过 Django Admin 维护演示数据。

---

## 6. 核心数据模型

## 6.1 Mold：模具台账

建议字段：

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `mold_id` | CharField | 唯一、不可为空 |
| `mold_name` | CharField | 不可为空 |
| `mold_type` | CharField | 注塑模具、钣金模具等 |
| `mold_level` | CharField | A/B/C 或业务等级 |
| `mold_category` | CharField | 可为空 |
| `cavity_count` | PositiveIntegerField | 可为空 |
| `current_count` | PositiveBigIntegerField | 当前累计模次 |
| `last_maintenance_count` | PositiveBigIntegerField | 上次保养时累计模次 |
| `last_maintenance_time` | DateTimeField | 可为空，但状态接口需明确缺失 |
| `primary_location` | CharField | 一级位置 |
| `secondary_location` | CharField | 二级位置 |
| `production_line` | CharField | 所属产线 |
| `status` | ChoiceField | `IN_PRODUCTION`、`IN_STORAGE`、`UNDER_REPAIR`、`DISABLED` |
| `data_source` | ChoiceField | 参赛版固定为 `DEMO` |
| `created_at` | DateTimeField | 自动记录 |
| `updated_at` | DateTimeField | 自动记录 |

约束：

- `current_count >= 0`；
- `last_maintenance_count >= 0`；
- `mold_id` 唯一；
- `DISABLED` 模具不进入待保养清单。

## 6.2 MaintenanceStandard：保养标准

| 字段 | 说明 |
|---|---|
| `standard_id` | 标准唯一编号 |
| `mold_type` | 适用模具类型 |
| `mold_level` | 适用模具等级 |
| `mold_category` | 可选类别 |
| `maintenance_level` | 一级、二级、三级保养等 |
| `maintenance_threshold` | 标准保养模次 |
| `maintenance_days` | 可选时间周期，V1 不参与预警 |
| `standard_hours` | 标准保养工时 |
| `version` | 标准版本 |
| `effective_from` | 生效日期 |
| `effective_to` | 可为空 |
| `is_active` | 是否启用 |
| `knowledge_tags` | JSON 数组，用于知识库检索 |

精确阈值、标准工时和版本必须由该模型返回，不由 LLM 或知识库自行推断。

## 6.3 AlertPolicy：参赛预警策略

| 字段 | 示例 |
|---|---|
| `policy_code` | `DEMO_USAGE_RATIO_V1` |
| `green_upper` | `0.90` |
| `yellow_upper` | `1.00` |
| `version` | `V1.0` |
| `is_active` | `true` |
| `description` | 参赛演示规则，非企业正式制度 |

系统只允许一个活动策略。阈值不直接写死在视图中。

## 6.4 Skill：技能

| 字段 | 说明 |
|---|---|
| `skill_code` | 唯一编码 |
| `skill_name` | 技能名称 |
| `is_active` | 是否有效 |

## 6.5 Employee：人员信息

| 字段 | 说明 |
|---|---|
| `employee_id` | 员工编号，唯一 |
| `employee_name` | 员工姓名 |
| `email` | 平台发送邮件所需地址 |
| `team` | 所属班组 |
| `production_line` | 所属产线 |
| `skill_level` | `JUNIOR`、`INTERMEDIATE`、`SENIOR`、`EXPERT` |
| `current_load` | 0.00—1.00 |
| `on_duty` | 是否在岗 |
| `available` | 是否可接任务 |
| `is_active` | 是否有效 |

约束：

- `0 <= current_load <= 1`；
- 邮箱格式必须有效；
- 失效人员不进入候选列表。

## 6.6 EmployeeSkill：人员技能关联

| 字段 | 说明 |
|---|---|
| `employee` | 员工 |
| `skill` | 技能 |
| `proficiency` | 熟练度 0.00—1.00 |
| `is_valid` | 是否有效 |

同一员工和同一技能只能存在一条有效关联。

## 6.7 MaintenanceRecord：历史保养记录

| 字段 | 说明 |
|---|---|
| `record_id` | 记录编号 |
| `mold` | 关联模具 |
| `maintenance_level` | 保养等级 |
| `maintenance_time` | 保养时间 |
| `maintenance_count` | 保养时累计模次 |
| `standard_hours` | 标准工时 |
| `actual_hours` | 实际工时 |
| `maintainer_name` | 保养人员姓名 |
| `result` | `PASSED`、`FAILED`、`PARTIAL` |
| `remarks` | 备注 |

该模型只通过公共 API 查询，不开放新增和修改 API。

## 6.8 WorkOrderSnapshot：可选只读工单快照

仅在比赛平台需要展示当前任务清单时启用：

- `work_order_id`；
- `mold_id`；
- `status`；
- `priority`；
- `estimated_hours`；
- `required_finish_at`；
- `assigned_employee_id`；
- `created_at`。

该表只由种子数据或 Admin 维护，不提供写接口，也不表示比赛平台真实发送邮件后的状态。

---

## 7. 保养标准匹配规则

给定一套模具和可选 `maintenance_level`，按以下顺序匹配活动标准：

1. `mold_type + mold_level + mold_category + maintenance_level` 完全匹配；
2. 未命中时，允许 `mold_category` 为空的同类型、同等级、同保养等级标准；
3. 未指定 `maintenance_level` 时，使用该模具默认活动标准；
4. 同一匹配范围不得存在两个同时生效的活动标准；
5. 未找到标准时返回 `STANDARD_NOT_FOUND`；
6. 多条标准冲突时返回 `STANDARD_AMBIGUOUS`，不得静默选择。

数据库和测试必须防止活动标准重叠。

---

## 8. 保养状态计算

## 8.1 基础计算

```python
run_count_since_last = current_count - last_maintenance_count
usage_ratio = run_count_since_last / maintenance_threshold
usage_percent = usage_ratio * 100
remaining_count = max(maintenance_threshold - run_count_since_last, 0)
overdue_count = max(run_count_since_last - maintenance_threshold, 0)
```

## 8.2 参赛版最终预警规则

| 使用率 | `maintenance_status` | `alert_level` |
|---:|---|---|
| `< 90%` | `NORMAL` | `GREEN` |
| `>= 90% 且 < 100%` | `DUE_SOON` | `YELLOW` |
| `>= 100%` | `OVERDUE` | `RED` |

该规则来自参赛实施适配，不等同于企业正式制度。

## 8.3 健康评分处理

V1 不实现健康评分。

接口固定返回：

```json
{
  "health_score": null,
  "health_score_status": "NOT_DEFINED"
}
```

禁止：

- 根据使用率自行推算健康评分；
- 让 LLM 生成健康评分；
- 将原方案示例中的 72 分写死；
- 根据未确认公式进行红黄绿判断。

## 8.4 时间周期处理

`maintenance_days` 可以保存和返回，但 V1 不参与红黄绿判定。接口返回：

```json
{
  "time_cycle_evaluation": "NOT_ENABLED"
}
```

## 8.5 异常数据

| 场景 | 错误码/处理 |
|---|---|
| 当前累计模次小于上次保养模次 | `INVALID_COUNT_DATA` |
| 标准阈值为空或小于等于零 | `INVALID_STANDARD` |
| 找不到适用标准 | `STANDARD_NOT_FOUND` |
| 存在多个冲突标准 | `STANDARD_AMBIGUOUS` |
| 模具停用 | 返回详情，但不进入待保养清单 |
| 关键字段缺失 | `INCOMPLETE_MOLD_DATA` |

Django 不自行补值。

---

## 9. 候选人员查询规则

原方案提出以下派工规则：

1. 技能匹配度不低于 80%；
2. 当前负荷低于 80%；
3. 同产线人员优先；
4. 高优先级模具优先考虑高级技师。

本服务器只执行候选查询，不执行最终派工。

## 9.1 技能匹配率

```python
skill_match_ratio = matched_required_skills / total_required_skills
```

当标准没有配置所需技能时，返回：

```text
SKILL_REQUIREMENT_NOT_CONFIGURED
```

不得自动认定所有员工合格。

## 9.2 候选资格

员工同时满足以下条件才为 `eligible=true`：

- `is_active=true`；
- `on_duty=true`；
- `available=true`；
- `current_load < max_load`，默认 `0.80`；
- `skill_match_ratio >= min_skill_match`，默认 `0.80`；
- 邮箱有效。

## 9.3 排序规则

候选人员排序：

1. `eligible=true` 优先；
2. 同产线优先；
3. 技能匹配率从高到低；
4. 当前负荷从低到高；
5. 当 `task_priority=HIGH` 或 `URGENT` 时，高级技师优先；
6. 员工编号稳定排序，确保多次演示结果一致。

## 9.4 返回原则

接口必须返回：

- 员工编号；
- 姓名；
- 邮箱；
- 班组；
- 产线；
- 技师等级；
- 当前负荷；
- 技能匹配率；
- 已匹配技能；
- 缺失技能；
- 是否同产线；
- 是否满足候选资格；
- 命中或排除原因。

Django 不返回 `assigned_to`，避免让查询结果看起来像已经完成派工。

---

## 10. API 通用契约

### 10.1 基础路径

```text
/api/v1
```

### 10.2 请求头

```http
X-API-Key: <secret>
X-Request-ID: <optional-client-request-id>
Accept: application/json
```

### 10.3 统一成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "meta": {
    "contract_version": "1.0",
    "source_type": "DEMO",
    "generated_at": "2026-08-12T15:30:00+08:00"
  },
  "request_id": "req-20260812-0001"
}
```

### 10.4 统一错误响应

```json
{
  "code": "STANDARD_NOT_FOUND",
  "message": "未找到适用于该模具的保养标准",
  "data": null,
  "errors": [
    {
      "field": "mold_id",
      "detail": "MOLD-2024-9999"
    }
  ],
  "request_id": "req-20260812-0002"
}
```

### 10.5 分页

```text
page=1
page_size=20
```

约束：

- 默认 `page_size=20`；
- 最大 `page_size=100`；
- 返回 `count`、`next`、`previous` 和 `results`。

### 10.6 排序

只允许白名单字段，禁止将任意请求参数直接传给 ORM `order_by()`。

### 10.7 合同版本

响应 `meta.contract_version` 固定为 `1.0`。破坏兼容性的修改必须升级 API 版本或合同版本。

---

## 11. 最终 API 清单

## 11.1 服务状态

```http
GET /api/v1/health
GET /api/v1/meta
```

`/health` 返回：

- 应用状态；
- 数据库状态；
- 当前时间；
- 版本；
- 演示数据是否已初始化。

`/meta` 返回：

- API 合同版本；
- 活动预警策略；
- 数据源类型；
- 可用模具类型；
- 可用保养等级；
- 服务能力和明确不支持的能力。

## 11.2 模具查询

```http
GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/due
GET /api/v1/molds/{mold_id}/knowledge-context
GET /api/v1/molds/{mold_id}/task-context
```

### 模具列表过滤

```text
mold_type
mold_level
mold_category
production_line
status
alert_level
search
page
page_size
ordering
```

### 待保养清单

`GET /api/v1/molds/due` 默认仅返回：

```text
YELLOW
RED
```

支持：

```text
alert_level=YELLOW|RED
mold_type
production_line
limit
```

## 11.3 保养标准查询

```http
GET /api/v1/maintenance-standards
GET /api/v1/maintenance-standards/{standard_id}
GET /api/v1/maintenance-standards/match
```

匹配参数：

```text
mold_id
maintenance_level
```

或：

```text
mold_type
mold_level
mold_category
maintenance_level
```

## 11.4 人员查询

```http
GET /api/v1/staff
GET /api/v1/staff/{employee_id}
GET /api/v1/staff/available
```

可用人员参数：

```text
mold_id
maintenance_level
required_skills
production_line
max_load
min_skill_match
task_priority
max_candidates
```

## 11.5 历史保养记录

```http
GET /api/v1/maintenance-records
GET /api/v1/maintenance-records/{record_id}
```

过滤参数：

```text
mold_id
start_date
end_date
maintenance_level
maintainer_name
result
```

## 11.6 基础统计

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/mold-history
```

统计只基于数据库已有模拟数据，不进行趋势预测。

## 11.7 可选只读工单

```http
GET /api/v1/work-orders
GET /api/v1/work-orders/{work_order_id}
```

该模块为 P1，可在 P0 完成后实施。

---

## 12. 知识库检索上下文接口

```http
GET /api/v1/molds/{mold_id}/knowledge-context
```

返回示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "mold_id": "MOLD-2024-0891",
    "mold_type": "注塑模具",
    "mold_level": "A",
    "mold_category": "精密注塑模",
    "maintenance_level": "一级保养",
    "standard_id": "STD-INJECTION-A-L1",
    "standard_version": "V1.0",
    "required_skills": [
      "注塑模具保养",
      "温控系统检查"
    ],
    "knowledge_tags": [
      "注塑模具",
      "一级保养",
      "模腔清洁",
      "排气槽检查",
      "导柱导套检查",
      "温控系统检查",
      "安全注意事项",
      "验收标准"
    ],
    "recommended_query": "A类精密注塑模 一级保养 点检项目 操作步骤 安全注意事项 验收标准",
    "recommended_filters": {
      "mold_type": "注塑模具",
      "maintenance_level": "一级保养",
      "standard_version": "V1.0"
    }
  },
  "meta": {
    "contract_version": "1.0",
    "source_type": "DEMO"
  },
  "request_id": "req-20260812-0010"
}
```

该接口不返回知识库正文，不虚构点检步骤。

---

## 13. 任务上下文聚合接口

为了减少比赛平台节点数量，P0 必须实现：

```http
GET /api/v1/molds/{mold_id}/task-context
```

参数：

```text
maintenance_level=一级保养
task_priority=HIGH
max_candidates=5
```

该接口只聚合查询结果，不创建任务、不派工、不发邮件。

返回内容：

- 模具详情；
- 保养状态；
- 匹配标准；
- 知识库检索上下文；
- 候选人员；
- 平台组装邮件所需的事实字段。

返回示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "mold": {
      "mold_id": "MOLD-2024-0891",
      "mold_name": "前壳体注塑模",
      "mold_type": "注塑模具",
      "mold_level": "A",
      "mold_category": "精密注塑模",
      "primary_location": "注塑车间",
      "secondary_location": "A区模具库",
      "production_line": "注塑一线"
    },
    "maintenance_status": {
      "current_count": 386500,
      "last_maintenance_count": 200000,
      "run_count_since_last": 186500,
      "maintenance_threshold": 200000,
      "usage_ratio": 0.9325,
      "usage_percent": 93.25,
      "remaining_count": 13500,
      "maintenance_status": "DUE_SOON",
      "alert_level": "YELLOW",
      "health_score": null,
      "health_score_status": "NOT_DEFINED",
      "rule_version": "DEMO_USAGE_RATIO_V1"
    },
    "standard": {
      "standard_id": "STD-INJECTION-A-L1",
      "maintenance_level": "一级保养",
      "standard_hours": 8,
      "version": "V1.0",
      "required_skills": [
        "注塑模具保养",
        "温控系统检查"
      ]
    },
    "knowledge_context": {
      "knowledge_tags": [
        "注塑模具",
        "一级保养",
        "模腔清洁",
        "导柱导套检查",
        "温控系统检查",
        "安全注意事项",
        "验收标准"
      ],
      "recommended_query": "A类精密注塑模 一级保养 点检项目 操作步骤 安全注意事项 验收标准"
    },
    "candidates": [
      {
        "employee_id": "EMP-0012",
        "employee_name": "张三",
        "email": "zhangsan@example.com",
        "team": "注塑一车间模具维保组",
        "production_line": "注塑一线",
        "skill_level": "SENIOR",
        "current_load": 0.45,
        "skill_match_ratio": 1.0,
        "same_line": true,
        "eligible": true,
        "reasons": [
          "技能完全匹配",
          "当前负荷低于80%",
          "与模具位于同一产线"
        ]
      }
    ],
    "platform_action": {
      "next_step": "RETRIEVE_KNOWLEDGE_AND_SEND_EMAIL",
      "django_has_dispatched": false,
      "django_has_sent_email": false
    }
  },
  "meta": {
    "contract_version": "1.0",
    "source_type": "DEMO"
  },
  "request_id": "req-20260812-0011"
}
```

`platform_action` 必须明确说明 Django 没有完成派工和邮件发送，避免误读。

---

## 14. 关键错误码

| 错误码 | HTTP 状态 | 含义 |
|---|---:|---|
| `AUTHENTICATION_REQUIRED` | 401 | 缺少 API Key |
| `INVALID_API_KEY` | 401 | API Key 无效 |
| `METHOD_NOT_ALLOWED` | 405 | 使用了非只读方法 |
| `MOLD_NOT_FOUND` | 404 | 模具不存在 |
| `STANDARD_NOT_FOUND` | 422 | 未找到适用标准 |
| `STANDARD_AMBIGUOUS` | 409 | 存在多个冲突标准 |
| `INVALID_STANDARD` | 422 | 标准阈值无效 |
| `INVALID_COUNT_DATA` | 422 | 模次数据不一致 |
| `INCOMPLETE_MOLD_DATA` | 422 | 模具关键字段缺失 |
| `SKILL_REQUIREMENT_NOT_CONFIGURED` | 422 | 标准未配置技能要求 |
| `NO_ELIGIBLE_STAFF` | 200 | 查询成功但无合格候选人，返回空数组和原因 |
| `INVALID_QUERY_PARAMETER` | 400 | 查询参数无效 |
| `RATE_LIMITED` | 429 | 请求超过限制 |
| `INTERNAL_ERROR` | 500 | 未预期错误 |

`NO_ELIGIBLE_STAFF` 不属于服务异常，使用 HTTP 200，平台应提示需要主管人工处理。

---

## 15. Django Admin

Admin 必须支持：

- 模具台账增删改查；
- 保养标准和版本管理；
- 活动预警策略管理；
- 技能管理；
- 员工和人员技能管理；
- 历史保养记录管理；
- 可选工单快照管理；
- 模具保养状态只读预览；
- 候选人员只读预览。

Admin 要求：

- 不与公共 API 共用路径；
- 使用强密码；
- 生产部署关闭公开注册；
- 支持通过环境变量配置 Admin 路径；
- 记录 Admin 修改日志；
- 比赛现场非必要不对公网开放，或限制访问 IP。

---

## 16. 演示数据设计

## 16.1 最小数据规模

- 至少 12 套模具；
- 至少 4 条保养标准；
- 至少 8 名模拟员工；
- 至少 10 个技能；
- 至少 20 条历史保养记录；
- 可选 6 条只读工单快照。

## 16.2 必须覆盖的场景

| 场景 | 数量要求 |
|---|---:|
| 绿色正常模具 | 至少 3 套 |
| 黄色即将到期模具 | 至少 3 套 |
| 红色超期模具 | 至少 2 套 |
| 停用或维修中模具 | 至少 1 套 |
| 缺少标准 | 至少 1 套 |
| 模次异常 | 至少 1 套 |
| 临界边界数据 | 至少 1 套 |

人员数据必须覆盖：

- 技能完全匹配；
- 技能部分匹配；
- 技能不足；
- 负荷超过 80%；
- 不在岗；
- 不同产线；
- 高级技师；
- 邮箱无效的异常人员。

## 16.3 固定主演示模具

```text
mold_id: MOLD-2024-0891
mold_name: 前壳体注塑模
mold_type: 注塑模具
mold_level: A
mold_category: 精密注塑模
cavity_count: 4
current_count: 386500
last_maintenance_count: 200000
run_count_since_last: 186500
maintenance_threshold: 200000
usage_percent: 93.25
alert_level: YELLOW
standard_hours: 8
primary_location: 注塑车间
secondary_location: A区模具库
production_line: 注塑一线
```

该示例来自原始方案，作为主演示数据固定保留。

除上述明确来源数据外，其他种子数据必须标注：

```text
data_source = DEMO
```

不得将模拟数值描述为企业真实生产数据。

## 16.4 管理命令

必须实现：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
```

要求：

- `seed_demo_data` 幂等；
- `reset_demo_data` 明确要求 `--confirm`；
- `verify_demo_data` 检查主演示模具、标准、人员和场景是否完整；
- 命令执行失败时返回非零退出码。

---

## 17. 安全设计

### 17.1 API 认证

- 使用 `X-API-Key`；
- API Key 只从环境变量读取；
- 不写入仓库、日志或示例响应；
- 使用常量时间比较；
- 支持至少一个活动 Key；
- 允许比赛前轮换 Key。

### 17.2 HTTPS

比赛平台必须通过：

```text
https://<domain>/api/v1
```

访问。

禁止在平台中填写：

```text
localhost
127.0.0.1
```

### 17.3 限流

参赛版建议：

```text
匿名请求：禁止
认证请求：60 次/分钟/API Key
突发上限：20 次/10 秒
```

限流值可配置。

### 17.4 日志与隐私

日志记录：

- request_id；
- 路径；
- 方法；
- 状态码；
- 响应耗时；
- 客户端 IP；
- 错误码。

日志不得记录：

- API Key；
- 完整邮箱地址；
- 管理员密码；
- 环境变量；
- 完整异常请求体中的敏感数据。

邮箱日志使用脱敏格式：

```text
zh***@example.com
```

### 17.5 Django 安全配置

生产环境必须：

- `DEBUG=False`；
- 配置 `ALLOWED_HOSTS`；
- 设置安全 `SECRET_KEY`；
- 启用安全 Cookie；
- 启用 HSTS；
- 配置 `SECURE_PROXY_SSL_HEADER`；
- 禁止目录列表；
- 禁止公开 SQLite 文件；
- 静态文件由 Nginx 提供；
- Admin 使用独立路径并限制访问。

---

## 18. 部署方案

## 18.1 虚拟服务器建议

| 项目 | 建议配置 |
|---|---|
| 操作系统 | Ubuntu 22.04/24.04 LTS |
| CPU | 2 核 |
| 内存 | 4 GB |
| 磁盘 | 40 GB |
| 公网 IP | 需要 |
| 域名 | 建议 |
| HTTPS | 必须 |
| 时区 | Asia/Shanghai |

## 18.2 Docker Compose 服务

```yaml
services:
  web:
    # Django + Gunicorn，内部监听 18080

  nginx:
    # 公开 80/443，反向代理到 web:18080
```

不部署：

```text
PostgreSQL
Redis
Celery
Mailpit
SMTP
```

## 18.3 数据持久化

SQLite 数据库必须挂载到持久化卷：

```text
/app/data/db.sqlite3
```

演示前备份：

```bash
cp data/db.sqlite3 data/backups/db-before-demo.sqlite3
```

## 18.4 环境变量

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<secret>
DJANGO_ALLOWED_HOSTS=<domain>,<ip>
DJANGO_ADMIN_URL=<non-default-path>/
MOLDGUARD_API_KEY=<secret>
MOLDGUARD_CONTRACT_VERSION=1.0
MOLDGUARD_SOURCE_TYPE=DEMO
MOLDGUARD_TIMEZONE=Asia/Shanghai
MOLDGUARD_DATABASE_PATH=/app/data/db.sqlite3
MOLDGUARD_LOG_LEVEL=INFO
MOLDGUARD_RATE_LIMIT=60/min
```

提供 `.env.example`，不得提交真实 `.env`。

## 18.5 启动检查

部署完成后必须执行：

```bash
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_demo_data
python manage.py verify_demo_data
```

随后从服务器外部访问：

```text
GET https://<domain>/api/v1/health
```

---

## 19. 测试计划

## 19.1 单元测试

必须覆盖：

- 标准精确匹配；
- 类别空值回退；
- 标准缺失；
- 标准冲突；
- 使用率计算；
- 剩余模次；
- 超期模次；
- 89.99% 绿色边界；
- 90.00% 黄色边界；
- 99.99% 黄色边界；
- 100.00% 红色边界；
- 模次倒退；
- 阈值为零；
- 停用模具排除；
- 技能匹配率；
- 80% 技能边界；
- 80% 负荷边界；
- 同产线排序；
- 高优先级高级技师排序；
- 稳定排序。

## 19.2 API 测试

必须覆盖：

- 无 API Key 返回 401；
- 错误 API Key 返回 401；
- GET 成功；
- POST/PUT/PATCH/DELETE 返回 405；
- 统一响应结构；
- request_id 回传与生成；
- 分页限制；
- 排序白名单；
- 参数校验；
- 错误码；
- 邮箱字段返回但日志脱敏；
- `task-context` 聚合一致性；
- OpenAPI 与实际响应一致。

## 19.3 管理命令测试

必须覆盖：

- 首次种子初始化；
- 重复初始化不重复创建；
- 重置需要确认；
- 验证命令能够发现缺失主演示数据；
- 主演示模具计算结果为 93.25% 和黄色。

## 19.4 集成测试

完整链路：

```text
查询 due 清单
→ 选择 MOLD-2024-0891
→ 查询 task-context
→ 获得知识检索标签
→ 获得候选人员和邮箱
→ 比赛平台检索知识库
→ 比赛平台生成并发送邮件
```

Django 验收范围截至 `task-context` 返回成功；知识检索和邮件送达由比赛平台验收。

## 19.5 部署测试

必须验证：

- 容器可以从空环境构建；
- 容器重启后数据保留；
- Nginx HTTPS 正常；
- Django 不直接暴露 18080；
- SQLite 文件无法通过 Web 下载；
- `/health` 外网可访问；
- Admin 未向非授权用户开放；
- 服务器重启后自动恢复。

## 19.6 质量门禁

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy --settings=config.settings.production
pytest
python manage.py spectacular --file docs/contracts/openapi.yaml --validate
python manage.py verify_demo_data
```

全部通过后才能进入比赛联调。

---

## 20. 性能与稳定性目标

参赛数据量下的工程目标：

- 常规单对象查询 P95 小于 500 ms；
- `task-context` P95 小于 1 秒；
- 连续 100 次主演示查询无 5xx；
- 服务器重启后 2 分钟内恢复可用；
- 演示前连续运行至少 4 小时无异常退出。

这些是工程验收目标，不替代原材料中未经验证的业务效益数据。

---

## 21. 开发阶段与 Stop Gate

## Phase 0：合同和演示规则冻结

### 任务

- 确认本计划为唯一权威基线；
- 创建 `docs/contracts/api-contract-v1.md`；
- 固定枚举、字段、错误码和响应结构；
- 固定主演示模具；
- 固定参赛预警策略；
- 固定 API Key 认证方式；
- 确认比赛平台能够访问公网 HTTPS。

### 交付物

- API 合同；
- 数据字典；
- 演示数据清单；
- 平台调用样例。

### Stop Gate A

只有字段、规则、错误码和接口路径全部明确后才能进入编码。

---

## Phase 1：工程骨架

### 任务

- 初始化 Django；
- 拆分 settings；
- 接入 DRF、django-filter、drf-spectacular；
- 实现 API Key 认证；
- 实现 request ID；
- 实现统一响应和异常；
- 实现 `/health` 和 `/meta`；
- 配置 Ruff 和 pytest。

### Stop Gate B

- `/health` 可访问；
- 无 Key 和错误 Key 测试通过；
- 所有非只读方法返回 405；
- OpenAPI 可以生成。

---

## Phase 2：模型、Admin 和演示数据

### 任务

- 实现 Mold；
- 实现 MaintenanceStandard；
- 实现 AlertPolicy；
- 实现 Skill、Employee、EmployeeSkill；
- 实现 MaintenanceRecord；
- 配置 Admin；
- 实现三条管理命令；
- 准备固定演示数据。

### Stop Gate C

- 迁移干净；
- Admin 可维护数据；
- `seed_demo_data` 幂等；
- `verify_demo_data` 通过；
- 主演示模具数据准确。

---

## Phase 3：标准匹配和状态计算

### 任务

- 实现标准匹配服务；
- 实现保养状态计算服务；
- 实现异常数据处理；
- 返回规则版本；
- 明确健康评分未定义。

### Stop Gate D

所有边界测试和异常测试通过，任何视图中不得复制规则计算代码。

---

## Phase 4：模具和标准 API

### 任务

- 模具列表；
- 模具详情；
- 保养状态；
- 待保养清单；
- 标准列表、详情和匹配；
- 分页、过滤、排序和文档。

### Stop Gate E

主演示模具通过 API 返回：

```text
186500 / 200000 = 93.25%
YELLOW
health_score = null
```

---

## Phase 5：人员候选、知识上下文和任务上下文

### 任务

- 人员和技能查询；
- 候选资格和稳定排序；
- `knowledge-context`；
- `task-context`；
- 邮箱字段和日志脱敏；
- 无候选人员处理。

### Stop Gate F

一次 `task-context` 请求能够返回平台检索知识和发送邮件所需的全部事实字段，同时明确 Django 未完成派工和发信。

---

## Phase 6：历史记录和基础统计

### 任务

- 历史记录查询；
- 总体统计；
- 工时统计；
- 模具历史；
- 可选只读工单快照。

### Stop Gate G

统计值可由明细数据复算，接口不生成趋势预测或虚构结论。

---

## Phase 7：部署和安全加固

### 任务

- Dockerfile；
- Docker Compose；
- Nginx；
- HTTPS；
- 持久化卷；
- 生产设置；
- 限流；
- 结构化日志；
- 运维文档；
- 备份和恢复测试。

### Stop Gate H

从外部网络通过 HTTPS 调用成功，内部端口和数据库文件不暴露，重启后数据保留。

---

## Phase 8：比赛平台联调和最终验收

### 任务

- 配置平台 API Key；
- 接入 `/molds/due`；
- 接入 `/task-context`；
- 使用知识上下文检索点检知识；
- 展示候选人员；
- 平台确认人员并发送邮件；
- 完成绿色、黄色、红色三类演示；
- 完成异常预案；
- 冻结比赛镜像和数据库备份。

### Stop Gate I

连续完成 3 次完整演示，无人工修改数据库、无 5xx、无错误知识匹配、邮件可到达测试邮箱。

---

## 22. 参赛演示脚本

建议演示时间：5—7 分钟。

### 第一步：系统定位

说明：

- 比赛平台负责智能交互、知识检索和邮件；
- Django 提供可解释、可验证的模拟业务数据；
- 关键模次、阈值、预警和候选资格不是由大模型生成。

### 第二步：执行今日巡检

平台调用：

```http
GET /api/v1/molds/due
```

展示黄色和红色模具清单。

### 第三步：查询主演示模具

平台调用：

```http
GET /api/v1/molds/MOLD-2024-0891/task-context
```

重点展示：

- 当前累计模次 386,500；
- 上次保养模次 200,000；
- 本周期运行 186,500；
- 阈值 200,000；
- 使用率 93.25%；
- 黄色预警；
- 标准工时 8 小时；
- 健康评分未定义而不是随意生成。

### 第四步：检索点检知识

平台使用 `knowledge_context` 中的标签检索：

- 点检项目；
- 操作步骤；
- 安全注意事项；
- 验收标准。

### 第五步：展示候选人员

展示：

- 技能匹配；
- 当前负荷；
- 同产线；
- 技师等级；
- 邮箱；
- 推荐原因。

由平台或主管完成最终确认。

### 第六步：发送邮件

比赛平台把：

- 模具任务；
- 保养状态；
- 点检知识；
- 安全要求；
- 验收标准；
- 截止时间；

发送至候选人员测试邮箱。

强调：邮件由比赛平台发送，不由 Django 发送。

### 第七步：异常示例

快速展示一个红色超期模具，或展示缺少标准时系统明确返回错误而不是让大模型猜测。

---

## 23. 比赛现场异常预案

| 异常 | 处理方式 |
|---|---|
| 公网域名无法解析 | 准备公网 IP HTTPS 备用地址 |
| HTTPS 证书异常 | 比赛前检查证书有效期，准备备用域名 |
| Django 容器异常 | `docker compose restart web` |
| 数据被修改 | 执行 `reset_demo_data --confirm` 后重新验证 |
| 平台请求超时 | 先访问 `/health`，再检查 Nginx 和 Gunicorn |
| API Key 错误 | 使用离线保存的比赛环境变量重新配置 |
| 无候选人员 | 展示排除原因，由主管人工处理 |
| 知识库无召回 | 使用 `recommended_query` 和结构化过滤标签重试 |
| 邮件发送失败 | 由比赛平台处理；准备测试邮箱和发送记录截图 |
| 网络完全不可用 | 准备接口响应、邮件结果和完整流程的录屏作为应急证据 |

录屏只能作为应急材料，正式演示仍以实时系统为主。

---

## 24. Definition of Done

服务器只有同时满足以下条件才可标记为 `READY_FOR_COMPETITION`：

### 24.1 范围

- [ ] Django 只提供查询 API；
- [ ] 不存在公共业务写接口；
- [ ] 不包含邮件、知识库、LLM、Celery 或 Redis；
- [ ] README、OpenAPI 和实现范围一致。

### 24.2 功能

- [ ] 模具、标准、状态、待保养、人员、知识上下文、任务上下文接口完成；
- [ ] 历史记录和基础统计完成；
- [ ] 主演示模具固定结果正确；
- [ ] 候选人员结果包含邮箱和可解释原因；
- [ ] 健康评分固定为未定义；
- [ ] 所有错误返回稳定错误码。

### 24.3 数据

- [ ] 演示数据覆盖所有规定场景；
- [ ] 管理命令幂等；
- [ ] 数据可一键重置；
- [ ] 所有模拟数据标记为 `DEMO`。

### 24.4 安全与部署

- [ ] API Key 生效；
- [ ] HTTPS 生效；
- [ ] `DEBUG=False`；
- [ ] 数据库和内部端口不暴露；
- [ ] 重启后数据保留；
- [ ] 无密钥提交到 Git。

### 24.5 测试

- [ ] Ruff 通过；
- [ ] Django check 通过；
- [ ] 全量 pytest 通过；
- [ ] OpenAPI 校验通过；
- [ ] 外部 HTTPS 冒烟测试通过；
- [ ] 连续 3 次完整平台演示通过。

### 24.6 文档

- [ ] README；
- [ ] API 合同；
- [ ] OpenAPI；
- [ ] 部署说明；
- [ ] 演示数据说明；
- [ ] 平台联调说明；
- [ ] 现场应急说明。

---

## 25. 开发与 Git 管理要求

### 25.1 分支

业务实现从：

```text
agent/django-query-api-v1
```

开始。

### 25.2 提交原则

- 每个 Phase 至少一个独立提交；
- 不在一个提交中混入无关格式化；
- 不直接在 `main` 上开发业务代码；
- 每个 Stop Gate 通过后更新计划状态；
- 实现完成后创建 Draft PR；
- 未完成平台联调前不标记 Ready for Review；
- 未经负责人明确批准不合并。

### 25.3 Codex 执行边界

交给 Codex 实施时必须明确：

1. 以本文件为唯一范围基线；
2. 不实现邮件；
3. 不实现工单写入；
4. 不实现健康评分；
5. 不猜测缺失保养阈值；
6. 不引入 Redis、Celery、前端或向量数据库；
7. 任何范围扩展先停下并请求负责人确认；
8. 每个 Stop Gate 完成后汇报测试、提交 SHA 和剩余风险。

---

## 26. 最终冻结矩阵

| 决策项 | 最终结论 |
|---|---|
| Django 是否发送邮件 | 否 |
| Django 是否保存知识库正文 | 否 |
| Django 是否调用 LLM | 否 |
| Django 是否创建工单 | 否 |
| Django 是否执行最终派工 | 否 |
| Django 是否记录报工和验收 | 否 |
| 是否使用 Celery/Redis | 否 |
| 公共 API 是否只读 | 是 |
| 是否提供候选人员 | 是，仅查询和排序 |
| 是否返回邮箱 | 是，供平台发信 |
| 是否提供知识检索标签 | 是 |
| 是否提供聚合任务上下文 | 是 |
| 是否实现健康评分 | 否，返回未定义 |
| 预警依据 | 保养周期使用率 |
| 参赛规则 | `<90%` 绿，`90%—<100%` 黄，`>=100%` 红 |
| 时间周期是否参与预警 | V1 否 |
| 数据库 | SQLite |
| 部署方式 | Docker Compose + Nginx + Gunicorn |
| 内部端口 | 18080 |
| 公网入口 | HTTPS 443 |
| 认证 | X-API-Key |
| 演示数据性质 | DEMO |
| 权威计划 | 本文件 V2.0 |

---

## 27. 最终结论

MoldGuard Django Server 的参赛定位已经冻结为：

> **面向比赛智能体平台的只读模具业务查询与规则计算服务。**

它通过确定性的模具数据、保养标准、预警计算、候选人员和知识检索标签，解决大模型在精确数字、业务规则和人员事实方面不应自由生成的问题；比赛平台则负责知识理解、任务组织和邮件发送。

后续开发不得重新扩展为完整工单系统，也不得将邮件、知识库或 LLM 逻辑迁入 Django。只有在比赛版稳定验收后，才能另行规划企业正式版写入接口和真实 MES/ERP 集成。
