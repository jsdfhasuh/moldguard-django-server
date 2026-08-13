# MoldGuard 一天后端优先实施计划

> **邮件责任覆盖说明（2026-08-13）**：本文的 `email-result` 和平台发信步骤是历史
> 计划，已由 `docs/decisions/2026-08-13-django-smtp-delivery.md` 覆盖。正式接口为
> `POST /api/v1/work-orders/{id}/send-email`，由 Django 通过 SMTP 发信。

- **状态**：`IMPLEMENTATION_READY_ONE_DAY`
- **版本**：V1.0
- **日期**：2026-08-13
- **目标分支**：`agent/competition-server-v1`
- **代码基线**：从 `main` 干净创建
- **业务基线**：`MOLDGUARD-KB-1.2`
- **架构基线**：完整实施计划 V5.0
- **阻塞项决议**：V5.1
- **模型字段**：V3.1
- **报工契约**：`REPORT-FORM-1.1`
- **开发方式**：Codex先一次性完成后端P0，再按测试失败逐项Debug

## 1. 一天目标

当天结束前必须得到一套可以部署并供比赛平台调用的后端，至少完成：

```text
健康检查
→ DEMO数据初始化
→ 模具扫描
→ 自动建立正式保养工单
→ 候选人员查询
→ 指定派工
→ 知识包回写
→ 邮件上下文和report_url
→ 正常/异常JSON报工
→ 正常完成、履历和周期复位
→ 幂等与重复工单保护
→ Docker/MariaDB部署
```

当天不追求一次写完所有页面样式和高级统计。先把后端事务闭环写出来，再依次执行单元测试、API测试、集成测试、Docker测试和平台联调。

## 2. 分支准备

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c agent/competition-server-v1
git push -u origin agent/competition-server-v1
```

禁止：

```text
merge agent/platform-capability-probe-v1
cherry-pick测试分支提交
复制测试分支迁移
继续使用platform_probe应用
```

测试分支仅作为设计参考。

## 3. 后端P0范围

### 3.1 工程

```text
Python 3.12
Django 5.2
Django REST Framework 3.16
SQLite本地测试
MariaDB比赛部署
DRF AllowAny
统一JSON响应
Request-ID
ClientRequestRecord幂等
OpenAPI
pytest
Ruff
```

### 3.2 应用

```text
apps/common
apps/molds
apps/staff
apps/workorders
apps/analytics
```

### 3.3 持久化模型

业务模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

技术模型：

```text
ClientRequestRecord
```

### 3.4 必须实现的API

```http
GET  /api/v1/health
GET  /api/v1/meta
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
POST /api/v1/alerts/scan
GET  /api/v1/alerts
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{id}
GET  /api/v1/work-orders/{id}/candidates
POST /api/v1/work-orders/{id}/assign
GET  /api/v1/work-orders/{id}/knowledge-context
POST /api/v1/work-orders/{id}/knowledge
GET  /api/v1/work-orders/{id}/email-context
POST /api/v1/work-orders/{id}/email-result
POST /api/v1/work-orders/{id}/report
GET  /api/v1/work-orders/{id}/timeline
GET  /api/v1/molds/{mold_id}/records
GET  /api/v1/analytics/summary
```

P1接口：

```http
GET  /report/{id}
POST /report/{id}
POST /api/v1/work-orders/{id}/continue-processing
POST /api/v1/work-orders/{id}/create-repair-task
POST /api/v1/work-orders/{id}/repair-completed
POST /api/v1/tracking/scan
GET  /api/v1/work-orders/overdue
GET  /api/v1/analytics/work-hours
GET  /api/v1/analytics/order-completion
```

## 4. Codex开发顺序

### Batch A：一次性完成后端P0

Codex应先实现完整P0，不在中途等待人工确认：

```text
A1 工程骨架和配置
A2 7个模型、约束、索引和初始迁移
A3 seed/reset/verify演示数据命令
A4 注塑、钣金触发服务
A5 扫描、合并触发、Alert和自动建单
A6 候选人员与指定派工
A7 知识包、内容哈希和锁定
A8 邮件上下文与邮件结果回写
A9 JSON正常/异常报工
A10 履历、周期复位、时间线和summary
A11 OpenAPI、测试骨架和冒烟脚本
A12 Dockerfile、Compose、Gunicorn、MariaDB配置
```

Batch A完成条件：

```text
代码可导入
迁移可生成
manage.py check通过
核心URL全部存在
```

### Batch B：运行测试并按失败类型Debug

依次执行：

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest tests/unit -q
pytest tests/api -q
pytest tests/integration -q
python manage.py migrate
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
python scripts/smoke_test.py
```

Debug顺序：

```text
导入和迁移错误
→ 模型约束错误
→ 规则计算错误
→ 状态机和事务错误
→ 幂等错误
→ API序列化错误
→ 集成链路错误
→ 部署错误
```

每修复一类问题后重新运行对应最小测试，不要每次都先跑全量。

### Batch C：P1页面和异常闭环

核心后端通过后再实现：

```text
Django HTML报工页面
WhiteNoise静态文件
CSRF和HTTPS代理配置
continue-processing
create-repair-task
repair-completed
tracking/overdue
work-hours/order-completion
```

### Batch D：部署与平台联调

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
curl http://127.0.0.1:18080/api/v1/health
curl https://正式域名/api/v1/health
python scripts/smoke_test.py --base-url https://正式域名
```

随后在比赛平台验证：

```text
POST扫描
读取work_order_id
读取候选数组
指定派工
回写知识包
读取动态邮箱和report_url
发送邮件
回写邮件结果
点击report_url
提交报工
查询完成结果
```

## 5. 一天时间安排

| 时间 | 目标 |
|---|---|
| 第0—0.5小时 | 创建分支，Codex读取全部权威文档 |
| 第0.5—4小时 | Batch A：完成后端P0代码 |
| 第4—6小时 | 模型、规则、API单元测试与Debug |
| 第6—7小时 | 正常/异常集成链路与幂等Debug |
| 第7—8小时 | 运行最小平台能力验证 |
| 第8—9.5小时 | HTML报工页面、CSRF、静态文件 |
| 第9.5—10.5小时 | 异常继续处理、关联修模、基础统计 |
| 第10.5—12小时 | Docker/MariaDB/Nginx部署和全链路演示 |

如实际只有8小时，优先完成前8小时内容；关联修模、tracking和高级页面样式允许后补。

## 6. 触发实现要求

### 6.1 注塑

```text
INJ-COUNT-050K：development_tonnage < 1000，周期模次 >= 50,000
INJ-COUNT-030K：development_tonnage >= 1000，周期模次 >= 30,000
INJ-TIME-2M：基准保养时间或首次生产时间 + 2个自然月
INJ-NO-OUTPUT-2Y：output_updated_at距今满2年后停止自动建单
```

### 6.2 钣金

```text
STAMP-FORM-150K：FORMING，150,000
STAMP-PUNCH-400K：PUNCH_BLANKING，400,000
STAMP-PROG-400K：CONTINUOUS + LC109，400,000
STAMP-SIDE-400K：SIDE_PANEL + LC109，400,000
```

### 6.3 合并触发

同一注塑模具的模次与时间同时到期时只生成一张正式工单：

```text
primary_rule_id = 模次规则
matched_rule_ids_json = [模次规则, INJ-TIME-2M]
work_order_type = CYCLE_COUNT_MAINTENANCE
```

## 7. 报工实现要求

### 7.1 无身份输入

客户端不提交员工编号。服务端直接使用工单 `assignee`。

### 7.2 NORMAL

允许状态：

```text
ASSIGNED
IN_PROGRESS
```

要求：

```text
全部required点检项已提交
无FAIL
NOT_APPLICABLE有原因
actual_work_hours > 0
```

事务：

```text
锁定工单、模具、Alert
→ 写报工结果
→ COMPLETED
→ 创建MaintenanceRecord
→ 按复位矩阵更新基线和cycle_version
→ 关闭Alert
→ 写事件
→ 返回下一次到期条件
```

### 7.3 ABNORMAL

允许状态：

```text
ASSIGNED
IN_PROGRESS
PAUSED
```

要求：

```text
至少一个FAIL或abnormal_item
异常说明非空
```

结果：

```text
ABNORMAL_REPORTED
不创建最终MaintenanceRecord
不关闭Alert
不复位周期
```

## 8. DEMO数据

至少包含：

```text
10套模具
4名员工
1套count+time同时命中注塑模具
1套LC109缺少类别错误模具
1张正常报工工单
1张异常报工工单
1条邮件成功记录
1条邮件失败记录
```

候选人员规则固定：

```text
skills_json包含mold_type
available=true
on_duty=true
current_load<0.8
邮箱存在
```

`current_load`不自动修改。

## 9. 最小测试清单

### 9.1 规则

```text
999.99T / 1000T
49,999 / 50,000
29,999 / 30,000
2个自然月月末
两年停扫
钣金4类
LC109缺少类别
count+time合并
```

### 9.2 事务与去重

```text
重复scan不重复Alert和工单
相同client_request_id重放
相同ID不同请求冲突
重复正常报工不重复履历和复位
```

### 9.3 报工

```text
ASSIGNED直接正常报工
FAIL不能走NORMAL
NOT_APPLICABLE缺原因失败
ABNORMAL不关闭Alert、不复位
```

### 9.4 知识和邮件

```text
无知识包不能生成email-context
知识版本错误拒绝
email SENT后知识包锁定
邮件上下文和报工页面hash一致
report_url使用公网base URL
```

## 10. Codex主提示词

将下面内容作为首次开发提示词：

```text
你正在仓库 jsdfhasuh/moldguard-django-server 开发 MoldGuard 比赛服务器。

先阅读且只以以下文件为权威：
1. knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md
2. knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md
3. docs/plans/2026-08-12-moldguard-django-implementation-plan.md
4. docs/decisions/2026-08-13-v5.1-blocker-resolution.md
5. docs/models/2026-08-13-django-model-field-review.md
6. docs/contracts/2026-08-13-mail-report-link-contract.md
7. docs/plans/2026-08-13-moldguard-one-day-backend-first-plan.md

从 main 创建的 agent/competition-server-v1 分支干净实现。不要合并、cherry-pick或复制 agent/platform-capability-probe-v1 的代码和迁移；它只能作为技术经验参考。

本轮先一次性完成P0后端，不在中途等待人工确认。实现：
- Django 5.2、DRF 3.16、SQLite/MariaDB双配置；
- apps/common、molds、staff、workorders、analytics；
- 6个业务模型 + ClientRequestRecord技术模型；
- 初始迁移、seed/reset/verify命令；
- 注塑和钣金最终触发规则；
- 同周期count+time合并为一张工单；
- scan自动创建Alert和WorkOrder；
- 候选人员、指定派工；
- knowledge-context、知识包回写、hash和邮件发送后锁定；
- email-context、email-result、Django生成report_url；
- JSON NORMAL/ABNORMAL报工；
- 正常完成、履历、周期复位；异常不结单不复位；
- 统一响应、Request-ID、client_request_id精确重放；
- health/meta/OpenAPI；
- 单元、API、集成测试骨架；
- Dockerfile、compose.yaml、Gunicorn、MariaDB配置、smoke_test.py。

严格执行：
- 无登录、无主管、无API鉴权；
- 报工客户端不提交employee_id，服务器使用work_order.assignee；
- current_load为固定DEMO值，不自动变更；
- 未配置standard_hours时返回null，不猜测；
- 正常报工允许ASSIGNED直接完成；
- email_status=SENT后知识包不可覆盖；
- 所有写接口要求client_request_id；
- 不实现/probe接口；
- 不实现历史文件导入；
- 不创建旧版多余模型。

实现后先运行：
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest tests/unit -q
pytest tests/api -q
pytest tests/integration -q

修复所有失败，最后提交代码和测试结果。不要修改知识库正文，不要降低测试断言来掩盖实现问题。
```

## 11. 当天完成标准

### 最低可部署

```text
P0后端全部完成
核心测试通过
Docker/MariaDB可启动
正式域名health可访问
平台能完成扫描→派工→邮件上下文→JSON报工
```

### 完整比赛演示

```text
增加HTML报工页面
邮件按钮可打开页面
异常继续处理或关联修模可演示
基础统计与tracking可查询
连续3次完整流程无重复工单、无重复复位、无5xx
```
