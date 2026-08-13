# MoldGuard Platform Capability Probe Server

MoldGuard 是一个供比赛智能体平台直接调用的开放 Django 测试服务器。它用模拟模具、模拟员工和 `example.com` 邮箱验证动态 HTTP 工作流，不是生产系统。

当前分支的权威基线是 [平台能力探测实施计划](docs/plans/2026-08-13-moldguard-platform-capability-probe-implementation-plan.md)。与 `main` 的完整 V3/V4 方案不同，本实现明确：

- 不登录、不鉴权、不使用 Token/JWT/API Key；所有业务 API 均为 DRF `AllowAny`；
- 不存在主管、计划员、验收人或审批角色；
- 不建立 `MaintenancePlan`，流程是“预警 → 工单”；
- 被派工人员主动开工、暂停、恢复和报工；正常报工直接完成并复位周期；
- 两个月提醒只提醒，异常报工不复位周期；
- Django 不发送邮件，只提供被派工人员的邮件上下文并保存平台回写结果。

只允许使用演示数据。不要连接真实生产数据库，不要提交真实员工邮箱或企业凭据。

## 环境与安装

基线为 Python 3.12、Django 5.2、DRF 3.16、SQLite、Asia/Shanghai，默认端口 `18080`。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

本项目不自动读取 `.env`；按需把其中变量导出到进程环境。默认值已经可以安全运行本地演示。

## 数据库与启动

```bash
python manage.py migrate
python manage.py seed_probe_data
python manage.py verify_probe_data
python manage.py runserver 0.0.0.0:18080
```

Linux 可选启动方式：

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:18080 --workers 1 --threads 4
```

OpenAPI schema 位于 `/api/schema`，Swagger UI 位于 `/api/docs`。

重置全部探测业务数据并恢复标准场景：

```bash
python manage.py reset_probe_data
python manage.py verify_probe_data
```

## 业务规则

```text
cycle_count = current_count - cycle_baseline_count
development_tonnage < 1000T  → threshold = 50,000
development_tonnage >= 1000T → threshold = 30,000
cycle_count >= threshold      → MAINTENANCE_DUE
```

注塑模具在 `cycle_baseline_time + 2 个自然月` 生成 `TWO_MONTH_REMINDER`，但不能创建工单。达到两年无产量时返回 `IDLE_AUTO_REMINDER_DISABLED`，停止新的自动模次提醒。

所有写接口的 JSON body 必须包含全局唯一的 `client_request_id`：相同 ID 和相同内容重放原结果并返回 `replayed=true`；相同 ID 和不同内容返回 `CLIENT_REQUEST_CONFLICT`。

## API

统一前缀为 `/api/v1`，所有响应包含 `code`、`message`、`data` 和追踪用 `request_id`。

| 能力 | 接口 |
|---|---|
| 服务 | `GET /health`、`GET /meta` |
| 平台探测 | `POST /probe/runs`、`GET /probe/runs/{run_id}/context`、`POST /probe/runs/{run_id}/variable-test`、`POST /probe/scheduler-heartbeat`、`GET /probe/runs/{run_id}/report` |
| 模具 | `GET /molds`、`GET /molds/{mold_id}`、`GET /molds/{mold_id}/maintenance-status` |
| 预警 | `POST /alerts/scan`、`GET /alerts`、`GET /alerts/{alert_id}`、`POST /alerts/{alert_id}/create-work-order` |
| 派工 | `GET /work-orders`、`GET /work-orders/{id}`、`GET /work-orders/{id}/candidates`、`POST /work-orders/{id}/assign`、`POST /work-orders/{id}/auto-assign` |
| 知识与邮件 | `GET /work-orders/{id}/knowledge-context`、`POST /work-orders/{id}/knowledge-snapshot`、`GET /work-orders/{id}/email-context`、`POST /work-orders/{id}/notifications` |
| 主动报工 | `POST /work-orders/{id}/start`、`pause`、`resume`、`report-complete`、`report-abnormal`、`GET /work-orders/{id}/history` |

### 扫描与创建工单

```bash
curl -sS http://127.0.0.1:18080/api/v1/alerts/scan \
  -H 'Content-Type: application/json' \
  -d '{"client_request_id":"demo-scan-001"}'

curl -sS http://127.0.0.1:18080/api/v1/alerts/ALT_ID/create-work-order \
  -H 'Content-Type: application/json' \
  -d '{"client_request_id":"demo-create-001"}'

curl -sS http://127.0.0.1:18080/api/v1/work-orders/WO_ID/auto-assign \
  -H 'Content-Type: application/json' \
  -d '{"client_request_id":"demo-assign-001"}'
```

### 正常报工

回写知识快照后，提交快照中全部 `required=true` 的点检项：

```bash
curl -sS http://127.0.0.1:18080/api/v1/work-orders/WO_ID/knowledge-snapshot \
  -H 'Content-Type: application/json' \
  -d '{
    "catalog_version":"demo-kb-v1",
    "items":[
      {"knowledge_id":"KB-INJECTION-001","item":"检查模具表面及型腔","required":true},
      {"knowledge_id":"KB-INJECTION-002","item":"检查冷却水路","required":true}
    ],
    "client_request_id":"demo-snapshot-001"
  }'

curl -sS http://127.0.0.1:18080/api/v1/work-orders/WO_ID/report-complete \
  -H 'Content-Type: application/json' \
  -d '{
    "employee_id":"EMP-001",
    "started_at":"2026-08-13T14:00:00+08:00",
    "completed_at":"2026-08-13T16:30:00+08:00",
    "work_summary":"已完成清洁、润滑和水路检查。",
    "inspection_results":[
      {"knowledge_id":"KB-INJECTION-001","item":"检查模具表面及型腔","result":"PASS","note":"正常"},
      {"knowledge_id":"KB-INJECTION-002","item":"检查冷却水路","result":"PASS","note":"畅通"}
    ],
    "attachments":[],
    "client_request_id":"demo-complete-001"
  }'
```

正常报工成功后，工单直接进入 `COMPLETED`，创建履历并将当前模次作为新周期基准。

### 异常报工

```bash
curl -sS http://127.0.0.1:18080/api/v1/work-orders/WO_ID/report-abnormal \
  -H 'Content-Type: application/json' \
  -d '{
    "employee_id":"EMP-001",
    "abnormal_type":"COOLING_CHANNEL_BLOCKED",
    "description":"冷却水路堵塞，常规保养无法处理。",
    "inspection_results":[
      {"knowledge_id":"KB-INJECTION-002","item":"检查冷却水路","result":"FAIL","note":"发现堵塞"}
    ],
    "client_request_id":"demo-abnormal-001"
  }'
```

异常报工进入 `ABNORMAL_REPORTED`，保存失败项，但不关闭保养需求、不创建保养履历、不复位周期。

## 验证

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py migrate
python manage.py seed_probe_data
python manage.py verify_probe_data
python scripts/smoke_test.py
docker build .
```

`smoke_test.py` 默认启动临时本地服务器，使用真实 HTTP 连续完成三次正常闭环和一次异常闭环。设置 `PROBE_BASE_URL` 时只执行 health/meta 和平台探测端点，不重置或运行远程业务闭环，避免破坏已有数据。

平台节点的完整调用顺序、请求示例与能力状态定义见 [平台测试指南](docs/platform-test-guide.md)。

## 状态与边界

```text
READY_FOR_PLATFORM_TEST
NOT READY FOR PRODUCTION
DEMO DATA ONLY
```

平台本身的公网访问、知识库命中、动态邮件发送和真正定时触发仍必须在比赛平台上实测；Django 报告会对没有证据的能力保留 `NOT_TESTED`。
