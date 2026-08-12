# MoldGuard Django 查询 API 完整实现计划

- **状态**：`IMPLEMENTATION_READY`
- **版本**：V1.0
- **日期**：2026-08-12
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **权威范围**：Django 只提供结构化查询 API；邮件、知识库、LLM 和流程编排由比赛平台或其他外部渠道实现
- **替代关系**：本文件替代仓库中早期“完整业务版”设想，作为后续 Django 编码的唯一实施基线

---

## 1. 计划目标

本项目为“模具保养智能预警与管理智能体”提供一个外部 Django 模拟数据服务。

Django 的唯一业务定位是：

> **向比赛智能体平台提供稳定、可解释、可验证的模具业务查询 API。**

完整演示链路如下：

```text
用户在比赛平台输入模具编号或巡检要求
        ↓
比赛平台调用 Django 查询模具、保养标准和保养状态
        ↓
Django 返回确定性计算结果及知识检索标签
        ↓
比赛平台检索点检知识库
        ↓
比赛平台查询 Django 返回的候选人员和邮箱
        ↓
比赛平台组装任务内容并发送邮件
```

Django 不参与邮件生成和发送，也不保存最终派工、邮件送达、开工、报工或验收状态。

---

## 2. 需求依据与边界

### 2.1 原始方案明确支持的业务数据

原始方案中，模具状态查询涉及以下字段：

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

原始方案还提出人员匹配所需事实：

- 员工编号和姓名；
- 技能匹配度；
- 当前负荷；
- 所在产线；
- 技师等级；
- 是否在岗；
- 接收任务所需邮箱。

知识库包含保养标准、故障案例、工时定额、备件手册和操作指导书。Django 不保存这些文档正文，只返回适合比赛平台检索知识库的结构化标签。

### 2.2 原始材料没有完整定义的内容

以下内容不能在代码中自行猜测：

1. “健康评分”的计算公式；
2. 健康评分 72 分与保养周期使用率 93.25% 之间的换算关系；
3. 图片中不同注塑模具、钣金模具等级对应的全部准确保养阈值；
4. 时间周期是否参与最终红黄绿判断，以及如何与生产模次合并；
5. 人员技能、负荷、产线和技师等级的综合权重；
6. “模具寿命缩短 30%—50%”“2—4 小时压缩至 10 秒以内”等指标的测试依据。

因此第一版必须采用可配置、可追溯的规则，不把上述未确认内容写成固定事实。

### 2.3 Django 必须实现

- 模具列表、详情和状态查询；
- 保养标准列表、详情和精确匹配；
- 距上次保养累计模次计算；
- 保养周期使用率、剩余模次和是否到期计算；
- 黄色、红色待保养模具清单；
- 知识库检索上下文标签；
- 人员、技能、负荷和在岗信息查询；
- 确定性的候选人员筛选和排序；
- 历史保养记录查询；
- 基础统计查询；
- 可选的只读模拟工单快照查询；
- API Key 认证、统一响应、请求 ID、分页和过滤；
- OpenAPI 文档；
- Django Admin 演示数据维护；
- 演示数据初始化、校验、重置和导出命令；
- 单元测试、接口测试、契约测试和部署配置。

### 2.4 Django 明确不实现

- 自然语言理解和大模型调用；
- RAG、Embedding、Rerank、向量数据库和知识库正文；
- 邮件模板、SMTP、邮件 API、附件生成和邮件发送；
- Celery、Redis、后台邮件重试；
- 企业微信、钉钉或短信通知；
- 定时巡检任务；
- 工单创建、派工写入、改派、开工、暂停、恢复、报工、验收和关闭；
- 邮件发送结果回写；
- 自动锁定排产；
- Excel、Word 报表导出；
- 独立 Vue、React 或其他前端。

### 2.5 写入边界

比赛平台对 `/api/v1` 只允许：

```text
GET
HEAD
OPTIONS
```

以下方法统一返回 `405 Method Not Allowed`：

```text
POST
PUT
PATCH
DELETE
```

Django 数据只允许通过以下内部方式维护：

- Django Admin；
- Django management command；
- 数据迁移；
- 后续真实 MES/ERP 只读适配器。

---

## 3. 总体架构

```text
┌────────────────────────────────────────────┐
│              比赛智能体平台                 │
│                                            │
│ 对话 │ 工作流 │ 知识库 │ LLM │ 邮件发送     │
└───────────────────┬────────────────────────┘
                    │ HTTPS / JSON / GET
                    ▼
┌────────────────────────────────────────────┐
│         MoldGuard Django Query API         │
│                                            │
│ 模具 │ 标准 │ 状态计算 │ 人员 │ 历史 │ 统计 │
│                                            │
│          Django REST Framework             │
└───────────────────┬────────────────────────┘
                    │ Django ORM
                    ▼
             SQLite / PostgreSQL
```

架构原则：

1. **数据事实归 Django**：模次、阈值、工时、人员和邮箱以 Django 返回为准；
2. **内容生成归平台**：预警报告、点检知识、邮件正文由比赛平台生成；
3. **规则确定性**：Django 不调用 LLM，不产生不可解释的业务判断；
4. **只读契约稳定**：平台可重复调用 GET，不产生副作用；
5. **模拟数据可替换**：以后可替换数据来源，但保持 `/api/v1` 输出契约不变。

---

## 4. 技术基线

### 4.1 推荐版本

| 组件 | 版本基线 | 说明 |
|---|---|---|
| Python | 3.12.x | 兼容性稳定，便于 Windows 和 Linux 开发 |
| Django | `>=5.2,<5.3` | 使用 Django 5.2 LTS 系列 |
| Django REST Framework | `>=3.16,<3.17` | REST API、序列化、权限和分页 |
| django-filter | 当前兼容稳定版 | 查询过滤 |
| drf-spectacular | 当前兼容稳定版 | OpenAPI 3 文档 |
| pytest | 当前兼容稳定版 | 测试框架 |
| pytest-django | 当前兼容稳定版 | Django 测试集成 |
| Ruff | 当前兼容稳定版 | lint 和格式检查 |
| Gunicorn | 当前兼容稳定版 | Linux 生产运行 |
| Nginx | 系统稳定版 | HTTPS 和反向代理 |

依赖必须在首次实现时生成锁定文件，不能仅使用无上限的 `latest`。

### 4.2 数据库决策

第一阶段比赛演示默认使用 SQLite：

- 数据量小；
- 查询为主；
- 部署和重置简单；
- 无需单独数据库服务。

出现以下情况时再切换 PostgreSQL：

- 多实例部署；
- 频繁后台写入；
- 大量历史数据；
- 多人同时维护 Admin；
- 接入真实业务系统。

数据库切换不得改变 API 契约。

### 4.3 第一版不引入的基础设施

- Redis；
- Celery；
- Kafka；
- Elasticsearch；
- 向量数据库；
- Kubernetes。

---

## 5. 仓库目录结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── uv.lock                         # 或项目选定的其他锁文件
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── __init__.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
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
│   │   ├── responses.py
│   │   └── validators.py
│   ├── molds/
│   │   ├── models.py
│   │   ├── admin.py
│   │   ├── serializers.py
│   │   ├── filters.py
│   │   ├── services.py
│   │   ├── selectors.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── standards/
│   ├── staff/
│   ├── maintenance/
│   ├── workorders/                 # P1，只读快照
│   └── analytics/
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
│   └── examples/
├── tests/
│   ├── unit/
│   ├── api/
│   ├── contract/
│   └── integration/
├── scripts/
├── Dockerfile
├── docker-compose.yml
└── nginx/
    └── default.conf
```

第一版不开发独立网页。内部数据维护使用 Django Admin。

---

## 6. 领域模型设计

## 6.1 Mold：模具台账

建议字段：

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `mold_id` | CharField | 唯一，业务模具编号 |
| `mold_name` | CharField | 必填 |
| `mold_type` | CharField | 注塑模具、钣金模具等 |
| `mold_level` | CharField | A、B 或业务等级 |
| `mold_category` | CharField | 精密注塑模等 |
| `cavity_count` | PositiveIntegerField | 可为空 |
| `current_count` | PositiveBigIntegerField | 当前累计生产模次 |
| `last_maintenance_count` | PositiveBigIntegerField | 上次保养时累计模次 |
| `last_maintenance_time` | DateTimeField | 上次保养时间 |
| `primary_location` | CharField | 一级位置 |
| `secondary_location` | CharField | 二级位置 |
| `production_line` | CharField | 所属产线 |
| `status` | CharField | `IN_PRODUCTION/STORAGE/REPAIR/INACTIVE` |
| `data_source` | CharField | `DEMO/MES/IMPORT` |
| `created_at` | DateTimeField | 自动记录 |
| `updated_at` | DateTimeField | 自动更新 |

数据库约束：

- `mold_id` 唯一；
- 所有模次不得小于 0；
- 默认要求 `current_count >= last_maintenance_count`；
- 发现计数器清零或换表时，不能静默修复，应由 Admin 明确更新基准数据；
- 为 `mold_type`、`mold_level`、`production_line`、`status` 建索引。

## 6.2 MaintenanceStandard：保养标准

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `standard_id` | CharField | 唯一标准编号 |
| `mold_type` | CharField | 适用模具类型 |
| `mold_level` | CharField | 适用等级 |
| `mold_category` | CharField | 可选，适用类别 |
| `maintenance_level` | CharField | 一级、二级、三级保养 |
| `maintenance_threshold` | PositiveBigIntegerField | 标准保养模次 |
| `maintenance_days` | PositiveIntegerField | 可选，时间周期 |
| `standard_hours` | DecimalField | 标准工时 |
| `required_skills` | ManyToManyField | 所需技能 |
| `knowledge_keywords` | JSONField | 知识库检索关键词 |
| `version` | CharField | 标准版本 |
| `effective_from` | DateField | 生效日期 |
| `effective_to` | DateField | 可为空 |
| `is_active` | BooleanField | 是否启用 |
| `created_at` / `updated_at` | DateTimeField | 审计时间 |

规则：

- 同一组匹配维度只能存在一个当前有效标准；
- 标准阈值和标准工时必须大于 0；
- 标准变更必须产生新版本，不覆盖已失效版本；
- `knowledge_keywords` 只保存检索标签，不保存知识库正文。

## 6.3 AlertPolicy：预警策略

为避免把暂定阈值写死，增加可配置策略：

| 字段 | 示例 | 说明 |
|---|---|---|
| `policy_id` | `POLICY-COUNT-V1` | 唯一编号 |
| `yellow_ratio` | `0.90` | 黄色起点 |
| `red_ratio` | `1.00` | 红色起点 |
| `use_time_dimension` | `false` | 第一版默认关闭时间维度 |
| `version` | `V1` | 规则版本 |
| `is_active` | `true` | 当前有效 |

第一版演示可使用 90% 和 100% 两个阈值，但必须在 Admin 中可查看、可修改，并在 API 结果中返回策略版本。

## 6.4 Skill：技能

字段：

- `skill_code`，唯一；
- `skill_name`；
- `description`；
- `is_active`。

## 6.5 Employee：人员

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `employee_id` | CharField | 唯一工号 |
| `employee_name` | CharField | 姓名 |
| `email` | EmailField | 供比赛平台发邮件 |
| `team` | CharField | 班组 |
| `production_line` | CharField | 所在产线 |
| `skill_level` | CharField | 初级、中级、高级技师等 |
| `current_load` | DecimalField | `0.00—1.00` |
| `on_duty` | BooleanField | 是否在岗 |
| `available` | BooleanField | 是否允许候选 |
| `created_at` / `updated_at` | DateTimeField | 审计时间 |

约束：

- `employee_id` 唯一；
- 邮箱格式合法；
- `current_load` 必须在 0 和 1 之间；
- 演示种子数据不得使用无授权的真实员工邮箱。

## 6.6 EmployeeSkill：员工技能

字段：

- `employee`；
- `skill`；
- `proficiency_level`；
- `valid_from`；
- `valid_until`；
- `is_active`。

同一员工与技能组合唯一。

## 6.7 MaintenanceRecord：历史保养记录

字段：

- `record_id`，唯一；
- `mold`；
- `maintenance_level`；
- `maintenance_time`；
- `maintenance_count`；
- `standard_hours`；
- `actual_hours`；
- `maintainer_employee_id`；
- `maintainer_name`；
- `result`；
- `abnormal_summary`；
- `remarks`；
- `source`。

该模型只通过 Admin、导入命令或未来数据适配器写入，比赛平台只查询。

## 6.8 WorkOrderSnapshot：只读模拟工单快照（P1）

仅在比赛平台确实需要查询“待派工清单”时实现：

- `work_order_id`；
- `mold`；
- `status`；
- `priority`；
- `maintenance_level`；
- `estimated_hours`；
- `required_finish_at`；
- `assigned_employee_id`；
- `assigned_employee_name`；
- `created_at`；
- `updated_at`。

它不是工单状态机，不开放任何状态修改 API。

---

## 7. 核心业务服务

业务计算必须放在 service/selector 层，不写在 serializer 的展示逻辑中。

## 7.1 MaintenanceStandardMatcher

输入：

- 模具类型；
- 模具等级；
- 模具类别；
- 保养等级；
- 查询日期。

规则：

1. 只匹配当前日期有效且 `is_active=true` 的标准；
2. 默认要求精确匹配；
3. 不进行模糊匹配；
4. 不静默使用其他模具类别的标准；
5. 找不到标准返回 `STANDARD_NOT_FOUND`；
6. 找到多个有效标准返回 `AMBIGUOUS_STANDARD`；
7. 所有响应返回 `standard_id` 和 `standard_version`。

若业务以后需要“类别为空时使用通用标准”，必须作为独立、可测试的回退规则加入，不能在第一版隐式实现。

## 7.2 MaintenanceStatusCalculator

基础计算：

```python
run_count_since_last = current_count - last_maintenance_count
usage_ratio = run_count_since_last / maintenance_threshold
usage_percent = usage_ratio * 100
remaining_count = max(maintenance_threshold - run_count_since_last, 0)
```

第一版红黄绿规则：

| 条件 | `maintenance_status` | `alert_level` |
|---|---|---|
| `usage_ratio < yellow_ratio` | `NORMAL` | `GREEN` |
| `yellow_ratio <= usage_ratio < red_ratio` | `DUE_SOON` | `YELLOW` |
| `usage_ratio >= red_ratio` | `OVERDUE` | `RED` |

必须返回：

- 当前累计模次；
- 上次保养模次；
- 距上次保养运行模次；
- 标准阈值；
- 使用率；
- 剩余模次；
- 预警等级；
- 标准工时；
- 标准编号和版本；
- 预警策略编号和版本；
- 计算时间。

健康评分处理：

- 第一版不计算健康评分；
- API 可返回 `health_score: null` 和 `health_score_status: "NOT_DEFINED"`；
- 比赛平台不得自行把使用率转换为健康评分；
- 收到正式公式后再增加独立版本化计算器。

时间维度处理：

- 可以返回 `days_since_last_maintenance`；
- 可以返回标准中的 `maintenance_days`；
- `use_time_dimension=false` 时，时间信息不参与最终预警等级；
- 禁止在没有业务公式时自行合并模次和日期。

异常：

- 当前模次小于上次保养模次：`INVALID_COUNT_DATA`；
- 阈值为空或小于等于 0：`INVALID_STANDARD`；
- 模具停用：返回状态，但默认不进入待保养清单；
- 上次保养时间为空：返回缺失字段提示，不伪造日期。

## 7.3 StaffCandidateSelector

Django 只返回候选人员，不执行最终派工。

输入：

- `mold_id`；
- `maintenance_level`；
- 可选 `max_load`；
- 可选 `limit`。

所需技能来自匹配到的 `MaintenanceStandard.required_skills`。

技能匹配度：

```python
skill_match_ratio = matched_required_skills / total_required_skills
```

第一版候选条件：

- 技能匹配度 `>= 0.80`；
- 当前负荷 `< 0.80`；
- `on_duty=true`；
- `available=true`；
- 技能未过期。

确定性排序：

1. 同产线优先；
2. 技能匹配度从高到低；
3. 高优先级任务时技师等级从高到低；
4. 当前负荷从低到高；
5. 员工编号升序，保证结果稳定。

返回每名候选人的：

- 事实字段；
- 技能匹配度；
- 匹配技能；
- 缺失技能；
- 当前负荷；
- 是否同产线；
- 技师等级；
- 是否满足候选条件；
- 命中或排除原因。

如果业务尚未确认技师等级排序，第一版使用显式配置映射，不能依赖字符串自然排序。

## 7.4 KnowledgeContextBuilder

返回比赛平台检索知识库所需标签，不返回知识正文。

输出包括：

- 模具编号、名称、类型、等级、类别；
- 保养等级；
- 标准编号和版本；
- 所需技能；
- 知识关键词；
- 一级、二级位置；
- 建议检索过滤器；
- 建议检索查询文本。

建议查询文本只能由结构化字段拼接，不调用大模型。

## 7.5 AnalyticsSelector

第一版只基于历史保养记录返回事实统计：

- 记录数量；
- 标准总工时；
- 实际总工时；
- 平均实际工时；
- 标准与实际工时偏差；
- 按模具类型、班组、人员和月份分组；
- 异常记录数量。

不输出未经验证的成本节约、寿命提升或趋势预测结论。

---

## 8. API 契约

统一前缀：

```text
/api/v1
```

## 8.1 统一成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "req-20260812-0001"
}
```

列表响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 0,
      "total_pages": 0
    }
  },
  "request_id": "req-20260812-0001"
}
```

## 8.2 统一失败响应

```json
{
  "code": "STANDARD_NOT_FOUND",
  "message": "未找到适用于该模具的有效保养标准",
  "data": {
    "mold_id": "MOLD-2024-0891"
  },
  "request_id": "req-20260812-0002"
}
```

## 8.3 时间、数字和枚举规范

- 时间：ISO 8601，包含时区，例如 `2026-08-12T16:00:00+08:00`；
- 时区：`Asia/Shanghai`；
- 比率：0—1 的小数，例如 `0.9325`；
- 百分比：数字，例如 `93.25`，不在字段中附加 `%`；
- 工时：十进制小时，例如 `8.00`；
- 枚举：使用大写英文稳定值；
- 中文说明放在独立 `display_name` 或 `message` 字段；
- 结果必须稳定排序。

## 8.4 健康检查

```http
GET /api/v1/health
```

认证：可不要求 API Key，但不得暴露敏感配置。

返回：

- 应用状态；
- 数据库状态；
- 版本；
- 当前时间。

## 8.5 服务元数据

```http
GET /api/v1/meta
```

返回：

- API 版本；
- 演示数据版本；
- 当前预警策略版本；
- 是否启用时间维度；
- 支持的模具类型；
- 服务只读标志。

## 8.6 模具接口

```http
GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/due
GET /api/v1/molds/{mold_id}/knowledge-context
```

列表过滤：

- `mold_type`；
- `mold_level`；
- `mold_category`；
- `production_line`；
- `status`；
- `alert_level`；
- `search`；
- `ordering`；
- `page`；
- `page_size`。

`page_size` 默认 20，最大 100。

### 保养状态响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "mold_id": "MOLD-2024-0891",
    "mold_name": "前壳体注塑模",
    "mold_type": "注塑模具",
    "mold_level": "A",
    "mold_category": "精密注塑模",
    "cavity_count": 4,
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
    "standard_hours": 8.0,
    "standard_id": "STD-INJECTION-A-L1",
    "standard_version": "V1",
    "alert_policy_id": "POLICY-COUNT-V1",
    "alert_policy_version": "V1",
    "primary_location": "注塑车间",
    "secondary_location": "A区模具库",
    "calculated_at": "2026-08-12T16:00:00+08:00"
  },
  "request_id": "req-20260812-0003"
}
```

该示例复用原始方案中的模次和阈值。除这些明确数值外，其他演示数据均应标记为模拟数据。

## 8.7 保养标准接口

```http
GET /api/v1/maintenance-standards
GET /api/v1/maintenance-standards/{standard_id}
GET /api/v1/maintenance-standards/match
```

匹配参数：

- `mold_type`；
- `mold_level`；
- `mold_category`；
- `maintenance_level`；
- 可选 `effective_at`。

不满足唯一匹配时必须明确报错。

## 8.8 人员接口

```http
GET /api/v1/staff
GET /api/v1/staff/{employee_id}
GET /api/v1/staff/available
```

推荐调用：

```http
GET /api/v1/staff/available?mold_id=MOLD-2024-0891&maintenance_level=一级保养&max_load=0.80&limit=10
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "mold_id": "MOLD-2024-0891",
    "required_skills": ["注塑模具保养", "温控系统检查"],
    "candidates": [
      {
        "employee_id": "EMP-0012",
        "employee_name": "张三",
        "email": "demo-maintainer@example.test",
        "team": "注塑一车间模具维保组",
        "production_line": "注塑一线",
        "skill_level": "SENIOR",
        "current_load": 0.45,
        "skill_match_ratio": 1.0,
        "same_line": true,
        "eligible": true,
        "matched_skills": ["注塑模具保养", "温控系统检查"],
        "missing_skills": [],
        "reasons": ["技能完全匹配", "负荷低于阈值", "同产线"]
      }
    ]
  },
  "request_id": "req-20260812-0004"
}
```

平台负责从候选列表中确定最终人员并发送邮件；Django 不保存最终选择。

## 8.9 历史保养记录

```http
GET /api/v1/maintenance-records
GET /api/v1/maintenance-records/{record_id}
```

过滤：

- `mold_id`；
- `start_date`；
- `end_date`；
- `maintenance_level`；
- `maintainer_employee_id`；
- `result`；
- `page`；
- `page_size`。

## 8.10 基础统计

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/mold-history
```

统计接口必须返回查询时间范围、筛选条件和样本数量，避免平台把不同口径数据混用。

## 8.11 可选只读工单快照

```http
GET /api/v1/work-orders
GET /api/v1/work-orders/{work_order_id}
```

只有在比赛平台必须展示预置工单时才实现。任何写方法均禁止。

## 8.12 OpenAPI

```text
/api/schema/
/api/docs/
```

要求：

- 每个接口有中文摘要；
- 参数有类型、是否必填和示例；
- 所有枚举写入 schema；
- 成功与失败响应有示例；
- 生成并提交 `docs/contracts/openapi.yaml`；
- CI 检查生成结果与仓库文件一致。

---

## 9. 错误码设计

| HTTP | 业务码 | 场景 |
|---:|---|---|
| 400 | `INVALID_QUERY_PARAMETER` | 参数格式或范围错误 |
| 400 | `INVALID_COUNT_DATA` | 当前模次小于上次保养模次 |
| 400 | `INVALID_STANDARD` | 阈值或标准工时无效 |
| 401 | `UNAUTHORIZED` | API Key 缺失或无效 |
| 404 | `MOLD_NOT_FOUND` | 模具不存在 |
| 404 | `STANDARD_NOT_FOUND` | 找不到有效标准 |
| 404 | `EMPLOYEE_NOT_FOUND` | 员工不存在 |
| 409 | `AMBIGUOUS_STANDARD` | 同时匹配多个有效标准 |
| 405 | `METHOD_NOT_ALLOWED` | 调用写入方法 |
| 429 | `RATE_LIMITED` | 超过调用限制 |
| 500 | `INTERNAL_ERROR` | 未预期异常 |
| 503 | `DATABASE_UNAVAILABLE` | 数据库不可用 |

服务端日志记录完整异常，API 不返回堆栈和敏感配置。

---

## 10. 认证与安全

### 10.1 API Key

比赛平台通过以下请求头调用：

```http
X-API-Key: <secret>
```

要求：

- Key 从环境变量或安全配置读取；
- 不提交到 Git；
- 使用常量时间比较；
- 日志中不得记录完整 Key；
- 支持至少一个当前 Key 和一个轮换 Key；
- 无效 Key 返回 401。

### 10.2 HTTP 安全

- 生产环境 `DEBUG=false`；
- 严格配置 `ALLOWED_HOSTS`；
- 公网访问必须通过 HTTPS；
- Nginx 只开放 80/443；
- Django/Gunicorn 内部监听 `0.0.0.0:18080`；
- 数据库端口不对公网开放；
- 配置安全响应头；
- 限制 `page_size`、搜索长度和请求头大小；
- 使用 DRF throttling 防止误调用；
- CORS 默认关闭，确需浏览器调用时只允许明确域名。

### 10.3 Admin 安全

- Admin 使用独立路径，例如 `/internal/admin/`；
- 必须启用账号密码和强密码；
- 条件允许时限制访问 IP；
- 不使用默认管理员账号名；
- 生产环境不暴露调试工具；
- 数据修改保留 Django Admin 日志。

### 10.4 个人信息

员工邮箱属于受控业务数据：

- 仅对认证 API 客户端返回；
- 日志中默认掩码；
- 种子数据使用 `example.test`；
- 比赛现场真实收件邮箱通过 Admin 单独配置；
- 不在截图、README 或公开日志中暴露真实邮箱。

---

## 11. Django Admin 与演示数据

### 11.1 Admin 功能

为以下模型提供管理页面：

- Mold；
- MaintenanceStandard；
- AlertPolicy；
- Skill；
- Employee；
- EmployeeSkill；
- MaintenanceRecord；
- WorkOrderSnapshot（如启用）。

Admin 要求：

- 关键字段可搜索、过滤和排序；
- 只读展示计算字段；
- 阈值和模次输入有校验；
- 标准启用前校验是否产生重复有效标准；
- 员工负荷限制在 0—1；
- 所有关联对象避免 N+1 查询。

### 11.2 Management Commands

必须实现：

```bash
python manage.py seed_demo_data
python manage.py validate_demo_data
python manage.py reset_demo_data --confirm
python manage.py export_demo_data --output data/export.json
```

要求：

- `seed_demo_data` 幂等；
- 每次种子数据有版本号；
- `validate_demo_data` 检查模具、标准、人员和技能关联；
- `reset_demo_data` 必须显式 `--confirm`；
- 命令失败返回非零退出码；
- 不删除非 DEMO 来源数据。

### 11.3 最小演示数据集

至少准备：

- 12 套模具；
- 绿色、黄色、红色各不少于 3 套；
- 1 套找不到标准的异常模具；
- 1 套模次数据异常的模具；
- 注塑和钣金两类模具；
- 至少 4 条保养标准；
- 8 名模拟员工；
- 技能完全匹配、部分匹配、负荷超限、不在岗、不同产线等人员场景；
- 至少 20 条历史保养记录；
- 可选 5 条只读工单快照。

源材料中明确的 `MOLD-2024-0891` 示例应保留，用于复现 186,500 / 200,000 = 93.25% 的黄色预警演示。

---

## 12. 查询性能与稳定性

### 12.1 ORM 规范

- 外键使用 `select_related`；
- 多对多技能使用 `prefetch_related`；
- 列表接口禁止逐行再次查询标准；
- 计算待保养清单时避免 N+1；
- 为常用过滤字段创建索引；
- 所有列表必须分页；
- 排序必须包含稳定的最终键，例如 `mold_id`。

### 12.2 性能目标

演示数据规模下：

- 单模具详情 P95 小于 300 ms；
- 保养状态查询 P95 小于 400 ms；
- 100 套模具的待保养清单 P95 小于 800 ms；
- 候选人员查询 P95 小于 500 ms；
- 健康检查 P95 小于 100 ms。

这些是工程验收目标，不是对外业务成效指标。

### 12.3 缓存

第一版不默认引入 Redis。只有性能测试证明必要时，才增加进程内短时缓存；缓存不得导致标准或人员变更后长期返回旧数据。

---

## 13. 日志与可观测性

### 13.1 Request ID

- 接受平台传入 `X-Request-ID`；
- 未传入时由 Django 生成；
- 响应头和响应体均返回 request ID；
- 所有日志携带同一个 request ID。

### 13.2 日志字段

结构化日志至少包含：

- timestamp；
- level；
- request_id；
- method；
- path；
- status_code；
- duration_ms；
- client_name；
- error_code；
- mold_id（如有）；
- employee_id（如有）。

不记录：

- API Key；
- 完整邮箱；
- 密码；
- 堆栈到 API 响应。

### 13.3 健康检查

`/api/v1/health` 至少验证：

- Django 进程可用；
- 数据库简单查询可用；
- 当前迁移已应用；
- 服务版本可读。

---

## 14. 测试计划

## 14.1 单元测试

覆盖：

- 标准精确匹配；
- 无标准和多标准；
- 模次差值；
- 使用率和剩余模次；
- 89.99%、90%、99.99%、100% 边界；
- 当前模次小于上次保养模次；
- 阈值为 0；
- 停用模具；
- 时间维度关闭时不影响预警；
- 技能匹配率；
- 80% 技能边界；
- 80% 负荷边界；
- 同产线排序；
- 技师等级排序；
- 稳定排序；
- 知识上下文标签。

## 14.2 模型测试

覆盖：

- 唯一约束；
- 数值范围；
- 有效标准重复；
- 邮箱校验；
- 员工负荷校验；
- 标准版本和有效期；
- DEMO 数据删除边界。

## 14.3 API 测试

覆盖：

- API Key 缺失、错误和正确；
- GET 成功；
- POST/PUT/PATCH/DELETE 返回 405；
- 查询过滤；
- 排序；
- 分页；
- 最大 page size；
- 统一响应结构；
- 统一错误结构；
- request ID 透传和生成；
- 时间和小数序列化；
- 404、409、429 和 503；
- OpenAPI schema 可生成。

## 14.4 契约测试

- 对关键响应建立 JSON Schema；
- 保存源材料示例的固定快照；
- 生成 OpenAPI 后与 `docs/contracts/openapi.yaml` 比较；
- 禁止无版本升级地删除字段、改名或改变类型；
- 枚举变化必须经过计划更新。

## 14.5 Management Command 测试

- 种子数据第一次成功；
- 第二次执行不重复；
- 校验命令能发现缺失标准；
- 重置命令无 `--confirm` 时拒绝；
- 重置不删除非 DEMO 数据；
- 导出结果可再次导入校验。

## 14.6 部署测试

- Docker 镜像构建；
- 容器以非 root 用户运行；
- 健康检查通过；
- 迁移可执行；
- 静态文件可收集；
- Nginx 反向代理可访问；
- HTTPS 环境下接口正常；
- 重启后 SQLite 数据卷仍存在。

## 14.7 质量门禁命令

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py spectacular --file docs/contracts/openapi.yaml --validate
```

生产配置另运行：

```bash
python manage.py check --deploy --settings=config.settings.production
```

---

## 15. 部署方案

### 15.1 虚拟服务器

比赛演示建议：

| 项目 | 建议 |
|---|---|
| 操作系统 | Ubuntu 22.04/24.04 |
| CPU | 2 核 |
| 内存 | 4 GB |
| 磁盘 | 20—40 GB |
| 公网地址 | 固定公网 IP 或域名 |
| 外部端口 | 443 |
| Django 内部端口 | 18080 |
| 时区 | Asia/Shanghai |

### 15.2 Docker Compose

第一版服务：

```yaml
services:
  web:
  nginx:
```

使用 PostgreSQL 时增加：

```yaml
  postgres:
```

不部署 Redis、Celery 或邮件服务。

### 15.3 环境变量

```text
DJANGO_SETTINGS_MODULE
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DATABASE_URL
MOLDGUARD_API_KEYS
MOLDGUARD_TIME_ZONE
MOLDGUARD_DEMO_MODE
MOLDGUARD_DEMO_DATA_VERSION
MOLDGUARD_DEFAULT_PAGE_SIZE
MOLDGUARD_MAX_PAGE_SIZE
MOLDGUARD_THROTTLE_RATE
```

`.env.example` 只放占位符，不放真实密钥。

### 15.4 部署步骤

1. 构建镜像；
2. 加载环境变量；
3. 执行数据库迁移；
4. 执行 `seed_demo_data`；
5. 执行 `validate_demo_data`；
6. 收集静态文件；
7. 启动 Gunicorn；
8. 启动 Nginx；
9. 外网验证 `/api/v1/health`；
10. 比赛平台使用 API Key 联调。

### 15.5 备份与恢复

SQLite：

- 停止写入后复制数据库文件；
- 每次比赛前保存一份初始快照；
- 提供一键恢复演示数据流程。

PostgreSQL：

- 使用 `pg_dump`；
- 恢复后执行数据校验命令。

---

## 16. 比赛平台接入流程

### 16.1 单模具预警

```text
平台接收模具编号
  ↓
GET /molds/{mold_id}/maintenance-status
  ↓
平台展示 Django 返回的预警事实
  ↓
GET /molds/{mold_id}/knowledge-context
  ↓
平台按标签检索点检知识库
  ↓
平台生成预警报告
```

### 16.2 候选人员与邮件

```text
平台确定需要派发的模具和保养等级
  ↓
GET /staff/available?mold_id=...&maintenance_level=...
  ↓
平台展示候选人员和规则原因
  ↓
主管在平台确认最终人员
  ↓
平台检索对应点检知识
  ↓
平台发送邮件
```

Django 不接收最终人员、不接收邮件结果，也不改变任何工单状态。

### 16.3 批量巡检

```text
平台手动或定时触发
  ↓
GET /molds/due?alert_level=YELLOW,RED
  ↓
平台遍历结果
  ↓
平台分别检索知识、选择人员并发送邮件
```

如果平台不支持真正定时任务，使用手动输入“执行今日巡检”触发，不在 Django 中增加调度器。

### 16.4 平台使用约束

- 平台不得重新计算 Django 已返回的模次和使用率；
- 平台不得自行补全缺失阈值；
- `health_score_status=NOT_DEFINED` 时不得生成具体健康评分；
- 接口失败时明确提示失败，不用 LLM 编造备用数据；
- GET 请求可安全重试；
- 平台日志保存 request ID，便于服务端排查。

---

## 17. 分阶段实施计划

## Phase 0：契约与规则冻结

目标：在编码前冻结 V1 查询范围。

任务：

- 确认本计划为权威计划；
- 明确 Django 只读边界；
- 确认 API 前缀；
- 确认模具字段；
- 确认人员字段；
- 确认保养标准字段；
- 确认 90%/100% 是否作为演示阈值；
- 确认健康评分第一版不实现；
- 确认是否需要只读工单快照；
- 确认比赛平台网络可访问外部 HTTPS。

交付：

- 本计划 V1.0；
- `docs/contracts/api-decisions.md`；
- `docs/contracts/demo-data-contract.md`。

**Stop Gate A**：未确认阈值和字段时，不进入业务规则编码。

## Phase 1：工程骨架

任务：

- 创建 Django 5.2 项目；
- 拆分开发和生产 settings；
- 接入 DRF、django-filter、drf-spectacular；
- 建立 common 模块；
- 实现 request ID；
- 实现统一响应和异常处理；
- 实现 API Key 认证；
- 实现 `/health` 和 `/meta`；
- 建立 pytest 和 Ruff 配置；
- 建立 Dockerfile。

验收：

- 服务可启动；
- `/health` 返回统一响应；
- 无 Key 访问受保护接口返回 401；
- 写入方法返回 405；
- 基础质量门禁通过。

**Stop Gate B**：基础接口、认证和测试框架全部通过后再建业务模型。

## Phase 2：模型、Admin 与种子数据

任务：

- 实现 Mold；
- 实现 MaintenanceStandard；
- 实现 AlertPolicy；
- 实现 Skill、Employee、EmployeeSkill；
- 实现 MaintenanceRecord；
- 可选实现 WorkOrderSnapshot；
- 配置 Admin；
- 增加数据库索引和约束；
- 实现种子、校验、重置和导出命令；
- 准备演示数据。

验收：

- 迁移无漂移；
- Admin 可维护数据；
- 种子命令幂等；
- 校验命令能发现冲突标准；
- 演示数据覆盖所有边界场景。

**Stop Gate C**：数据模型、约束和演示数据通过审查后再开发计算服务。

## Phase 3：标准匹配和状态计算

任务：

- 实现 MaintenanceStandardMatcher；
- 实现 MaintenanceStatusCalculator；
- 实现预警策略版本；
- 实现异常码；
- 实现单元测试；
- 复现 93.25% 示例。

验收：

- 90% 和 100% 边界准确；
- 缺失或冲突标准明确报错；
- 健康评分不被伪造；
- 计算结果包含标准和策略版本。

**Stop Gate D**：所有规则单元测试通过后再开放 API。

## Phase 4：模具与标准 API

任务：

- 模具列表和详情；
- 保养状态；
- 待保养清单；
- 标准列表、详情和匹配；
- 过滤、分页和排序；
- OpenAPI 文档；
- API 契约测试。

验收：

- 查询结果稳定；
- 无 N+1；
- 所有错误使用统一格式；
- OpenAPI 可验证；
- POST 等方法返回 405。

**Stop Gate E**：比赛平台能够完成单模具查询和批量巡检调用。

## Phase 5：人员候选和知识上下文

任务：

- 实现 StaffCandidateSelector；
- 实现人员列表、详情和可用候选接口；
- 实现 KnowledgeContextBuilder；
- 实现技能匹配和排序测试；
- 增加邮箱保护和日志掩码。

验收：

- 候选结果可解释；
- 技能、负荷、在岗和产线规则正确；
- 平台可用返回标签检索点检知识；
- Django 不保存最终派工结果。

**Stop Gate F**：比赛平台可完成“查询候选人—检索知识—发送邮件”演示。

## Phase 6：历史与统计 API

任务：

- 历史保养记录查询；
- summary、work-hours、mold-history 统计；
- 时间范围和过滤口径；
- 数据量和性能测试；
- 可选只读工单快照。

验收：

- 统计结果与明细一致；
- 每个统计响应包含口径和样本数量；
- 不输出未经验证的业务收益。

**Stop Gate G**：统计接口与平台展示通过联调。

## Phase 7：部署与安全加固

任务：

- 生产 settings；
- Gunicorn；
- Nginx；
- HTTPS；
- Docker Compose；
- 限流；
- 结构化日志；
- 健康检查；
- 备份恢复文档；
- `check --deploy`。

验收：

- 公网 HTTPS 可访问；
- 只开放必要端口；
- DEBUG 关闭；
- API Key 不泄漏；
- 容器重启后数据保留；
- 部署测试通过。

**Stop Gate H**：只有外网联调、备份和恢复全部通过，才进入正式演示。

## Phase 8：比赛平台联调与验收

任务：

- 配置平台 API Key；
- 对接单模具查询；
- 对接今日巡检；
- 对接知识上下文；
- 对接候选人员；
- 对接历史和统计；
- 验证接口失败分支；
- 编写演示数据重置流程；
- 完成演示脚本。

验收：

- 从查询到平台发邮件的链路稳定；
- Django 全程无业务写入；
- 所有关键结果可通过 request ID 追踪；
- 接口失败时平台不产生虚构数据；
- 演示可以重复执行。

---

## 18. 开发与 Git 工作流

建议实施分支：

```text
agent/django-query-api-v1
```

提交建议：

```text
chore: scaffold Django query service
feat: add mold and maintenance standard models
feat: add maintenance status calculator
feat: expose mold query endpoints
feat: add staff candidate queries
feat: add maintenance analytics endpoints
chore: add production deployment configuration
docs: freeze v1 API contract
```

要求：

- 每个 Phase 独立提交；
- 不把多个未完成 Phase 混进一个提交；
- 每个 Stop Gate 前工作树干净；
- 所有迁移文件提交入库；
- OpenAPI 契约更新与代码同一提交；
- 不直接在 `main` 上编写业务代码；
- 完成后通过 Draft PR 审阅，再决定合并。

---

## 19. 完成定义（Definition of Done）

只有满足以下全部条件，V1 才算完成：

- [ ] Django 只读边界没有被突破；
- [ ] `/api/v1` 只允许 GET/HEAD/OPTIONS；
- [ ] 模具、标准、人员、技能和历史模型完成；
- [ ] 规则计算不依赖 LLM；
- [ ] 93.25% 示例可稳定复现；
- [ ] 健康评分未定义时返回明确状态；
- [ ] 无标准、冲突标准和异常模次均有稳定错误码；
- [ ] 候选人员结果可解释且不执行派工；
- [ ] 知识上下文只返回标签，不返回知识正文；
- [ ] 邮件发送完全由比赛平台或其他渠道负责；
- [ ] Django 不保存邮件结果；
- [ ] API Key、HTTPS、限流和 Admin 安全配置完成；
- [ ] 演示种子数据幂等且可重置；
- [ ] OpenAPI 契约生成并提交；
- [ ] 单元、API、契约和部署测试全部通过；
- [ ] Ruff、Django check 和迁移检查通过；
- [ ] 比赛平台完成真实外网联调；
- [ ] 备份与恢复流程验证通过；
- [ ] README 与本计划范围一致。

---

## 20. 仍需负责人确认的事项

1. 注塑模具和钣金模具的完整准确保养标准表；
2. 第一版是否正式采用 90% 黄色、100% 红色阈值；
3. 健康评分是否彻底取消，还是后续补公式；
4. 时间周期是否只展示，还是参与预警；
5. 一级、二级、三级保养如何选择；
6. 人员技能等级的标准枚举和排序；
7. 负荷是人工维护值，还是由其他系统计算；
8. 候选人员是否必须返回邮箱；
9. 比赛使用的真实测试收件邮箱；
10. 是否需要只读模拟工单快照；
11. 是否需要历史工时统计接口；
12. 比赛平台的 HTTP 超时、认证头和公网访问限制；
13. 虚拟服务器域名、HTTPS 证书和部署位置；
14. 仓库后续是否继续保持 Private。

未确认事项必须保留配置或明确错误，不允许开发人员自行补全业务规则。

---

## 21. 后续接入真实系统的演进路径

V1 完成后，如果需要连接真实 MES/ERP：

1. 保持 `/api/v1` 响应结构不变；
2. 将 ORM 查询封装在 selector/repository 边界内；
3. 增加真实数据适配器；
4. 对外继续返回相同字段和错误码；
5. 对真实数据与模拟数据分别标记 `data_source`；
6. 先做双读比对，再切换数据源；
7. 写入类业务另建计划和 API 版本，不直接扩展本只读基线。

若未来确实需要工单闭环，应新建独立计划，重新设计认证、权限、幂等、状态机和审计，不能把写入接口临时添加到当前 V1。

---

## 22. 计划结论

本项目第一版不是完整模具管理系统，而是一个为比赛智能体提供可靠业务事实的 Django 查询服务。

最终职责保持为：

```text
Django：数据、确定性计算、候选查询、历史和统计
比赛平台：对话、知识检索、内容生成、任务编排、邮件发送
```

后续编码必须以本文件为唯一范围基线。任何邮件、知识库、工单写入或状态流转需求，都应先更新计划并单独审阅，不能在实现过程中自行扩张范围。
