# MoldGuard 比赛服务器完整实施计划

> **邮件责任覆盖说明（2026-08-13）**：比赛平台不支持发信。本文关于平台组装/发送
> 邮件、`email-result` 和“不实现Django SMTP”的历史计划，均由
> `docs/decisions/2026-08-13-django-smtp-delivery.md` 覆盖。当前正式流程为平台回写
> 知识包并调用 Django `send-email`，由 Django 通过 SMTP 发送。

- **计划状态**：`IMPLEMENTATION_READY_CLEAN_BUILD`
- **版本**：V5.0
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **实施分支**：`agent/competition-server-v1`
- **分支基线**：从 `main` 创建，不从测试分支创建
- **知识库基线**：`MOLDGUARD-KB-1.2`
- **模型字段基线**：V3.0
- **报工契约**：`REPORT-FORM-1.0`
- **测试分支参考**：`agent/platform-capability-probe-v1@2ed0b59bbf74c5171860481ab2b1de2294bbfc9d`
- **代码策略**：测试分支只用于评估技术风险和验证设计，不合并、不 cherry-pick、不复用其迁移与业务代码
- **服务器定位**：无主管角色、无用户登录、无 API 鉴权、仅保存 DEMO 数据的比赛业务服务器
- **比赛部署**：Oracle Linux 主机 + Docker Compose + MariaDB + Gunicorn + 宿主 Nginx

---

## 1. 计划目的

本计划用于从干净的 `main` 分支重新实现一套可直接用于比赛的 MoldGuard Django 服务器。

服务器需要支撑以下完整演示链路：

```text
模具触发条件扫描
→ 自动建立保养工单
→ 查询候选人员并完成派工
→ 智能体平台检索点检知识
→ 平台发送包含点检知识和报工链接的邮件
→ 被派工人员点击 Django 报工页面
→ 提交正常报工或异常报工
→ 正常报工自动完成并按规则复位周期
→ 异常报工继续处理或关联修模任务
→ 查询工时、完成率和模具履历
```

智能体平台负责对话、工作流、知识检索、LLM 内容生成和邮件发送；Django 负责结构化业务数据、触发规则、工单事务、状态流转、报工页面和统计结果。

原始参赛方案要求实现预警、自动工单、派工、过程追踪和工时分析。本计划保留该完整主线，但按照已经确认的比赛边界删除主管审批、登录鉴权、历史文件导入和生产级复杂治理。

---

## 2. 权威来源与冲突顺序

开发时按以下顺序解释业务规则：

```text
1. knowledge-base/releases/MOLDGUARD-KB-1.2/upload/ 下的最终知识正文
2. 本计划 V5.0
3. docs/models/2026-08-13-django-model-field-review.md V3.0
4. docs/contracts/2026-08-13-mail-report-link-contract.md REPORT-FORM-1.0
5. 其他当前文档
```

以下内容只作为背景，不覆盖当前知识库：

- 原方案中的健康评分、红黄绿预警和主管验收；
- 早期“钣金和注塑统一按吨位触发”的决定；
- 早期“注塑两个月只提醒、不建单”的决定；
- 测试分支中的旧字段、旧规则和平台探测流程。

发生冲突时，以 `MOLDGUARD-KB-1.2` 为最终解释。

---

## 3. 测试分支的参考结论

测试分支已经证明下列技术方案可行：

- Django 5.2 与 Django REST Framework 3.16 可满足接口需求；
- 统一 JSON 响应、Request-ID 和统一异常码有利于平台工作流处理；
- 所有写请求使用 `client_request_id` 能避免平台重试造成重复写入；
- `transaction.atomic()` 与 `select_for_update()` 能保护扫描、派工、报工和周期复位；
- management command 适合初始化、重置和验证演示数据；
- OpenAPI、API 测试、集成测试和 HTTP 冒烟测试对联调有明显价值；
- Docker Compose + MariaDB + Gunicorn + Nginx 适合比赛服务器部署；
- MariaDB 私有网络、健康检查、日志轮转和宿主持久化目录可直接作为部署设计参考。

测试分支同时暴露了需要在新实现中避免的问题：

1. 旧代码对所有模具使用 30K/50K 吨位规则，和最终钣金规则不一致；
2. 两个月仅生成提醒，和最终自动建单要求不一致；
3. 扫描和建单是两个步骤，比赛流程需要扫描时自动建单；
4. 字段使用 `current_count/cycle_baseline_count/cycle_baseline_time`，和知识库最终字段不一致；
5. 没有 `/report/{work_order_id}` 网页报工入口；
6. 邮件上下文没有 `report_url` 和 `REPORT-FORM-1.0`；
7. 异常报工同时占用最终报工记录，无法在后续处理后再次正常报工；
8. 平台探测模型和 `/probe/*` 接口不属于最终比赛业务；
9. 旧迁移链包含多次试验性模型演进，不适合作为全新比赛服务器的长期基线。

因此，本计划只参考测试分支的技术经验，不复用其代码、模型、迁移、数据文件和接口实现。

---

## 4. 最终范围

### 4.1 Django 必须实现

- 模拟模具台账；
- 注塑和钣金触发规则计算；
- 自动扫描、提醒去重和自动建单；
- 模拟人员、技能、负荷和候选排序；
- 指定派工；
- 工单状态机和时间线；
- 知识检索上下文；
- 单份知识包保存；
- 邮件上下文与邮件发送结果回写；
- Django 生成的 `report_url`；
- 移动端友好的报工页面；
- 开工、暂停、恢复；
- 正常报工；
- 异常报工；
- 继续处理；
- 关联修模任务；
- 修模完成后回到原保养工单；
- 周期复位；
- 模具履历；
- 工时与完成率统计；
- 演示数据初始化、重置和验证；
- OpenAPI、自动化测试、Docker 与部署文档。

### 4.2 智能体平台负责

- 用户对话；
- Workflow / Agent 编排；
- 知识库与 RAG；
- LLM 生成预警说明、任务说明和分析结论；
- 展示候选人员并选择最终人员；
- 组装派工邮件；
- 发送邮件；
- 将知识包和邮件结果回写 Django；
- 使用 Django 返回的 `report_url` 生成“提交报工情况”按钮。

### 4.3 明确不实现

```text
主管、管理员、计划员、验收人等业务角色
用户登录、密码、JWT、Token、API Key
历史 Excel 或文件导入
真实 MES、ERP 和排产系统
Django SMTP 邮件发送
健康评分和红黄绿评分模型
一级、二级、三级保养模型
复杂审批、两次关闭机会和送模流程
独立 Vue/React 前端
Redis、Celery 和异步任务队列
备件、采购、成本和库存
Excel/Word 报表导出
同比、环比和趋势预测
生产级高并发、容灾和长期公网安全治理
```

---

## 5. 总体架构

```text
┌────────────────────────────────────────────┐
│               比赛智能体平台               │
│                                            │
│ 对话 │ 工作流 │ 知识库/RAG │ LLM │ 邮件   │
└─────────────────────┬──────────────────────┘
                      │ HTTP/HTTPS + JSON
                      ▼
┌────────────────────────────────────────────┐
│          MoldGuard Django Server           │
│                                            │
│ 模具 │ 触发规则 │ 工单 │ 派工 │ 报工页面 │
│ 知识快照 │ 邮件回写 │ 修模关联 │ 统计     │
└─────────────────────┬──────────────────────┘
                      │
                      ▼
                 MariaDB 数据库
```

比赛现场浏览器通过邮件中的 `report_url` 直接打开 Django 页面；智能体平台通过 API 完成扫描、派工、知识回写和邮件结果回写。

---

## 6. 技术基线

| 项目 | 选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS 系列 |
| REST API | Django REST Framework 3.16 系列 |
| OpenAPI | drf-spectacular |
| 比赛数据库 | MariaDB 11.8 |
| 本地与单元测试 | SQLite |
| WSGI | Gunicorn，1 worker / 4 threads |
| 反向代理 | 宿主 Nginx |
| 容器 | Docker Compose |
| 测试 | pytest、pytest-django |
| 代码质量 | Ruff |
| 时区 | Asia/Shanghai |
| 内部端口 | 18080 |
| 认证 | 无，DRF `AllowAny` |
| 数据分类 | DEMO ONLY |

新工程必须同时支持 SQLite 和 MariaDB，所有迁移与查询需要在两种数据库上兼容。

---

## 7. 工程目录

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── requirements.txt
├── .env.example
├── Dockerfile
├── compose.yaml
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── common/
│   │   ├── responses.py
│   │   ├── exceptions.py
│   │   ├── middleware.py
│   │   ├── idempotency.py
│   │   └── validators.py
│   ├── molds/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services/
│   │       ├── trigger_service.py
│   │       └── scan_service.py
│   ├── staff/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── services.py
│   ├── workorders/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── forms.py
│   │   ├── views.py
│   │   ├── web_views.py
│   │   ├── urls.py
│   │   └── services/
│   │       ├── creation_service.py
│   │       ├── assignment_service.py
│   │       ├── knowledge_service.py
│   │       ├── report_service.py
│   │       ├── repair_service.py
│   │       └── timeline_service.py
│   └── analytics/
│       ├── views.py
│       ├── urls.py
│       └── services.py
├── templates/
│   └── workorders/
│       ├── report_form.html
│       └── report_result.html
├── static/
│   └── report.css
├── data/demo/
│   └── demo_data.json
├── scripts/
│   ├── container_entrypoint.sh
│   ├── smoke_test.py
│   └── backup_mariadb.sh
├── deploy/nginx/
│   └── moldguard.conf
├── tests/
│   ├── unit/
│   ├── api/
│   ├── web/
│   ├── integration/
│   └── deployment/
└── docs/
```

新项目不创建 `platform_probe` 应用，也不创建 `/probe/*` 业务接口。

---

## 8. 持久化模型

本版只建立 6 个业务模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

字段以 V3.0 模型字段清单为基础，编码前在 Phase 0 再冻结一次最终 Django 类型和约束。

### 8.1 Mold

核心字段：

```text
mold_id
mold_name
mold_type                    INJECTION / SHEET_METAL
effective_mold_cycles
baseline_effective_mold_cycles
baseline_maintenance_at
cycle_version
first_production_at
development_tonnage
mold_category                FORMING / PUNCH_BLANKING / CONTINUOUS / SIDE_PANEL
mold_type_code               LC101 ... LC109
level_1_location
level_2_location
production_line
output_updated_at
status                       ACTIVE / INACTIVE / UNDER_REPAIR / DISABLED
knowledge_profile_code
created_at
updated_at
```

数据库约束：

- 有效模次不得小于 0；
- 基准模次不得大于当前有效模次；
- 注塑自动扫描时必须具备 `development_tonnage`；
- 钣金自动扫描时必须具备 `mold_category`；
- `LC109` 只允许 `CONTINUOUS` 或 `SIDE_PANEL`；
- `cycle_version >= 1`。

### 8.2 Alert

```text
alert_id
mold
rule_id
alert_type                    COUNT_TRIGGER / TIME_TRIGGER / MANUAL
cycle_version
cycle_mold_cycles_snapshot
threshold_count
trigger_reason
status                        OPEN / CLOSED
work_order_created
created_at
closed_at
dedupe_key                    unique
```

`dedupe_key` 推荐组成：

```text
mold_id + rule_id + cycle_version
```

### 8.3 Employee

```text
employee_id
employee_name
email
production_line
skills_json
current_load                 0—1
on_duty
available
created_at
updated_at
```

测试邮箱必须由环境变量或 DEMO 数据提供，不保存真实员工个人信息。

### 8.4 WorkOrder

工单主字段：

```text
work_order_id
alert                         可空，手动工单无Alert
mold
parent_work_order             关联修模任务使用
linked_repair_order
rule_id
work_order_type
status
assignee
required_finish_at
create_key                    unique
```

触发快照：

```text
effective_mold_cycles_snapshot
baseline_effective_mold_cycles_before
baseline_maintenance_at_before
cycle_mold_cycles_snapshot
threshold_count
trigger_reason
triggered_at
reset_count_cycle
reset_time_cycle
```

知识和邮件：

```text
knowledge_snapshot_version
knowledge_package_json
inspection_results_json
email_recipient
email_subject
email_status                  NOT_SENT / SENT / FAILED
email_message_id
email_sent_at
email_error
```

报工：

```text
report_method                 WEB_FORM
report_form_schema_version    REPORT-FORM-1.0
report_type                   NORMAL / ABNORMAL
report_summary
abnormal_items_json
photos_json                   只保存URL或引用，不接收二进制上传
parts_replaced_json
source_fault_id
fault_type
fault_description
standard_repair_hours
actual_work_hours
abnormal_next_action          CONTINUE_PROCESSING / CREATE_REPAIR_TASK
repair_reason
assigned_at
started_at
pause_started_at
paused_seconds
reported_at
completed_at
created_at
updated_at
```

`report_url` 不落库，根据 `MOLDGUARD_PUBLIC_BASE_URL` 与 `work_order_id` 动态生成。

### 8.5 WorkOrderEvent

```text
work_order
event_type
from_status
to_status
operator_id                   可空，仅展示
remarks
event_data_json
request_key                   可空，非空时唯一
created_at
```

所有状态变化都写入事件表。该表同时用于写请求去重后的结果追踪。

### 8.6 MaintenanceRecord

```text
record_id
mold
work_order
record_type
effective_mold_cycles_snapshot
occurred_at
baseline_count_before
baseline_time_before
baseline_count_after
baseline_time_after
reset_count_cycle
reset_time_cycle
knowledge_snapshot_version
actual_work_hours
result
note
request_key                   unique
created_at
```

仅正常完成的业务记录进入履历；异常报工不创建最终履历。

---

## 9. 触发规则

### 9.1 注塑模具

| 规则 ID | 条件 | 工单类型 |
|---|---|---|
| `INJ-COUNT-050K` | 开发吨位 `<1000T` 且周期有效模次达到 50,000 | `CYCLE_COUNT_MAINTENANCE` |
| `INJ-COUNT-030K` | 开发吨位 `>=1000T` 且周期有效模次达到 30,000 | `CYCLE_COUNT_MAINTENANCE` |
| `INJ-TIME-2M` | 最近有效周期保养后 2 个自然月；无记录时从 `first_production_at` 起算 | `CYCLE_TIME_MAINTENANCE` |
| `INJ-NO-OUTPUT-2Y` | 连续 2 年未更新产量 | 停止自动触发，允许手工建单 |

周期计算：

```text
cycle_mold_cycles
= effective_mold_cycles - baseline_effective_mold_cycles
```

边界：

```text
999.99T  → 50,000
1000.00T → 30,000
```

### 9.2 钣金模具

| 规则 ID | mold_category | 类型编码 | 阈值 |
|---|---|---|---:|
| `STAMP-FORM-150K` | `FORMING` | LC102、LC104、LC106、LC107 | 150,000 |
| `STAMP-PUNCH-400K` | `PUNCH_BLANKING` | LC101、LC103、LC105 | 400,000 |
| `STAMP-PROG-400K` | `CONTINUOUS` | LC109 | 400,000 |
| `STAMP-SIDE-400K` | `SIDE_PANEL` | LC109 | 400,000 |

`LC109` 缺少明确 `mold_category` 时返回字段错误，不根据名称或位置推断。

### 9.3 自动扫描与建单

`POST /api/v1/alerts/scan` 在一个事务内完成：

```text
锁定待扫描模具
→ 计算所有适用规则
→ 创建或复用Alert
→ 创建或复用PENDING_ASSIGNMENT工单
→ 返回rule_id、alert_id、work_order_id和触发快照
```

同一模具、同一规则、同一周期版本只能存在一个开放工单。

### 9.4 复位矩阵

正常报工后同时复位产量和时间周期：

```text
CYCLE_COUNT_MAINTENANCE
CYCLE_TIME_MAINTENANCE
REPAIR_SYNC_MAINTENANCE
```

不复位：

```text
LIGHTWEIGHT_DAILY
LIGHTWEIGHT_PRE_PRODUCTION
LIGHTWEIGHT_POST_PRODUCTION
LIGHTWEIGHT_FIXED_FREQUENCY
STORAGE_INSPECTION
REPAIR_TASK本身
异常报工
```

复位值：

```text
baseline_effective_mold_cycles = 报工时有效模次
baseline_maintenance_at = reported_at
cycle_version += 1
```

---

## 10. 候选人员与派工

候选规则：

1. `available=true`；
2. `on_duty=true`；
3. 邮箱存在；
4. 技能包含当前模具类型或本工单所需技能；
5. `current_load < 0.8`；
6. 同产线优先；
7. 技能匹配率降序；
8. 当前负荷升序；
9. 员工编号作为稳定排序兜底。

比赛主路径由平台展示候选人员后调用指定派工：

```http
POST /api/v1/work-orders/{work_order_id}/assign
```

Django在派工时重新校验人员状态，保存派工结果，并返回：

```text
assignee_id
assignee_name
assignee_email
knowledge_snapshot_version
report_method
report_url
report_button_text
report_form_schema_version
```

服务器可以保留自动派工接口作为测试工具，但不作为比赛主流程。

---

## 11. 工单状态机

主流程：

```text
PENDING_ASSIGNMENT
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
```

暂停：

```text
IN_PROGRESS → PAUSED → IN_PROGRESS
```

异常：

```text
ASSIGNED / IN_PROGRESS / PAUSED
→ ABNORMAL_REPORTED
```

继续处理：

```text
ABNORMAL_REPORTED → IN_PROGRESS
```

关联修模：

```text
ABNORMAL_REPORTED
→ 创建子工单 REPAIR_TASK
→ 原工单 REPAIR_LINKED
→ 子工单 COMPLETED
→ 原工单 IN_PROGRESS
→ 重新点检并报工
```

终态：

```text
COMPLETED
CANCELLED
```

正常报工直接完成，不设置待验收和主管验收节点。

---

## 12. 知识库、邮件与报工页面

### 12.1 知识上下文

```http
GET /api/v1/work-orders/{id}/knowledge-context
```

至少返回：

```text
work_order_id
mold_type
mold_category
rule_id
work_order_type
knowledge_profile_code
knowledge_snapshot_version=MOLDGUARD-KB-1.2
query_keywords
required_knowledge_types
```

### 12.2 知识包回写

```http
POST /api/v1/work-orders/{id}/knowledge
```

知识包最小结构：

```json
{
  "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
  "title": "注塑模具周期保养点检",
  "items": [
    {
      "knowledge_id": "CHK-INJ-001",
      "item": "模具外观",
      "criteria": "配件齐全完好无异常",
      "method": "目视",
      "required": true
    }
  ],
  "safety_notes": [],
  "source_documents": []
}
```

一个工单保存最后一份有效知识包。邮件和报工页面必须使用同一版本、同一内容。

### 12.3 邮件上下文

```http
GET /api/v1/work-orders/{id}/email-context
```

返回：

```text
收件邮箱
邮件主题
模具和工单信息
触发依据
要求完成时间
知识包
report_url
report_button_text
report_form_schema_version
```

平台发送邮件后回写：

```http
POST /api/v1/work-orders/{id}/email-result
```

### 12.4 报工页面

```http
GET  /report/{work_order_id}
POST /report/{work_order_id}
```

页面必须：

- 支持手机浏览器；
- 展示工单、模具、触发依据和要求完成时间；
- 展示与邮件一致的点检知识包；
- 逐项填写 `PASS/FAIL/NOT_APPLICABLE`；
- `NOT_APPLICABLE` 必须填写原因；
- `FAIL` 必须填写异常说明；
- 可填写更换件、实际工时和异常后续动作；
- 不接收二进制照片，照片字段只保存URL或文本引用；
- 使用 Django CSRF 防止浏览器重复或跨站误提交；
- 已完成工单再次打开时只显示结果，不允许重复提交。

同时提供 JSON 报工接口：

```http
POST /api/v1/work-orders/{id}/report
```

---

## 13. 正常报工与异常闭环

### 13.1 正常报工条件

- 所有必检项均已提交；
- 所有适用项为 `PASS`；
- 所有 `NOT_APPLICABLE` 项均有原因；
- 无未处理异常；
- `actual_work_hours` 已填写；
- 当前工单状态允许报工；
- 提交人员与被派工人员一致。

事务内执行：

```text
锁定工单、模具和Alert
→ 校验知识包与点检结果
→ 写入报工字段
→ 工单COMPLETED
→ 创建MaintenanceRecord
→ 按复位矩阵更新Mold基线
→ 关闭对应Alert
→ 更新人员负荷
→ 写入WorkOrderEvent
→ 返回下一次阈值和时间
```

### 13.2 异常报工

异常报工：

- 保存异常项目、说明、点检结果、故障候选和可选照片引用；
- 工单进入 `ABNORMAL_REPORTED`；
- 不创建最终 MaintenanceRecord；
- 不关闭 Alert；
- 不复位周期；
- 不占用最终正常报工结果；
- 可继续处理或创建关联修模任务。

### 13.3 幂等

所有写 API 必须提供：

```text
client_request_id
```

HTML 报工表单使用隐藏的 `submission_id`。

相同 ID、相同内容重复提交：返回第一次结果；相同 ID、不同内容：返回 `CLIENT_REQUEST_CONFLICT`。

不额外建立幂等模型时，使用 `WorkOrderEvent.request_key`、`Alert.dedupe_key`、`WorkOrder.create_key` 和 `MaintenanceRecord.request_key` 实现动作级去重。

---

## 14. API 清单

### 14.1 服务

```http
GET /api/v1/health
GET /api/v1/meta
GET /api/schema
GET /api/docs
```

### 14.2 模具与触发

```http
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
POST /api/v1/alerts/scan
GET  /api/v1/alerts
GET  /api/v1/alerts/{alert_id}
POST /api/v1/work-orders/manual
```

### 14.3 人员与派工

```http
GET  /api/v1/staff
GET  /api/v1/work-orders/{id}/candidates
POST /api/v1/work-orders/{id}/assign
POST /api/v1/work-orders/{id}/auto-assign   # 备用测试接口
```

### 14.4 工单与时间线

```http
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{id}
GET  /api/v1/work-orders/{id}/timeline
POST /api/v1/work-orders/{id}/start
POST /api/v1/work-orders/{id}/pause
POST /api/v1/work-orders/{id}/resume
POST /api/v1/work-orders/{id}/cancel
```

### 14.5 知识与邮件

```http
GET  /api/v1/work-orders/{id}/knowledge-context
POST /api/v1/work-orders/{id}/knowledge
GET  /api/v1/work-orders/{id}/email-context
POST /api/v1/work-orders/{id}/email-result
```

### 14.6 报工与修模

```http
GET  /report/{id}
POST /report/{id}
POST /api/v1/work-orders/{id}/report
POST /api/v1/work-orders/{id}/continue-processing
POST /api/v1/work-orders/{id}/create-repair-task
POST /api/v1/work-orders/{id}/repair-completed
```

### 14.7 履历和统计

```http
GET /api/v1/molds/{mold_id}/records
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
```

不提供公开 `/demo/reset` 接口，演示重置使用服务器管理命令完成。

---

## 15. 统一响应与错误

成功：

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {},
  "request_id": "req-..."
}
```

错误：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "data": null,
  "errors": [],
  "request_id": "req-..."
}
```

关键错误码：

```text
MOLD_NOT_FOUND
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
MOLD_CATEGORY_NOT_CONFIGURED
INVALID_LC109_CATEGORY
INVALID_CYCLE_COUNT
DUPLICATE_OPEN_WORK_ORDER
WORK_ORDER_NOT_FOUND
INVALID_WORK_ORDER_STATE
EMPLOYEE_NOT_FOUND
EMPLOYEE_NOT_AVAILABLE
NO_ASSIGNMENT_CANDIDATE
KNOWLEDGE_PACKAGE_REQUIRED
KNOWLEDGE_VERSION_MISMATCH
INSPECTION_ITEMS_INCOMPLETE
NOT_APPLICABLE_REASON_REQUIRED
ABNORMAL_DESCRIPTION_REQUIRED
REPORT_ALREADY_SUBMITTED
CLIENT_REQUEST_CONFLICT
```

---

## 16. 演示数据

至少准备 10 套模具和 4 名员工：

1. 注塑 `<1000T` 达到 50,000；
2. 注塑 `>=1000T` 达到 30,000；
3. 注塑 2 个月时间触发；
4. 注塑连续 2 年无产量更新；
5. 钣金 `FORMING` 达到 150,000；
6. 钣金 `PUNCH_BLANKING` 达到 400,000；
7. 钣金 `CONTINUOUS + LC109` 达到 400,000；
8. 钣金 `SIDE_PANEL + LC109` 达到 400,000；
9. `LC109` 缺少类别的错误场景；
10. 未达到阈值的正常模具。

员工场景：

- 注塑技能人员；
- 钣金技能人员；
- 综合技能但不可用人员；
- 综合技能且高负荷人员。

管理命令：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
```

命令必须幂等，重置后能够稳定恢复所有主演示场景。

---

## 17. 基础统计

### 17.1 summary

返回：

```text
模具总数
开放提醒数
待派工工单数
进行中工单数
异常工单数
已完成工单数
工单完成率
```

### 17.2 work-hours

支持按时间、人员、模具类型筛选，返回：

```text
工单数
标准工时
实际工时
平均工时
工时偏差
```

### 17.3 order-completion

返回：

```text
创建数
完成数
异常数
取消数
完成率
```

Django只返回结构化数字，智能体平台负责解释和生成管理建议。

---

## 18. 部署设计

### 18.1 Docker Compose

服务：

```text
mariadb
api
```

MariaDB：

- 不暴露宿主端口；
- 使用 `runtime/mariadb` 持久化；
- 配置健康检查；
- 使用 `utf8mb4`；
- 采用严格 SQL 模式。

API：

- 绑定宿主 `127.0.0.1:18080`；
- 启动时等待数据库、执行迁移、按空库条件初始化 DEMO 数据；
- Gunicorn 1 worker / 4 threads；
- 日志输出到 stdout；
- Docker 日志轮转。

### 18.2 Nginx

```text
公网HTTP/HTTPS
→ 宿主Nginx
→ 127.0.0.1:18080
→ Django容器
```

Nginx需保留：

- `Host`；
- `X-Real-IP`；
- `X-Forwarded-For`；
- `X-Forwarded-Proto`。

Django通过 `MOLDGUARD_PUBLIC_BASE_URL` 生成公网 `report_url`。

### 18.3 环境变量

```dotenv
DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=
DJANGO_DB_ENGINE=mariadb
DJANGO_DB_HOST=mariadb
DJANGO_DB_PORT=3306
DJANGO_DB_NAME=moldguard
DJANGO_DB_USER=moldguard
DJANGO_DB_PASSWORD=
MOLDGUARD_PUBLIC_BASE_URL=https://moldguard.example.com
MOLDGUARD_KNOWLEDGE_VERSION=MOLDGUARD-KB-1.2
MOLDGUARD_REPORT_SCHEMA_VERSION=REPORT-FORM-1.0
DEMO_EMPLOYEE_1_EMAIL=
DEMO_EMPLOYEE_2_EMAIL=
```

### 18.4 备份

提供 `scripts/backup_mariadb.sh`，备份到 `runtime/backups/`，并执行 gzip 完整性校验。

---

## 19. 测试计划

### 19.1 单元测试

- 注塑 999.99T / 1000T 边界；
- 注塑 50K / 30K 阈值；
- 两个自然月月末计算；
- 两年无产量停止自动触发；
- 钣金四类阈值；
- LC109 显式类别；
- 基准模次大于当前模次；
- 复位矩阵。

### 19.2 API 测试

- 健康检查和 meta；
- 扫描自动建单；
- 重复扫描不重复工单；
- 候选人员排序；
- 指定派工；
- 知识包版本校验；
- 邮件上下文包含 `report_url`；
- 邮件结果成功和失败回写；
- 状态机非法跳转；
- client_request_id 重放和冲突。

### 19.3 Web 报工测试

- 页面可打开并显示工单与知识；
- 正常报工；
- FAIL 强制异常；
- NOT_APPLICABLE 必填原因；
- 重复提交；
- 已完成页面只读；
- 手机宽度下表单可用；
- CSRF 生效。

### 19.4 集成测试

1. 注塑模次触发正常闭环；
2. 注塑 2 个月触发正常闭环；
3. 钣金成型类正常闭环；
4. 异常后继续处理再正常报工；
5. 异常后创建修模任务、修模完成、恢复原工单并正常报工；
6. 邮件发送失败后重新回写成功；
7. 连续 3 次重置和完整演示无数据污染。

### 19.5 部署测试

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py spectacular --file docs/openapi.yaml --validate
docker compose config --quiet
docker compose build
docker compose up -d
curl https://域名/api/v1/health
python scripts/smoke_test.py --base-url https://域名
```

---

## 20. 实施阶段与 Stop Gate

### Phase 0：合同冻结与新分支建立

**建议时间：1个工作日**

任务：

- 从 `main` 创建 `agent/competition-server-v1`；
- 确认 V1.2、V5.0、V3.0、REPORT-FORM-1.0；
- 冻结字段、枚举、API、错误码和 DEMO 数据；
- 测试分支仅登记为参考，不合并代码。

Stop Gate：不存在未解决的字段或状态冲突。

### Phase 1：干净工程骨架

**建议时间：1个工作日**

任务：

- 新建 Django 项目和五个应用；
- 统一响应、异常、Request-ID；
- SQLite/MariaDB双数据库配置；
- OpenAPI；
- pytest、Ruff；
- 初始Dockerfile与Compose。

Stop Gate：health、meta、schema、docs和基础CI通过。

### Phase 2：模型、迁移和演示数据

**建议时间：2个工作日**

任务：

- 建立6个模型；
- 完成约束和索引；
- 创建初始迁移；
- 完成 seed/reset/verify 命令；
- 准备10套模具和4名人员。

Stop Gate：SQLite和MariaDB均能从空库迁移并验证数据。

### Phase 3：触发规则、扫描和自动建单

**建议时间：2个工作日**

任务：

- 注塑和钣金规则服务；
- 两个月时间规则；
- 两年无产量停扫；
- 自动扫描和自动建单；
- 去重与事务；
- 模具和Alert API。

Stop Gate：全部规则边界测试通过，同类工单不重复。

### Phase 4：人员、候选和派工

**建议时间：1个工作日**

任务：

- Employee API；
- 候选筛选与排序；
- 指定派工；
- 备用自动派工；
- 派工响应生成 report_url。

Stop Gate：候选结果稳定，派工状态与负荷正确。

### Phase 5：知识包和邮件衔接

**建议时间：1至2个工作日**

任务：

- knowledge-context；
- knowledge 写入；
- email-context；
- email-result；
- 版本一致性校验。

Stop Gate：邮件上下文包含同一知识包、收件邮箱和报工链接。

### Phase 6：报工页面与正常报工

**建议时间：2个工作日**

任务：

- HTML模板和样式；
- Web/JSON报工接口；
- 点检完整性校验；
- 正常完成；
- 周期复位；
- MaintenanceRecord；
- 页面重复提交保护。

Stop Gate：邮件链接可完成正常闭环并正确产生下一周期。

### Phase 7：异常、继续处理和关联修模

**建议时间：2个工作日**

任务：

- 异常报工；
- continue-processing；
- create-repair-task；
- repair-completed；
- 恢复原工单；
- 最终正常报工。

Stop Gate：异常期间不关闭Alert、不复位，修模后可回到原工单。

### Phase 8：统计、时间线和文档

**建议时间：1个工作日**

任务：

- timeline；
- records；
- summary；
- work-hours；
- order-completion；
- OpenAPI和调用示例。

Stop Gate：统计与数据库明细一致。

### Phase 9：部署与比赛平台联调

**建议时间：2个工作日**

任务：

- Oracle Docker/MariaDB部署；
- Nginx和HTTPS；
- 备份恢复；
- 平台动态变量、知识检索和邮件；
- 连续3次完整演示；
- 形成现场运行手册和回退方案。

Stop Gate：服务器标记 `READY_FOR_COMPETITION`。

### 总周期

```text
建议开发周期：12—15个工作日
```

该周期是完整、干净实现的估算，不采用测试分支代码复用或快速改造假设。

---

## 21. 交付物

- 完整 Django 源码；
- 初始迁移；
- DEMO 数据；
- 两种数据库配置；
- 报工页面；
- OpenAPI 文档；
- API 调用示例；
- 自动化测试；
- HTTP 冒烟脚本；
- Dockerfile；
- compose.yaml；
- Nginx模板；
- MariaDB备份脚本；
- 部署说明；
- 比赛平台联调说明；
- 比赛演示脚本；
- 故障回退清单。

---

## 22. Definition of Done

满足以下条件后，服务器标记为：

```text
READY_FOR_COMPETITION
```

- [ ] 代码从 `main` 干净建立，没有合并测试分支代码和旧迁移；
- [ ] 知识库版本固定为 `MOLDGUARD-KB-1.2`；
- [ ] 注塑和钣金规则与知识库完全一致；
- [ ] 扫描自动建单且不会重复；
- [ ] 候选人员、派工和邮箱可用；
- [ ] 派工响应包含 Django 生成的 `report_url`；
- [ ] 邮件和报工页面使用同一知识包；
- [ ] 正常报工自动完成并按矩阵复位；
- [ ] 异常报工不关闭、不复位；
- [ ] 继续处理和关联修模闭环可用；
- [ ] 工时、完成率和履历查询正确；
- [ ] SQLite和MariaDB测试通过；
- [ ] OpenAPI校验通过；
- [ ] Docker、Nginx和HTTPS部署通过；
- [ ] MariaDB备份与恢复实测通过；
- [ ] 比赛平台连续3次完整演示成功；
- [ ] 演示过程中无5xx、无重复工单、无重复复位；
- [ ] 服务只包含DEMO数据，比赛结束后可安全停止。
