# MoldGuard 比赛服务器快速代码实施计划

- **计划状态**：`IMPLEMENTATION_READY_FAST_TRACK`
- **版本**：V1.0
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **测试代码基线**：`agent/platform-capability-probe-v1@2ed0b59bbf74c5171860481ab2b1de2294bbfc9d`
- **业务与知识基线**：`main` 分支的 `MOLDGUARD-KB-1.2`、V4.2、V3.0、`REPORT-FORM-1.0`
- **目标实施分支**：`agent/competition-server-v1`
- **目标部署**：Oracle Linux 主机 + Docker Compose + MariaDB + 宿主 Nginx
- **数据性质**：`DEMO ONLY`

---

## 1. 计划目的

测试分支已经完成可运行的 Django/DRF 服务、基础模具规则、预警、工单、派工、知识快照、邮件结果回写、开工/暂停/恢复、正常/异常报工、幂等、测试和 Docker/MariaDB 部署。

当前不再从空仓库重新开发，而是：

```text
复用测试分支现有代码
→ 同步最终知识库 MOLDGUARD-KB-1.2
→ 改造触发规则和字段契约
→ 增加邮件报工链接网页
→ 补齐正常/异常报工闭环
→ 补齐基础统计
→ 直接部署为比赛服务器
```

最终比赛链路：

```text
扫描模具触发条件并自动建单
→ 查询候选人员并派工
→ 平台检索点检知识
→ 平台发送含点检知识和 report_url 的邮件
→ 被派工人员点击链接报工
→ 正常报工自动完成并复位
→ 异常报工继续处理或关联修模
→ 查询工时、完成率和模具履历
```

---

## 2. 测试分支代码审查结论

### 2.1 分支状态

```text
测试分支：agent/platform-capability-probe-v1
HEAD：2ed0b59bbf74c5171860481ab2b1de2294bbfc9d
相对 main：ahead 12 / behind 65 / diverged
```

因此禁止直接把测试分支快进或强行覆盖 `main`。应从测试分支 HEAD 创建新的比赛实施分支，再选择性同步 `main` 的最终知识库和权威文档。

### 2.2 已完成且应直接复用

| 能力 | 当前完成情况 | 比赛版处理 |
|---|---|---|
| Django 5.2 / DRF 3.16 工程 | 已完成 | 原样复用 |
| 统一 JSON 响应与 Request-ID | 已完成 | 原样复用 |
| 统一异常码 | 已完成 | 原样复用并改服务命名 |
| `client_request_id` 幂等 | 已完成，支持同内容重放和冲突检测 | 原样复用 |
| 数据库事务与 `select_for_update` | 已用于扫描、派工、报工 | 原样复用 |
| 模具/预警/人员/工单 API | 已完成旧版流程 | 改造字段和规则 |
| 指定派工与自动派工 | 已完成 | 以指定派工为比赛主路径，自动派工作备用 |
| 知识快照与邮件结果 | 已完成独立模型和接口 | 保留模型，改为 KB 1.2 契约 |
| 开工/暂停/恢复 | 已完成 | 保留 |
| 正常报工 | 已完成并可原子复位周期 | 改为 KB 1.2 复位矩阵 |
| 异常报工 | 已完成基础保存 | 增加继续处理与关联修模 |
| 管理命令 | 已有 seed/reset/verify | 改为 competition 数据命令或兼容别名 |
| API 测试 | 已有 7 个 API 测试模块 | 更新旧断言并增补 KB 1.2 测试 |
| 集成/单元测试 | 已有 1 个集成模块、1 个规则单元模块 | 继续扩展 |
| HTTP 冒烟测试 | 已有 `scripts/smoke_test.py` | 改成比赛全链路 |
| Docker / MariaDB / Gunicorn | 已完成 | 比赛部署直接复用 |
| Nginx 反向代理与备份 | 已完成 | 更新域名和服务名称后复用 |

### 2.3 不能直接作为比赛版的部分

1. 当前所有模具都按开发吨位 30K/50K 触发；最终知识库要求钣金按 150K/400K 分类触发。
2. 当前注塑两个月只生成提醒，并禁止创建工单；最终知识库要求自动建立时间周期工单。
3. 当前扫描与创建工单是两个动作；最终流程要求扫描达到条件时自动建单。
4. 当前字段仍使用 `current_count/cycle_baseline_count/cycle_baseline_time`；对外契约必须使用 KB 1.2 字段名称。
5. 当前没有 `/report/{work_order_id}` HTML 报工页面，也没有 Django 生成的 `report_url`。
6. 当前邮件上下文不包含 `report_url`、表单版本和完整知识包。
7. 当前异常报工是终止状态，没有“继续处理/关联修模/修模完成后回原工单”。
8. 当前异常报工同时创建 `WorkReport`，会占用正常报工的 OneToOne 关系，无法在异常处理后再次正常报工。
9. 当前没有钣金 `mold_category/mold_type_code`、注塑 `first_production_at`、位置和产量更新时间字段。
10. 当前没有比赛所需的基础统计 API。
11. `/probe/*` 及 `ProbeRun/ProbeStep` 只用于平台探测，不应出现在最终比赛主流程。

---

## 3. 快速实施原则

### 3.1 不重写工程

为节省时间，本轮不做以下重构：

```text
不拆分 platform_probe 为多个 Django app
不把现有十多个模型强制压缩成六个模型
不删除旧迁移
不重命名 app label
不重写统一响应、异常、幂等和事务层
不从 main 空白代码重新搭骨架
```

`main` 中 V3.0 的六模型设计继续作为业务字段参考，但比赛实现允许保留测试分支中已经稳定工作的独立模型：

```text
KnowledgeSnapshot
NotificationReceipt
PauseSegment
WorkReport
AbnormalReport
MaintenanceHistory
ClientRequestRecord
ProbeRun
ProbeStep
```

比赛后再做模型合并和清理。

### 3.2 对外契约必须使用 KB 1.2 命名

数据库内部可以暂时保留旧列名：

```text
current_count
cycle_baseline_count
cycle_baseline_time
```

API、序列化器、知识上下文、邮件和报工页面统一输出：

```text
effective_mold_cycles
baseline_effective_mold_cycles
baseline_maintenance_at
cycle_mold_cycles
```

通过 serializer alias / model property 实现，不为改字段名执行高风险数据库重建。

### 3.3 比赛运行使用现有 MariaDB 部署

本地测试仍可使用 SQLite；比赛服务器使用已经完成的：

```text
Docker Compose
MariaDB 11.8
Gunicorn 1 worker / 4 threads
宿主 Nginx HTTPS
宿主持久化 runtime/mariadb
```

不在比赛前临时改回 SQLite。

---

## 4. 分支与同步策略

### 4.1 创建比赛实施分支

```bash
git fetch origin
git switch -c agent/competition-server-v1 \
  origin/agent/platform-capability-probe-v1
```

### 4.2 同步最终知识与权威文档

从 `origin/main` 选择性取回：

```text
knowledge-base/
docs/README.md
docs/plans/2026-08-12-moldguard-django-implementation-plan.md
docs/models/2026-08-13-django-model-field-review.md
docs/contracts/2026-08-13-mail-report-link-contract.md
docs/architecture/2026-08-12-agent-platform-django-relationship.md
docs/business/2026-08-12-moldguard-business-scenarios.md
docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md
docs/decisions/
```

保留测试分支中的：

```text
docs/deployment-oracle-mariadb.md
docs/platform-test-guide.md
Dockerfile
compose.yaml
deploy/nginx/
scripts/
apps/
config/
tests/
```

不要直接执行无条件 `git merge main`，避免 README 和历史方案冲突吞掉现有代码说明。

---

## 5. P0 数据模型改造

只新增迁移，不删除现有表。建议从 `0007_competition_kb12_fields.py` 开始。

### 5.1 Mold 增加字段

```text
first_production_at
mold_category              FORMING / PUNCH_BLANKING / CONTINUOUS / SIDE_PANEL
mold_type_code             LC101 / LC102 / ... / LC109
level_1_location
level_2_location
production_line
output_updated_at
knowledge_profile_code
```

兼容属性：

```python
effective_mold_cycles = current_count
baseline_effective_mold_cycles = cycle_baseline_count
baseline_maintenance_at = cycle_baseline_time
```

### 5.2 MaintenanceAlert 增加字段

```text
rule_id
work_order_type
trigger_reason
triggered_at
```

唯一性从“模具 + alert_type + cycle_version”调整为能够区分规则的：

```text
mold + rule_id + cycle_version
```

### 5.3 WorkOrder 增加字段

```text
rule_id
work_order_type
parent_work_order
reset_count_cycle
reset_time_cycle
effective_mold_cycles_snapshot
baseline_effective_mold_cycles_before
baseline_maintenance_at_before
cycle_mold_cycles_snapshot
threshold_count
trigger_reason
triggered_at
active_knowledge_snapshot
knowledge_snapshot_version
report_method                WEB_FORM
report_form_schema_version   REPORT-FORM-1.0
report_type                  NORMAL / ABNORMAL
report_summary
actual_work_hours
abnormal_next_action
repair_reason
```

状态增加：

```text
REPAIR_LINKED
```

### 5.4 KnowledgeSnapshot

保留现有表，新增或冻结：

```text
catalog_version 必须为 MOLDGUARD-KB-1.2
items_json 保存邮件与报工页面使用的同一份点检知识
WorkOrder.active_knowledge_snapshot 指向当前有效快照
```

### 5.5 NotificationReceipt

保留现有表，继续记录每次平台邮件回写；工单详情额外返回最后一次邮件状态。

### 5.6 WorkReport 与 AbnormalReport

- `WorkReport` 只用于最终正常报工；保留 OneToOne。
- 异常报工不得再创建 `WorkReport`，避免后续正常报工冲突。
- `AbnormalReport.work_order` 从 OneToOne 调整为 ForeignKey，允许继续处理后再次异常报工。
- `AbnormalReport` 增加：

```text
abnormal_items_json
photos_json
parts_replaced_json
source_fault_id
fault_type
fault_description
standard_repair_hours
actual_work_hours
next_action
```

### 5.7 MaintenanceHistory

保留现有表并增加：

```text
work_order_type
reset_count_cycle
reset_time_cycle
knowledge_snapshot_version
actual_work_hours
baseline_count_before / after
baseline_time_before / after
```

---

## 6. P0 触发规则改造

重写 `services/trigger_service.py`，输出统一 `TriggerDecision`：

```text
rule_id
work_order_type
is_due
threshold_count
cycle_mold_cycles
trigger_reason
reset_count_cycle
reset_time_cycle
knowledge_profile_code
```

### 6.1 注塑

```text
INJ-COUNT-050K：development_tonnage < 1000，50,000模次
INJ-COUNT-030K：development_tonnage >= 1000，30,000模次
INJ-TIME-2M：baseline_maintenance_at + 2个月；无有效基线时使用 first_production_at
INJ-NO-OUTPUT-2Y：output_updated_at 超过2年，停止自动触发
```

`INJ-TIME-2M` 必须自动创建 `CYCLE_TIME_MAINTENANCE` 工单，不再只是提醒。

### 6.2 钣金

```text
STAMP-FORM-150K       FORMING         150,000
STAMP-PUNCH-400K      PUNCH_BLANKING  400,000
STAMP-PROG-400K       CONTINUOUS      400,000
STAMP-SIDE-400K       SIDE_PANEL      400,000
```

`mold_type_code=LC109` 且没有明确 `mold_category` 时返回：

```text
MOLD_CATEGORY_REQUIRED
```

不得按名称或位置猜测。

### 6.3 扫描自动建单

改造 `scan_molds()`：

```text
扫描模具
→ 计算所有到期规则
→ 创建或复用 Alert
→ 同一事务自动创建或复用 PENDING_ASSIGNMENT WorkOrder
→ 返回 alert_id + work_order_id
```

保留旧接口：

```text
POST /alerts/{alert_id}/create-work-order
```

但在 OpenAPI 标记为 deprecated，仅作为旧平台流程兼容入口。

去重键至少包含：

```text
mold_id + rule_id + cycle_version
```

---

## 7. P0 人员与派工改造

复用现有派工服务，补充：

```text
Employee.on_duty
Employee.production_line
current_load 继续使用0—100整数百分比，比赛前不改Decimal
```

候选条件：

```text
available = true
on_duty = true
current_load < 80
技能包含模具类型或工单所需技能
同产线优先
低负荷优先
```

派工响应必须包含：

```text
assignee_id
assignee_name
assignee_email
knowledge_snapshot_version=MOLDGUARD-KB-1.2
report_method=WEB_FORM
report_url
report_button_text=提交报工情况
report_form_schema_version=REPORT-FORM-1.0
```

增加环境变量：

```text
MOLDGUARD_PUBLIC_BASE_URL=https://moldguard.example.com
```

`report_url` 使用该变量加反向路由生成；未配置时才使用 `request.build_absolute_uri()`。

---

## 8. P0 知识与邮件上下文

### 8.1 知识上下文

`GET /work-orders/{id}/knowledge-context` 返回：

```text
MOLDGUARD-KB-1.2
rule_id
work_order_type
mold_type
development_tonnage
mold_category
mold_type_code
knowledge_profile_code
required_knowledge_types
```

不得再固定返回 `MAINT_TRIGGER_TONNAGE_V1`。

### 8.2 知识快照

`POST /work-orders/{id}/knowledge-snapshot`：

- 只接受 `catalog_version=MOLDGUARD-KB-1.2`；
- 保存点检项目、判定标准、安全要求和来源 ID；
- 设置 `WorkOrder.active_knowledge_snapshot`；
- 返回 `snapshot_id`。

### 8.3 邮件上下文

`GET /work-orders/{id}/email-context` 必须返回：

```text
to
subject
work_order
trigger_basis
knowledge_package
report_url
report_button_text
report_form_schema_version
knowledge_snapshot_version
```

平台发送后继续使用现有 notifications 接口回写结果。

---

## 9. P0 邮件报工页面与 API

### 9.1 页面路由

新增：

```http
GET  /report/{work_order_id}
POST /report/{work_order_id}
```

新增模板：

```text
templates/report_form.html
templates/report_result.html
```

页面无需登录，展示：

```text
工单、模具、被派工人员、触发依据、要求完成时间
知识快照版本
本次点检知识包
正常/异常报工字段
```

### 9.2 JSON 接口

新增统一接口：

```http
POST /api/v1/work-orders/{work_order_id}/report
```

请求遵循 `REPORT-FORM-1.0`：

```text
report_type
report_summary
inspection_results
abnormal_items
photos
parts_replaced
source_fault_id
actual_work_hours
abnormal_next_action
client_request_id
```

保留旧接口作为兼容别名：

```text
report-complete
report-abnormal
```

### 9.3 正常报工

```text
校验被派工人员和有效知识快照
→ 校验全部必检项
→ 校验 PASS / NOT_APPLICABLE 原因
→ 创建 WorkReport
→ COMPLETED
→ 按 reset_count_cycle / reset_time_cycle 更新基线
→ 创建 MaintenanceHistory
→ 关闭对应 Alert
→ 释放人员负荷
```

不是所有工单都复位周期，必须按知识库矩阵执行。

### 9.4 异常报工

```text
保存 AbnormalReport
→ ABNORMAL_REPORTED
→ 不创建最终 WorkReport
→ 不关闭 Alert
→ 不复位周期
→ 不释放原被派工人员负荷
```

新增：

```http
POST /work-orders/{id}/continue-processing
POST /work-orders/{id}/create-repair-task
POST /work-orders/{id}/repair-completed
```

流程：

```text
ABNORMAL_REPORTED → IN_PROGRESS
ABNORMAL_REPORTED → REPAIR_LINKED
REPAIR_LINKED → IN_PROGRESS
```

关联修模任务继续使用同一个 `WorkOrder` 模型，`work_order_type=REPAIR_TASK`，通过 `parent_work_order` 关联。

---

## 10. P0/P1 统计

### P0 必须

```http
GET /api/v1/molds/{mold_id}/records
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
```

只做数据库聚合 JSON，不生成图表和文件。

### P1 延后

```text
同比/环比
趋势预测
成本与备件
复杂停机分析
Excel/Word导出
```

---

## 11. 平台探测代码处理

为了避免大规模迁移，本轮保留：

```text
ProbeRun
ProbeStep
probe_report_service.py
```

但新增环境变量：

```text
ENABLE_PLATFORM_PROBE_ENDPOINTS=false
```

比赛默认不注册 `/api/v1/probe/*` 路由；本地平台能力复测时才启用。

Health/Meta 改名为：

```text
service = moldguard-competition-server
version = 1.0.0-competition
knowledge_version = MOLDGUARD-KB-1.2
deployment_status = READY_FOR_COMPETITION
```

---

## 12. 演示数据改造

新增：

```text
data/competition_data.json
```

至少覆盖：

1. 注塑 `<1000T` 达到 50,000；
2. 注塑 `>=1000T` 达到 30,000；
3. 注塑两个月时间工单；
4. 注塑两年无产量停扫；
5. 钣金成型 150,000；
6. 钣金冲孔落料 400,000；
7. 钣金连续模 LC109；
8. 钣金边板 LC109；
9. LC109 缺少分类错误；
10. 正常报工并复位；
11. 异常报工继续处理；
12. 异常报工关联修模；
13. 邮件成功和失败回写。

管理命令：

```text
seed_competition_data
reset_competition_data
verify_competition_data
```

旧 `seed_probe_data` 保留用于测试分支兼容，但比赛容器入口改用 competition 命令。

---

## 13. 测试改造

### 13.1 直接保留

```text
健康检查
统一错误响应
Request-ID
幂等重放与冲突
指定/自动派工并发保护
暂停区间和时间范围校验
知识快照和邮件回写
Docker构建
```

### 13.2 更新旧测试

删除或改写以下旧断言：

```text
钣金按吨位30K/50K
注塑2个月只提醒且禁止建单
扫描后必须另调create-work-order
异常报工创建最终WorkReport
所有正常报工一律复位周期
```

### 13.3 新增必测

- 注塑 999.99T / 1000T 边界；
- 注塑首次生产日期和两个月自动建单；
- 钣金四分类及 150K/400K；
- LC109 类别缺失；
- 同一规则同一周期只建一个工单；
- 派工响应中的 `report_url` 使用公网基址；
- 报工页面显示活动知识快照；
- HTML 正常/异常提交；
- 正常报工直接完成并按矩阵复位；
- 异常报工不复位，可继续处理；
- 关联修模任务完成后恢复原工单；
- 重复正常报工不重复履历和周期复位；
- MariaDB 容器重启后数据仍存在；
- 连续 3 次完整闭环无 5xx 和重复工单。

---

## 14. 快速实施阶段

### Phase 0｜分支与基线同步（1—2小时）

- 创建 `agent/competition-server-v1`；
- 同步 main 的 KB 1.2 与权威文档；
- 保存测试分支 HEAD 和数据库备份；
- 更新 README 为比赛服务器。

**Stop Gate A**：代码、知识库和部署文件同时存在，工作树干净。

### Phase 1｜字段与迁移（3—4小时）

- 新增 Mold/Alert/WorkOrder/AbnormalReport/MaintenanceHistory 字段；
- 增加兼容 alias；
- 迁移 SQLite 与 MariaDB；
- 保证旧探测数据可迁移或可安全重置。

**Stop Gate B**：`migrate`、`makemigrations --check`、旧测试基础用例通过。

### Phase 2｜触发与自动建单（4—5小时）

- 重写注塑和钣金规则；
- 两个月自动建单；
- 扫描原子建单和去重；
- 新演示数据与验证命令。

**Stop Gate C**：所有规则边界和自动建单测试通过。

### Phase 3｜知识、邮件与报工链接（4—6小时）

- KB 1.2 知识上下文；
- 活动知识快照；
- email-context 增加 report_url；
- HTML 报工页面；
- 统一 report API。

**Stop Gate D**：测试邮箱中的链接能打开正确工单和同一知识快照。

### Phase 4｜正常/异常闭环（3—5小时）

- 正常报工直接完成及复位矩阵；
- 异常报工不创建最终 WorkReport；
- 继续处理；
- 简化关联修模任务；
- 基础履历与统计。

**Stop Gate E**：正常、异常继续处理、异常关联修模三条路径均通过。

### Phase 5｜部署与比赛联调（3—4小时）

- 更新 compose 环境变量、入口命令和 Nginx；
- MariaDB 备份；
- 公网 HTTPS 健康检查；
- 平台动态邮箱、知识检索、邮件按钮和结果回写；
- 连续 3 次完整演示。

**Stop Gate F**：`READY_FOR_COMPETITION`。

### 预计总投入

```text
最快P0可演示：12—16小时
含异常修模与统计：18—24小时
```

---

## 15. 部署计划

沿用当前 compose，不重建基础设施。

新增环境变量：

```dotenv
MOLDGUARD_PUBLIC_BASE_URL=https://moldguard.oracle.19970219.xyz
MOLDGUARD_KNOWLEDGE_VERSION=MOLDGUARD-KB-1.2
MOLDGUARD_REPORT_SCHEMA_VERSION=REPORT-FORM-1.0
ENABLE_PLATFORM_PROBE_ENDPOINTS=false
```

部署：

```bash
git fetch origin
git switch agent/competition-server-v1
git pull --ff-only

docker compose config --quiet
docker compose up -d --build
docker compose ps

docker compose exec api python manage.py migrate --noinput
docker compose exec api python manage.py seed_competition_data --if-empty
docker compose exec api python manage.py verify_competition_data

curl -fsS https://moldguard.oracle.19970219.xyz/api/v1/health
```

比赛前备份：

```bash
./scripts/backup_mariadb.sh
```

---

## 16. 质量门禁

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py verify_competition_data
python scripts/smoke_test.py
docker compose config --quiet
docker build .
```

远程验证：

```text
GET /api/v1/health
GET /api/v1/meta
POST /api/v1/alerts/scan
POST /api/v1/work-orders/{id}/assign
GET /api/v1/work-orders/{id}/email-context
GET /report/{id}
POST /api/v1/work-orders/{id}/report
GET /api/v1/analytics/summary
```

---

## 17. Definition of Done

达到以下条件才能标记：

```text
READY_FOR_COMPETITION
```

- [ ] 实施分支来源于测试分支 HEAD，不重新搭建工程；
- [ ] 已同步 `MOLDGUARD-KB-1.2`；
- [ ] 注塑和钣金触发规则完全符合知识库；
- [ ] 扫描能够自动建单且不重复；
- [ ] 派工响应包含 Django 生成的公网 `report_url`；
- [ ] 邮件与报工页面使用同一知识快照；
- [ ] 正常报工直接完成并按矩阵复位；
- [ ] 异常报工不复位，可继续处理或关联修模；
- [ ] 基础工时、完成率和履历可查询；
- [ ] MariaDB 数据重启后保持；
- [ ] seed/reset/verify 可恢复演示；
- [ ] 全量测试通过；
- [ ] 比赛平台连续 3 次完整演示无 5xx、无重复工单、无重复复位。

---

## 18. 最终实施决策

```text
代码起点：agent/platform-capability-probe-v1@2ed0b59
最终知识：MOLDGUARD-KB-1.2
目标分支：agent/competition-server-v1
本地测试数据库：SQLite
比赛数据库：MariaDB
对外入口：Nginx HTTPS
鉴权：无
邮件发送：比赛平台
报工入口：Django report_url
实施策略：增量改造，不重写、不压缩现有模型
```
