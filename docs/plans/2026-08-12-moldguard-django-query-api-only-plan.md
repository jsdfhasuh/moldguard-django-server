# MoldGuard Django 查询 API 实现计划

- **状态**：待负责人审阅
- **版本**：V0.1
- **日期**：2026-08-12
- **目标仓库**：`moldguard-django-server`
- **计划性质**：Django 只读查询 API 实现基线

---

## 1. 计划定位

本计划只覆盖 Django 查询服务，不包含智能体平台、知识库、邮件发送、任务通知或流程编排。

Django 的唯一定位是：

> **向比赛平台提供稳定、结构化、可查询的模具业务数据 API。**

比赛平台负责：

- 用户自然语言交互；
- 工作流编排；
- 点检知识库检索；
- 预警报告生成；
- 派工邮件内容组装；
- 邮件发送；
- 任务通知和后续交互。

Django 负责：

- 保存和维护模拟模具数据；
- 保存保养标准；
- 保存人员、技能和负荷数据；
- 保存可供查询的历史保养记录；
- 根据查询条件返回模具、标准、人员和统计数据；
- 计算确定性的派生字段，例如距上次保养模次、周期使用率和是否到期；
- 为比赛平台知识库检索提供结构化标签和查询上下文；
- 提供 Django Admin，用于人工维护演示数据。

当前版本对比赛平台只开放查询接口，不提供工单创建、派工提交、报工、验收、邮件回写等写入接口。

---

## 2. 核心边界

### 2.1 Django 要实现

- 模具列表查询；
- 单套模具详情查询；
- 单套模具保养状态查询；
- 待保养模具清单查询；
- 保养标准查询；
- 人员列表查询；
- 可用人员候选查询；
- 历史保养记录查询；
- 可选的只读模拟工单查询；
- 基础统计查询；
- OpenAPI 文档；
- API Key 认证；
- 统一错误响应；
- Django Admin 数据维护；
- 演示数据初始化与重置命令。

### 2.2 Django 不实现

- 自然语言理解；
- 大模型调用；
- RAG、向量数据库或知识库；
- 邮件发送；
- 邮件模板；
- SMTP、Mailpit 或邮件 API；
- Celery、Redis 和后台任务；
- 定时巡检；
- 企业微信、钉钉或短信通知；
- 工单创建与状态流转；
- 派工写入；
- 报工与验收；
- 生产排程锁定；
- 复杂报表导出；
- 独立前端页面。

### 2.3 只读范围的影响

只读 API 可以支持以下比赛演示：

```text
查询模具
  ↓
获取保养状态
  ↓
获取知识检索标签
  ↓
查询候选人员
  ↓
比赛平台生成任务和邮件
  ↓
比赛平台发送邮件
```

但 Django 不会保存以下结果：

- 最终派给了谁；
- 邮件是否发送成功；
- 保养人员是否开工；
- 工单是否完成；
- 实际工时和验收结果。

如果后续需要展示完整闭环，再单独新增最小写入 API，不纳入本计划。

---

## 3. 总体架构

```text
┌──────────────────────────────────────┐
│            比赛智能体平台             │
│                                      │
│ 对话 / 工作流 / 知识库 / LLM / 邮件   │
└──────────────────┬───────────────────┘
                   │ HTTPS + JSON
                   ▼
┌──────────────────────────────────────┐
│       MoldGuard Django Query API     │
│                                      │
│ 模具查询 │ 标准查询 │ 人员查询        │
│ 状态计算 │ 历史记录 │ 基础统计        │
│                                      │
│       Django REST Framework          │
└──────────────────┬───────────────────┘
                   │
                   ▼
            SQLite 演示数据库
```

### 3.1 推荐技术栈

| 项目 | 建议 |
|---|---|
| Python | 3.12 |
| Django | 5.x |
| API 框架 | Django REST Framework |
| 查询过滤 | django-filter |
| API 文档 | drf-spectacular |
| 演示数据库 | SQLite |
| 测试 | pytest + pytest-django |
| 代码质量 | Ruff + Black |
| 生产运行 | Gunicorn |
| 反向代理 | Nginx |
| 部署方式 | Docker Compose 或单容器部署 |
| 时区 | Asia/Shanghai |

当前范围不需要 PostgreSQL、Redis 和 Celery。若后续接口并发增加或需要业务写入，再评估 PostgreSQL。

---

## 4. Django 工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── .env.example
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── common/             # 通用响应、异常、认证、请求ID
│   ├── molds/              # 模具台账与保养状态查询
│   ├── standards/          # 保养标准查询
│   ├── staff/              # 人员、技能和可用人员查询
│   ├── maintenance/        # 历史保养记录查询
│   ├── workorders/         # 可选：只读模拟工单查询
│   └── analytics/          # 基础统计查询
├── data/
│   └── demo/               # 演示种子数据
├── docs/
│   ├── plans/
│   ├── contracts/
│   └── examples/
├── tests/
├── Dockerfile
├── docker-compose.yml
└── README.md
```

第一版不开发 Vue、React 等前端。数据维护直接使用 Django Admin。

---

## 5. 核心数据模型

## 5.1 Mold：模具台账

建议字段：

- `mold_id`：模具编号，唯一；
- `mold_name`：模具名称；
- `mold_type`：注塑模具、钣金模具等；
- `mold_level`：模具等级；
- `mold_category`：模具类别；
- `cavity_count`：腔数；
- `current_count`：当前累计生产模次；
- `last_maintenance_count`：上次保养时累计模次；
- `last_maintenance_time`：上次保养时间；
- `primary_location`：一级位置；
- `secondary_location`：二级位置；
- `production_line`：所属产线；
- `status`：生产中、库存、维修、停用；
- `created_at`；
- `updated_at`。

## 5.2 MaintenanceStandard：保养标准

建议字段：

- `standard_id`；
- `mold_type`；
- `mold_level`；
- `mold_category`；
- `maintenance_level`；
- `maintenance_threshold`：标准保养模次；
- `maintenance_days`：可选时间周期；
- `standard_hours`；
- `required_skills`；
- `version`；
- `effective_from`；
- `is_active`。

精确保养阈值、标准工时和规则版本必须由 Django 数据库返回，不依赖知识库猜测。

## 5.3 Employee：人员信息

建议字段：

- `employee_id`；
- `employee_name`；
- `team`；
- `production_line`；
- `skill_level`；
- `current_load`，范围 `0.00—1.00`；
- `on_duty`；
- `available`；
- `email`：仅作为查询结果返回，Django 不负责发送邮件。

## 5.4 Skill 与 EmployeeSkill

用于表示：

- 技能名称；
- 员工掌握的技能；
- 技能等级；
- 是否有效。

## 5.5 MaintenanceRecord：历史保养记录

建议字段：

- `record_id`；
- `mold`；
- `maintenance_level`；
- `maintenance_time`；
- `maintenance_count`；
- `standard_hours`；
- `actual_hours`；
- `maintainer_name`；
- `result`；
- `remarks`。

该模型只用于查询历史数据，不在本计划中提供新增或修改 API。

## 5.6 WorkOrderSnapshot：可选只读模拟工单

如果比赛平台需要展示“待派工清单”或“当前工单”，可以增加只读模拟工单表：

- `work_order_id`；
- `mold_id`；
- `status`；
- `priority`；
- `estimated_hours`；
- `required_finish_at`；
- `assigned_employee_id`；
- `created_at`。

该表仅由 Django Admin 或种子数据维护，不对比赛平台开放写入接口。

---

## 6. 保养状态计算

## 6.1 基础计算

```python
run_count_since_last = current_count - last_maintenance_count
usage_ratio = run_count_since_last / maintenance_threshold
usage_percent = usage_ratio * 100
```

返回字段：

- `run_count_since_last`；
- `maintenance_threshold`；
- `usage_ratio`；
- `usage_percent`；
- `remaining_count`；
- `maintenance_status`；
- `alert_level`。

## 6.2 第一版演示规则

原材料没有给出健康评分的明确计算公式，因此第一版不实现 `health_score`。

暂定演示规则：

| 使用率 | maintenance_status | alert_level |
|---:|---|---|
| `< 90%` | `NORMAL` | `GREEN` |
| `90%—<100%` | `DUE_SOON` | `YELLOW` |
| `≥100%` | `OVERDUE` | `RED` |

该阈值属于实施建议，应由业务负责人确认后写入配置。

## 6.3 异常场景

- 当前累计模次小于上次保养模次：返回 `INVALID_COUNT_DATA`；
- 找不到匹配标准：返回 `STANDARD_NOT_FOUND`；
- 标准阈值为零或空：返回 `INVALID_STANDARD`；
- 模具停用：返回状态，但不进入待保养清单；
- 数据不完整：明确返回缺失字段，不自行补值。

---

## 7. API 设计

统一前缀：

```text
/api/v1
```

统一响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req-20260812-0001"
}
```

## 7.1 健康检查

```http
GET /api/v1/health
```

返回应用和数据库状态。

## 7.2 模具查询

```http
GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/due
```

支持过滤：

- `mold_type`；
- `mold_level`；
- `production_line`；
- `status`；
- `alert_level`；
- `page`；
- `page_size`。

## 7.3 保养标准查询

```http
GET /api/v1/maintenance-standards
GET /api/v1/maintenance-standards/{standard_id}
GET /api/v1/maintenance-standards/match
```

匹配参数：

```text
mold_type
mold_level
mold_category
maintenance_level
```

## 7.4 人员查询

```http
GET /api/v1/staff
GET /api/v1/staff/{employee_id}
GET /api/v1/staff/available
```

可用人员查询参数：

```text
skills
production_line
max_load
skill_level
on_duty
```

返回候选人时只提供事实字段和规则命中说明，不由 Django 自动完成派工。

## 7.5 历史保养记录查询

```http
GET /api/v1/maintenance-records
GET /api/v1/maintenance-records/{record_id}
```

支持过滤：

```text
mold_id
start_date
end_date
maintenance_level
maintainer_name
result
```

## 7.6 可选只读工单查询

```http
GET /api/v1/work-orders
GET /api/v1/work-orders/{work_order_id}
```

只查询模拟工单，不创建、不派工、不改变状态。

## 7.7 知识库检索上下文

```http
GET /api/v1/molds/{mold_id}/knowledge-context
```

该接口为比赛平台返回知识库检索标签，例如：

```json
{
  "mold_id": "MOLD-2024-0891",
  "mold_type": "注塑模具",
  "mold_level": "A",
  "mold_category": "精密注塑模",
  "maintenance_level": "一级保养",
  "standard_id": "STD-INJECTION-A-L1",
  "required_skills": [
    "注塑模具保养",
    "温控系统检查"
  ],
  "knowledge_keywords": [
    "模腔清洁",
    "排气槽检查",
    "导柱导套检查",
    "温控系统检查"
  ]
}
```

比赛平台使用这些字段检索点检知识并生成邮件，Django 不接收也不发送知识内容。

## 7.8 基础统计查询

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/maintenance-hours
GET /api/v1/analytics/mold-status
```

统计只基于数据库中的模拟或历史数据，不由 Django 生成自然语言结论。

---

## 8. 单套模具状态响应示例

```http
GET /api/v1/molds/MOLD-2024-0891/maintenance-status
```

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
      "cavity_count": 4,
      "production_line": "注塑一线",
      "primary_location": "注塑车间",
      "secondary_location": "A区模具库",
      "status": "IN_PRODUCTION"
    },
    "standard": {
      "standard_id": "STD-INJECTION-A-L1",
      "maintenance_level": "一级保养",
      "maintenance_threshold": 200000,
      "standard_hours": 8,
      "version": "V1.0"
    },
    "calculation": {
      "current_count": 386500,
      "last_maintenance_count": 200000,
      "run_count_since_last": 186500,
      "usage_ratio": 0.9325,
      "usage_percent": 93.25,
      "remaining_count": 13500,
      "maintenance_status": "DUE_SOON",
      "alert_level": "YELLOW"
    },
    "knowledge_context": {
      "maintenance_level": "一级保养",
      "required_skills": [
        "注塑模具保养",
        "温控系统检查"
      ],
      "knowledge_keywords": [
        "模腔清洁",
        "排气槽检查",
        "导柱导套检查",
        "温控系统检查"
      ]
    }
  },
  "request_id": "req-20260812-0001"
}
```

---

## 9. API 安全与通用约定

## 9.1 认证

比赛平台请求头：

```http
X-API-Key: <secret>
```

第一版使用单个服务级 API Key 即可。

## 9.2 请求追踪

支持：

```http
X-Request-ID: <平台生成ID>
```

未传入时由 Django 自动生成，并在响应中返回。

## 9.3 只读权限

对比赛平台开放的 API 只允许：

```text
GET
HEAD
OPTIONS
```

`POST`、`PUT`、`PATCH`、`DELETE` 返回 `405 Method Not Allowed`。

Django Admin 通过独立管理员账号维护数据，不与比赛平台 API Key 共用权限。

## 9.4 分页

默认：

```text
page_size = 20
```

最大：

```text
page_size = 100
```

## 9.5 错误码

| 错误码 | 含义 |
|---|---|
| `INVALID_API_KEY` | API Key 无效 |
| `MOLD_NOT_FOUND` | 模具不存在 |
| `STANDARD_NOT_FOUND` | 找不到匹配保养标准 |
| `INVALID_COUNT_DATA` | 模次数据异常 |
| `INVALID_STANDARD` | 标准阈值无效 |
| `EMPLOYEE_NOT_FOUND` | 员工不存在 |
| `INVALID_QUERY_PARAM` | 查询参数错误 |
| `INTERNAL_ERROR` | 服务内部错误 |

---

## 10. Django Admin 设计

Django Admin 仅用于维护模拟数据，不作为比赛展示主界面。

需要配置：

- 模具台账列表、搜索、过滤；
- 保养标准列表、版本和启停状态；
- 员工、技能和负荷维护；
- 历史保养记录维护；
- 可选模拟工单维护；
- 批量导入或导出演示数据；
- 明确标记必填字段和唯一字段。

建议搜索字段：

```text
模具编号
模具名称
员工编号
员工姓名
标准编号
工单编号
```

---

## 11. 演示数据计划

至少准备 12 套模具：

| 类型 | 数量 | 目的 |
|---|---:|---|
| 绿色正常模具 | 4 | 展示未到保养周期 |
| 黄色临近模具 | 3 | 展示即将保养 |
| 红色超期模具 | 3 | 展示已超过阈值 |
| 数据异常模具 | 1 | 展示异常校验 |
| 缺少标准模具 | 1 | 展示标准缺失处理 |

至少准备 8 名员工：

- 同产线、技能匹配、低负荷人员；
- 同产线、技能匹配、高负荷人员；
- 不同产线、技能匹配人员；
- 技能不匹配人员；
- 未在岗人员；
- 高级技师与普通技师。

种子数据命令：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data
```

---

## 12. 测试计划

## 12.1 模型与规则测试

- 模具编号唯一性；
- 保养标准匹配；
- 模次差值计算；
- 使用率计算；
- 绿、黄、红边界；
- 当前模次小于上次保养模次；
- 保养阈值为零；
- 标准版本启停；
- 员工负荷范围校验。

## 12.2 API 测试

- 未提供 API Key；
- API Key 错误；
- 查询存在模具；
- 查询不存在模具；
- 多条件过滤；
- 分页；
- 排序；
- 可用人员筛选；
- 知识上下文返回；
- 统计结果；
- 非 GET 方法被拒绝；
- 响应包含 request_id。

## 12.3 关键验收用例

| 编号 | 场景 | 预期结果 |
|---|---|---|
| T01 | 查询不存在模具 | 返回 `MOLD_NOT_FOUND` |
| T02 | 使用率 50% | `GREEN / NORMAL` |
| T03 | 使用率 93.25% | `YELLOW / DUE_SOON` |
| T04 | 使用率 102.5% | `RED / OVERDUE` |
| T05 | 缺少保养标准 | 返回 `STANDARD_NOT_FOUND` |
| T06 | 当前模次小于上次保养模次 | 返回 `INVALID_COUNT_DATA` |
| T07 | 查询最大负荷 80% 的可用人员 | 只返回低于或等于约定阈值的人选 |
| T08 | POST 创建工单 | 返回 405，不创建数据 |
| T09 | 查询知识上下文 | 返回稳定标签供平台检索知识库 |
| T10 | 多次查询相同模具 | 结果一致，除 request_id 外不漂移 |

---

## 13. 分阶段实施计划

## Phase 0：需求与字段冻结

**建议时间：0.5—1个工作日**

任务：

- 确认模具字段；
- 确认保养标准字段；
- 确认人员字段；
- 确认保养阈值；
- 确认黄、红预警边界；
- 确认比赛平台 API 调用格式；
- 确认知识库检索所需标签；
- 冻结 `/api/v1` 路径。

交付物：

```text
docs/contracts/api-contract.md
docs/contracts/data-dictionary.md
docs/contracts/demo-rules.md
```

## Phase 1：Django 基础工程

**建议时间：1个工作日**

任务：

- 创建 Django 项目；
- 接入 DRF；
- 配置 SQLite；
- 配置统一响应；
- 配置 API Key；
- 配置 request_id；
- 配置 OpenAPI；
- 实现健康检查；
- 配置测试框架。

验收：

```http
GET /api/v1/health
```

返回应用和数据库正常。

## Phase 2：模型与 Admin

**建议时间：1—2个工作日**

任务：

- 实现 Mold；
- 实现 MaintenanceStandard；
- 实现 Employee、Skill、EmployeeSkill；
- 实现 MaintenanceRecord；
- 可选实现 WorkOrderSnapshot；
- 配置 Django Admin；
- 编写种子数据命令。

验收：

- 管理员可以维护全部模拟数据；
- 重置命令可以恢复固定演示状态。

## Phase 3：模具与标准查询 API

**建议时间：1—2个工作日**

任务：

- 模具列表和详情；
- 标准列表和匹配；
- 保养状态计算服务；
- 待保养清单；
- 过滤、排序和分页；
- 异常数据处理。

验收：

- 绿色、黄色、红色示例结果正确；
- 缺少标准时不猜测结果。

## Phase 4：人员与知识上下文 API

**建议时间：1个工作日**

任务：

- 人员列表和详情；
- 可用人员过滤；
- 技能与产线筛选；
- 负荷筛选；
- 知识库检索上下文接口。

验收：

- 比赛平台能根据返回标签检索对应点检要求；
- Django 不自动派工、不发送邮件。

## Phase 5：历史与统计查询 API

**建议时间：1个工作日**

任务：

- 历史保养记录查询；
- 可选模拟工单查询；
- 工时和模具状态统计；
- 日期范围过滤。

验收：

- 统计结果与数据库明细一致；
- API 只返回数据，不生成管理结论。

## Phase 6：测试、部署与平台联调

**建议时间：1—2个工作日**

任务：

- 完成单元和 API 测试；
- 生成 OpenAPI 文档；
- 创建 Dockerfile；
- 配置 Gunicorn 和 Nginx；
- 配置 HTTPS；
- 从比赛平台实际调用；
- 验证超时和错误分支；
- 编写部署和重置说明。

验收：

- 比赛平台可通过公网 HTTPS 查询全部 P0 API；
- 非 GET 请求被拒绝；
- 多次演示可通过重置命令恢复数据。

---

## 14. 预计周期

| 范围 | 预计时间 |
|---|---:|
| 最小可用查询 API | 4—5个工作日 |
| 包含人员、历史和统计 | 6—8个工作日 |
| 完成部署与比赛平台联调 | 7—10个工作日 |

该估算按一名熟悉 Django 的开发人员计算，不包含知识库整理、比赛平台工作流和邮件模板搭建。

---

## 15. 部署计划

### 15.1 虚拟服务器

| 项目 | 建议 |
|---|---|
| 操作系统 | Ubuntu 22.04 / 24.04 |
| CPU | 1—2核 |
| 内存 | 2GB 起，建议 4GB |
| 磁盘 | 20GB 起 |
| 公网访问 | 需要 |
| HTTPS | 建议必须配置 |
| 时区 | Asia/Shanghai |

### 15.2 服务组成

最简部署只需要：

```text
Nginx
Gunicorn
Django
SQLite 数据卷
```

不需要：

```text
Redis
Celery
SMTP
Mailpit
向量数据库
独立前端
```

### 15.3 端口

| 端口 | 用途 | 公网开放 |
|---:|---|---|
| 443 | HTTPS API | 是 |
| 80 | HTTP 跳转 HTTPS | 可选 |
| 18080 | Django/Gunicorn 内部端口 | 否 |

比赛平台访问：

```text
https://你的域名/api/v1
```

---

## 16. 需要提供的业务资料

### 16.1 模具数据

- 模具编号；
- 模具名称；
- 模具类型；
- 模具等级；
- 模具类别；
- 腔数；
- 当前累计模次；
- 上次保养模次；
- 上次保养时间；
- 一级位置；
- 二级位置；
- 所属产线；
- 当前状态。

### 16.2 保养标准

- 注塑模具保养阈值；
- 钣金模具保养阈值；
- 各模具等级适用标准；
- 一、二、三级保养划分；
- 标准工时；
- 所需技能；
- 标准版本与生效日期；
- 红、黄、绿边界。

### 16.3 人员数据

- 员工编号；
- 姓名；
- 邮箱；
- 班组；
- 所属产线；
- 技能；
- 技能等级；
- 当前负荷；
- 是否在岗；
- 是否可用。

### 16.4 平台联调信息

- 比赛平台支持的 HTTP 方法；
- 请求头配置方式；
- JSON 字段映射方式；
- 单次请求超时；
- 是否支持分页循环；
- 知识库过滤标签；
- 平台邮件节点需要的人员字段。

---

## 17. 完成定义

本计划完成的标准是：

1. Django 只提供查询 API；
2. 对比赛平台不开放任何业务写入接口；
3. 模具、保养标准、人员和历史记录可通过 Django Admin 维护；
4. 单套模具状态和待保养清单可以稳定查询；
5. 保养状态计算有明确规则和异常校验；
6. 人员候选查询只返回数据，不完成派工；
7. 知识上下文接口能为比赛平台知识库检索提供稳定标签；
8. Django 不发送邮件、不调用 LLM、不管理知识库；
9. OpenAPI 文档完整；
10. 核心 API 有自动化测试；
11. 服务可通过公网 HTTPS 被比赛平台访问；
12. 演示数据可以一键初始化和重置。

---

## 18. 后续扩展边界

只有在比赛演示确实需要闭环状态时，才另行设计写入 API，例如：

```http
POST /api/v2/work-orders
POST /api/v2/work-orders/{id}/assign
POST /api/v2/work-orders/{id}/complete
```

这些接口不应提前混入当前 `/api/v1` 只读计划，避免范围膨胀和联调复杂化。
