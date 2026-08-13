# MoldGuard 平台能力探测服务器实施计划

- **计划状态**：`READY_FOR_IMPLEMENTATION`
- **计划版本**：V0.1
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **基础分支**：`main`
- **实施分支**：`agent/platform-capability-probe-v1`
- **系统性质**：比赛平台能力验证用开放测试服务器
- **权威范围**：仅约束 `agent/platform-capability-probe-v1` 分支及其后续测试实现

---

## 1. 计划目的

本轮不直接建设完整的企业级模具保养系统，而是先实现一个能够公开调用的最小 Django 测试服务器，用于验证比赛智能体平台到底能够完成哪些能力：

```text
外部 HTTP 调用
→ 动态变量传递
→ 嵌套 JSON 与数组处理
→ 模具保养规则计算
→ 预警与工单创建
→ 自动或指定人员派工
→ 知识库检索条件传递
→ 知识快照回写
→ 动态任务邮件
→ 被派工人员主动报工
→ 正常完成或异常记录
→ 保养履历与周期复位
→ 输出平台能力测试报告
```

本服务器的首要目标不是安全、权限或复杂业务治理，而是：

1. 尽快提供可调用的真实接口；
2. 让比赛平台按真实业务形态进行联调；
3. 明确平台原生支持、需要适配和无法实现的能力；
4. 用测试结论决定正式参赛服务器的最终架构。

---

## 2. 与现有完整方案的关系

仓库现有 V3.1、V3.2、V3.3 文档描述的是完整业务服务器，包括鉴权、主管确认、计划、送模、验收、修模和生产级治理。

本计划是一个独立的 **平台探测分支计划**，不修改 `main` 的完整方案，也不宣称完整方案已经废止。

在本分支中，以下内容明确不适用：

```text
API Key
登录和身份认证
角色权限
主管角色
主管确认
主管派工
主管验收
保养计划层
计划关闭次数
排产和送模
复杂修模审批
生产级审计
```

本分支采用更短的测试闭环：

```text
预警
→ 工单
→ 派工
→ 知识随单与邮件
→ 被派工人员主动报工
→ 直接完成或记录异常
```

平台探测完成后，再决定哪些代码、接口和状态模型迁移到正式实现分支。

---

## 3. 已冻结的实施原则

### 3.1 完全开放调用

服务器不实现任何鉴权机制：

```text
不登录
不使用用户名密码
不使用 Token 或 JWT
不使用 X-API-Key
不校验调用者身份
不校验角色权限
不设置主管账号
```

Django REST Framework 全局配置：

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}
```

所有接口都可以直接通过 HTTP 请求调用。

本分支只允许使用模拟数据，不保存真实生产敏感数据和真实员工隐私数据。

### 3.2 不引入主管角色

系统不存在以下流程：

```text
主管确认是否保养
主管选择被派工人员
主管审批派工
主管验收报工
主管退回报工
主管转修模
```

系统只保存被派工人员，不保存审批人、验收人和主管角色。

### 3.3 被派工人员主动报工

工单派发后，被派工人员可以：

```text
主动开工
主动暂停
主动恢复
主动提交正常报工
主动提交异常报工
```

正常报工通过服务器校验后，工单直接完成，不进入待验收状态。

### 3.4 不建立保养计划层

本分支不建立 `MaintenancePlan`。

原完整流程：

```text
预警 → 计划 → 确认 → 送模 → 工单
```

本分支简化为：

```text
预警 → 工单
```

### 3.5 派工方式

本分支同时支持：

```text
自动派工：服务器按确定性规则选择候选第一名
指定派工：比赛平台直接传 employee_id
```

不需要任何人审批派工。

为了验证平台数组处理能力，仍保留候选人员查询接口。

### 3.6 邮件只发送给被派工人员

任务邮件只返回被派工人员邮箱：

```text
to = assigned_employee.email
```

不返回主管、计划部或其他抄送地址。

Django 不负责真正发送邮件；比赛平台负责生成和发送，随后将结果回写 Django。

---

## 4. 本轮验证目标

| 编号 | 能力 | 验证内容 |
|---|---|---|
| P01 | 外部 HTTP | GET、POST、公网地址、状态码、超时 |
| P02 | 动态变量 | `mold_id`、`alert_id`、`work_order_id`、`employee_id` 的连续传递 |
| P03 | 嵌套 JSON | 读取多层对象并作为下一节点输入 |
| P04 | 数组 | 候选人员、知识条目、点检结果的遍历和回传 |
| P05 | 状态流转 | 按接口返回结果继续创建工单、派工和报工 |
| P06 | 知识库 | 根据模具类型、规则 ID 和知识画像检索知识 |
| P07 | 知识回写 | 将实际使用的知识条目数组回写 Django |
| P08 | 动态邮件 | 使用接口返回的收件人和正文变量发送邮件 |
| P09 | 邮件回写 | 回写发送状态、消息 ID、失败原因和时间 |
| P10 | 主动报工 | 被派工人员提交点检和工作总结 |
| P11 | 异常分支 | 点检失败或无法完成时提交异常报工 |
| P12 | 定时触发 | 平台定时调用扫描接口，或确认需要外部定时器 |
| P13 | 重复调用 | 平台重试时不重复生成工单、不重复复位周期 |
| P14 | 报告 | 形成原生支持、适配支持、外部依赖和阻塞矩阵 |

---

## 5. 不在本轮实施的范围

```text
真实 MES、ERP 或排产系统
生产级 PostgreSQL 集群
Redis 和 Celery
向量数据库
Django 自建知识库
大模型调用
SMTP 服务器
企业微信、钉钉和短信
独立 Web 前端
真实组织架构
登录和权限
正式规则审批
主管、计划部、分厂角色
保养计划和送模
主管验收
完整修模执行流程
备件、成本和库存
复杂负荷算法
生产级备份、容灾和安全加固
```

---

## 6. 当前业务规则基线

### 6.1 吨位模次触发

钣金和注塑模具统一按开发吨位触发周期保养，不区分一级、二级、三级保养。

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 50,000 模次 |
| `>=1000T` | 30,000 模次 |

计算公式：

```text
cycle_count = current_count - cycle_baseline_count
```

触发条件：

```text
cycle_count >= threshold
```

边界要求：

```text
999T  → 50,000
1000T → 30,000
```

开发吨位为空时不得猜测，返回：

```text
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
```

当前模次小于周期基准时返回：

```text
INVALID_CYCLE_COUNT
```

历史一保、二保、三保、精密/普通/小型模具阈值和外部 A/B/C 资料只用于知识检索和作业参考，不参与本分支自动计算。

### 6.2 注塑模具每两个月提醒

只适用于注塑模具：

```text
next_reminder_at = cycle_baseline_time + 2 calendar months
```

达到时间后：

```text
生成 TWO_MONTH_REMINDER
不创建工单
不派工
不复位周期
```

响应必须包含：

```text
仅表示已满2个月，不代表模次保养条件已达到。
```

### 6.3 两年无产量

当模具最后生产时间超过两年时：

```text
停止该模具自动保养扫描
不生成新的模次保养预警
返回 IDLE_AUTO_REMINDER_DISABLED
```

### 6.4 正常报工后的周期复位

本分支主路径只实现“保养完成”复位：

```text
cycle_baseline_count = mold.current_count
cycle_baseline_time = work_report.completed_at
cycle_version = cycle_version + 1
last_reset_type = MAINTENANCE_COMPLETED
last_reset_event_id = work_report.report_id
```

重新计算：

```text
next_trigger_count = cycle_baseline_count + threshold
next_two_month_reminder_at = cycle_baseline_time + 2 calendar months
```

异常报工不得复位周期。

修模完成、换镶件完成和历史记录导入仅预留枚举，不进入本轮主流程。

---

## 7. 最小业务闭环

### 7.1 正常路径

```text
1. 平台调用 POST /api/v1/alerts/scan
2. Django 返回模次保养预警
3. 平台调用预警创建工单接口
4. Django 创建 PENDING_ASSIGNMENT 工单
5. 平台查询候选人员数组
6. 平台调用自动派工或指定派工
7. Django 返回被派工人员和邮箱
8. 平台获取 knowledge-context
9. 平台检索保养步骤、点检标准和安全知识
10. 平台回写 knowledge-snapshot
11. 平台获取 email-context 并发送任务邮件
12. 平台回写邮件发送结果
13. 被派工人员主动开工，或直接一次性报工
14. 被派工人员提交工作总结和点检结果
15. Django 校验全部必检项
16. Django 将工单直接设为 COMPLETED
17. Django 创建履历并复位周期
18. 平台查询完成结果并生成通报
```

### 7.2 异常路径

```text
1. 工单已派工
2. 被派工人员执行点检
3. 发现常规保养无法解决的问题
4. 调用 report-abnormal
5. Django 保存失败点检和异常说明
6. 工单进入 ABNORMAL_REPORTED
7. 本次不复位周期
8. 平台生成异常通知或后续人工处理说明
```

---

## 8. 技术基线

| 项目 | 选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS |
| API | Django REST Framework 3.16 系列 |
| 数据库 | SQLite |
| 测试 | pytest、pytest-django |
| 代码质量 | Ruff |
| API 文档 | drf-spectacular |
| 时区 | Asia/Shanghai |
| 默认端口 | 18080 |
| 本地运行 | Django runserver |
| Linux 运行 | Gunicorn，可选 |
| Docker | 提供最小 Dockerfile，可选使用 |
| 鉴权 | 无 |
| 权限 | AllowAny |
| 请求格式 | JSON |
| 返回格式 | 统一 JSON |

不部署：

```text
PostgreSQL
Redis
Celery
Nginx
SMTP
向量数据库
```

若比赛平台只能访问 HTTPS，再单独通过现有反向代理、Cloudflare Tunnel 或其他临时公网入口暴露，不把 HTTPS 配置作为 Django 第一阶段阻塞项。

---

## 9. 工程结构

```text
moldguard-django-server/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── __init__.py
│   └── platform_probe/
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── models.py
│       ├── serializers.py
│       ├── urls.py
│       ├── views.py
│       ├── responses.py
│       ├── exceptions.py
│       ├── services/
│       │   ├── trigger_service.py
│       │   ├── alert_service.py
│       │   ├── assignment_service.py
│       │   ├── reporting_service.py
│       │   └── probe_report_service.py
│       └── management/
│           └── commands/
│               ├── seed_probe_data.py
│               ├── reset_probe_data.py
│               └── verify_probe_data.py
├── data/
│   └── probe_data.json
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── api/
│   └── integration/
├── scripts/
│   └── smoke_test.py
├── docs/
│   ├── contracts/
│   ├── reports/
│   └── platform-test-guide.md
├── Dockerfile
└── README.md
```

第一版只建立一个 Django App：

```text
platform_probe
```

不提前拆分为多个正式业务 App。

---

## 10. 数据模型

### 10.1 Mold

```text
mold_id
mold_name
mold_type
status
development_tonnage
current_count
cycle_baseline_count
cycle_baseline_time
cycle_version
last_production_at
last_reset_type
last_reset_event_id
created_at
updated_at
```

枚举：

```text
mold_type:
  INJECTION
  SHEET_METAL

status:
  IN_PRODUCTION
  IN_STORAGE
  UNDER_REPAIR
  DISABLED
```

### 10.2 Employee

```text
employee_id
employee_name
email
team
skill_tags
available
current_load
created_at
updated_at
```

不设置角色字段。

### 10.3 MaintenanceAlert

```text
alert_id
mold
alert_type
cycle_version
cycle_count_snapshot
threshold_snapshot
trigger_basis_json
status
created_at
updated_at
```

枚举：

```text
alert_type:
  MAINTENANCE_DUE
  TWO_MONTH_REMINDER
  IDLE_AUTO_REMINDER_DISABLED

status:
  OPEN
  WORK_ORDER_CREATED
  CLOSED
```

唯一约束：

```text
mold + alert_type + cycle_version
```

### 10.4 WorkOrder

```text
work_order_id
alert
mold
status
assigned_employee
assigned_at
started_at
completed_at
required_finish_at
knowledge_profile_code
created_at
updated_at
```

状态：

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
COMPLETED
ABNORMAL_REPORTED
CANCELLED
```

### 10.5 PauseSegment

```text
pause_id
work_order
paused_at
resumed_at
reason
created_at
```

### 10.6 KnowledgeSnapshot

```text
snapshot_id
work_order
catalog_version
items_json
created_at
```

第一版使用 JSONField 保存平台回写的知识条目数组。

### 10.7 NotificationReceipt

```text
notification_id
work_order
recipient
status
message_id
error_message
sent_at
created_at
```

### 10.8 WorkReport

```text
report_id
work_order
employee
report_type
started_at
completed_at
paused_seconds
actual_minutes
work_summary
inspection_results_json
attachments_json
cycle_reset
client_request_id
created_at
```

枚举：

```text
report_type:
  COMPLETE
  ABNORMAL
```

### 10.9 AbnormalReport

```text
abnormal_report_id
work_order
employee
abnormal_type
description
inspection_results_json
client_request_id
created_at
```

### 10.10 MaintenanceHistory

```text
history_id
mold
work_order
event_type
count_snapshot
occurred_at
cycle_version_before
cycle_version_after
created_at
```

### 10.11 ClientRequestRecord

用于防止平台重试产生重复写入，不属于鉴权。

```text
client_request_id
action
object_id
request_hash
response_status
response_json
created_at
```

### 10.12 ProbeRun 与 ProbeStep

```text
ProbeRun:
  run_id
  platform_name
  tester
  mode
  status
  started_at
  completed_at

ProbeStep:
  run
  capability_code
  status
  request_snapshot_json
  response_snapshot_json
  evidence
  created_at
```

`mode`：

```text
STRICT
COMPATIBILITY
```

严格模式用于验证平台原生能力；兼容模式只在严格模式失败后验证 Django 是否能够通过接口适配补偿。

---

## 11. 工单状态机

### 11.1 完整执行模式

```text
PENDING_ASSIGNMENT
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
```

暂停路径：

```text
IN_PROGRESS
→ PAUSED
→ IN_PROGRESS
→ COMPLETED
```

异常路径：

```text
ASSIGNED / IN_PROGRESS / PAUSED
→ ABNORMAL_REPORTED
```

### 11.2 一次性报工模式

平台不方便提供单独开工节点时，允许：

```text
ASSIGNED
→ report-complete
→ COMPLETED
```

请求必须显式提交：

```text
started_at
completed_at
```

服务器不得自行猜测开工时间。

### 11.3 正常完成条件

```text
工单已派工
employee_id 与 assigned_employee 一致
工单状态允许报工
started_at 和 completed_at 合法
所有必检项已提交
不存在 FAIL 项
NOT_APPLICABLE 项填写原因
client_request_id 未与其他请求冲突
```

完成事务：

```text
创建 WorkReport
计算暂停时长和实际分钟数
工单设为 COMPLETED
创建 MaintenanceHistory
复位 Mold 周期
关闭关联 MAINTENANCE_DUE 预警
保存原响应供重复请求复用
```

### 11.4 异常报工条件

```text
工单已派工
employee_id 与 assigned_employee 一致
填写 abnormal_type 和 description
FAIL 点检项填写 note
```

异常事务：

```text
创建 AbnormalReport
创建 ABNORMAL 类型 WorkReport
工单设为 ABNORMAL_REPORTED
不复位周期
不关闭保养需求
```

---

## 12. API 契约

### 12.1 通用要求

请求：

```http
Content-Type: application/json
Accept: application/json
```

不要求任何认证请求头。

成功响应：

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {},
  "request_id": "req-..."
}
```

失败响应：

```json
{
  "code": "WORK_ORDER_NOT_FOUND",
  "message": "工单不存在",
  "data": null,
  "errors": [],
  "request_id": "req-..."
}
```

`request_id` 由 Django 自动生成，用于定位平台调用，不作为鉴权信息。

### 12.2 服务和探测接口

```http
GET  /api/v1/health
GET  /api/v1/meta
POST /api/v1/probe/runs
GET  /api/v1/probe/runs/{run_id}/context
POST /api/v1/probe/runs/{run_id}/variable-test
POST /api/v1/probe/scheduler-heartbeat
GET  /api/v1/probe/runs/{run_id}/report
```

### 12.3 模具与预警

```http
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
POST /api/v1/alerts/scan
GET  /api/v1/alerts
GET  /api/v1/alerts/{alert_id}
POST /api/v1/alerts/{alert_id}/create-work-order
```

`TWO_MONTH_REMINDER` 调用创建工单时返回：

```text
REMINDER_NOT_WORK_ORDER_ELIGIBLE
```

### 12.4 工单与派工

```http
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{work_order_id}
GET  /api/v1/work-orders/{work_order_id}/candidates
POST /api/v1/work-orders/{work_order_id}/assign
POST /api/v1/work-orders/{work_order_id}/auto-assign
GET  /api/v1/work-orders/{work_order_id}/history
```

指定派工请求：

```json
{
  "employee_id": "EMP-001",
  "client_request_id": "assign-WO-TEST-001-001"
}
```

自动派工规则：

```text
available = true
→ skill_tags 与 mold_type 匹配
→ current_load 从低到高
→ employee_id 从小到大
→ 选择第一人
```

### 12.5 知识和邮件

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge-snapshot
GET  /api/v1/work-orders/{work_order_id}/email-context
POST /api/v1/work-orders/{work_order_id}/notifications
```

`knowledge-context` 至少返回：

```json
{
  "work_order_id": "WO-TEST-001",
  "mold_type": "INJECTION",
  "rule_id": "MAINT_TRIGGER_TONNAGE_V1",
  "knowledge_profile_code": "INJECTION_PERIODIC_MAINTENANCE",
  "query_keywords": [
    "注塑模具",
    "周期保养",
    "点检标准",
    "安全要求"
  ],
  "required_types": [
    "MAINTENANCE_STANDARD",
    "INSPECTION_STANDARD",
    "SAFETY"
  ]
}
```

`email-context` 只返回被派工人员：

```json
{
  "to": ["maintainer-a@example.com"],
  "subject": "【MoldGuard】WO-TEST-001 模具保养任务",
  "template_variables": {
    "employee_name": "测试保养员甲",
    "mold_name": "前壳体注塑模",
    "work_order_id": "WO-TEST-001",
    "development_tonnage": 850,
    "trigger_threshold": 50000,
    "current_cycle_count": 50200
  }
}
```

不返回 `cc` 和主管字段。

### 12.6 主动报工

```http
POST /api/v1/work-orders/{work_order_id}/start
POST /api/v1/work-orders/{work_order_id}/pause
POST /api/v1/work-orders/{work_order_id}/resume
POST /api/v1/work-orders/{work_order_id}/report-complete
POST /api/v1/work-orders/{work_order_id}/report-abnormal
```

正常报工示例：

```json
{
  "employee_id": "EMP-001",
  "started_at": "2026-08-13T14:00:00+08:00",
  "completed_at": "2026-08-13T16:30:00+08:00",
  "work_summary": "已完成模具清洁、润滑和水路检查。",
  "inspection_results": [
    {
      "knowledge_id": "KB-INJECTION-001",
      "item": "检查模具表面及型腔",
      "result": "PASS",
      "note": "表面及型腔正常"
    },
    {
      "knowledge_id": "KB-INJECTION-002",
      "item": "检查冷却水路",
      "result": "PASS",
      "note": "水路畅通，无堵塞"
    }
  ],
  "attachments": [],
  "client_request_id": "report-WO-TEST-001-001"
}
```

成功响应：

```json
{
  "code": "SUCCESS",
  "message": "报工完成",
  "data": {
    "work_order_id": "WO-TEST-001",
    "status": "COMPLETED",
    "report_id": "REPORT-TEST-001",
    "actual_minutes": 150,
    "cycle_reset": {
      "performed": true,
      "baseline_count": 150200,
      "cycle_version": 2,
      "next_threshold": 50000,
      "next_trigger_count": 200200
    }
  },
  "request_id": "req-..."
}
```

异常报工示例：

```json
{
  "employee_id": "EMP-001",
  "abnormal_type": "COOLING_CHANNEL_BLOCKED",
  "description": "冷却水路堵塞，常规保养无法处理。",
  "inspection_results": [
    {
      "knowledge_id": "KB-INJECTION-002",
      "item": "检查冷却水路",
      "result": "FAIL",
      "note": "发现堵塞"
    }
  ],
  "client_request_id": "abnormal-WO-TEST-001-001"
}
```

---

## 13. 重复调用与数据一致性

本服务器不做身份鉴权，但必须避免平台重试造成重复数据。

所有写接口接受：

```text
client_request_id
```

处理规则：

```text
相同 client_request_id + 相同请求内容
→ 返回第一次结果
→ data.replayed = true

相同 client_request_id + 不同请求内容
→ 返回 CLIENT_REQUEST_CONFLICT
```

数据库约束：

```text
同一 MAINTENANCE_DUE 预警只能创建一张工单
同一工单只能有一条成功 COMPLETE 报工
已完成工单不能再次复位周期
同一模具、预警类型和 cycle_version 不重复生成开放预警
```

---

## 14. 错误码

```text
MOLD_NOT_FOUND
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
INVALID_CYCLE_COUNT
ALERT_NOT_FOUND
ALERT_ALREADY_HAS_WORK_ORDER
REMINDER_NOT_WORK_ORDER_ELIGIBLE
WORK_ORDER_NOT_FOUND
WORK_ORDER_ALREADY_COMPLETED
INVALID_WORK_ORDER_STATE
EMPLOYEE_NOT_FOUND
EMPLOYEE_NOT_AVAILABLE
EMPLOYEE_NOT_ASSIGNED
NO_ASSIGNMENT_CANDIDATE
KNOWLEDGE_SNAPSHOT_REQUIRED
INSPECTION_ITEMS_INCOMPLETE
INSPECTION_FAIL_REQUIRES_ABNORMAL_REPORT
NOT_APPLICABLE_REASON_REQUIRED
ABNORMAL_DESCRIPTION_REQUIRED
INVALID_TIME_RANGE
CLIENT_REQUEST_CONFLICT
PROBE_RUN_NOT_FOUND
```

---

## 15. 演示数据

### 15.1 模具

| 模具编号 | 类型 | 吨位 | 场景 |
|---|---|---:|---|
| `MOLD-TEST-001` | 注塑 | 850T | 达到 50,000 模次 |
| `MOLD-TEST-002` | 钣金 | 1200T | 达到 30,000 模次 |
| `MOLD-TEST-003` | 注塑 | 850T | 满两个月但模次未到 |
| `MOLD-TEST-004` | 注塑 | 850T | 两年无产量 |
| `MOLD-TEST-005` | 钣金 | 900T | 尚未达到阈值 |
| `MOLD-TEST-006` | 注塑 | 空 | 缺少开发吨位 |
| `MOLD-TEST-007` | 注塑 | 1000T | 验证边界使用 30,000 |

### 15.2 人员

| 人员编号 | 技能 | 可用状态 |
|---|---|---|
| `EMP-001` | 注塑模具保养 | 可用 |
| `EMP-002` | 钣金模具保养 | 可用 |
| `EMP-003` | 注塑、钣金 | 不可用 |
| `EMP-004` | 注塑、钣金 | 可用但负荷较高 |

邮箱通过环境变量配置：

```text
PROBE_EMPLOYEE_1_EMAIL
PROBE_EMPLOYEE_2_EMAIL
PROBE_EMPLOYEE_4_EMAIL
```

未配置时使用 `example.com` 测试地址。

### 15.3 知识条目标识

第一版只准备少量模拟 ID，真实知识正文仍放在比赛平台知识库：

```text
KB-INJECTION-001
KB-INJECTION-002
KB-SHEET-001
KB-SHEET-002
KB-SAFETY-001
```

---

## 16. 平台探测模式

### 16.1 STRICT

严格模式验证平台原生能力：

```text
使用嵌套 JSON
使用数组
使用动态路径变量
按原接口提交知识快照和点检数组
不提供扁平化替代字段
```

### 16.2 COMPATIBILITY

仅在严格模式失败后启用，用于验证服务器适配是否可补偿：

```text
允许扁平化上下文
允许逐条提交点检结果
允许逐条回写知识条目
允许使用单候选接口
```

兼容模式成功时，能力状态标记为：

```text
PASS_WITH_ADAPTER
```

兼容接口属于后续适配项，不能替代严格模式测试。

---

## 17. 分阶段实施与 Stop Gate

### Phase 0：冻结分支合同

交付：

```text
本实施计划
API 路径清单
业务规则基线
状态机
演示数据定义
```

Stop Gate：

```text
计划中不存在鉴权、主管、保养计划和验收依赖
主路径明确为被派工人员主动报工
```

### Phase 1：开放 Django 骨架

实现：

```text
Django 工程
platform_probe App
SQLite
AllowAny
统一响应
request_id
health
meta
OpenAPI 基础配置
```

Stop Gate：

```text
python manage.py check 通过
GET /api/v1/health 成功
POST 接口无需 Token 即可调用
```

### Phase 2：模具、规则和预警

实现：

```text
Mold
MaintenanceAlert
吨位阈值计算
注塑两个月提醒
两年无产量判断
seed_probe_data
alerts/scan
maintenance-status
```

Stop Gate：

```text
999T 按 50,000 触发
1000T 按 30,000 触发
两个月提醒不创建工单
两年无产量停止自动提醒
重复扫描不生成重复预警
```

### Phase 3：工单与派工

实现：

```text
Employee
WorkOrder
预警创建工单
候选人员
自动派工
指定人员派工
工单详情与历史
```

Stop Gate：

```text
模次预警可创建工单
两个月提醒不可创建工单
同一预警不可重复创建工单
自动派工排序稳定可复现
```

### Phase 4：知识与邮件

实现：

```text
knowledge-context
knowledge-snapshot
email-context
notifications
动态邮箱
知识条目数组回写
```

Stop Gate：

```text
平台可获取知识检索条件
平台可回写知识数组
邮件上下文只返回被派工人员
发送状态和 message_id 可回写
```

### Phase 5：主动报工

实现：

```text
start
pause
resume
report-complete
report-abnormal
PauseSegment
WorkReport
AbnormalReport
点检校验
工时计算
```

Stop Gate：

```text
被派工人员可主动报工
错误 employee_id 被拒绝
缺少必检项不能完成
FAIL 项不能走正常完成
异常报工不复位周期
```

### Phase 6：履历、周期复位和重复保护

实现：

```text
MaintenanceHistory
ClientRequestRecord
完成事务
周期复位
下一触发模次
重复请求返回原结果
```

Stop Gate：

```text
正常报工只复位一次
current_count 成为新 baseline
cycle_version 正确加一
重复报工不重复创建履历
```

### Phase 7：平台能力报告

实现：

```text
ProbeRun
ProbeStep
variable-test
scheduler-heartbeat
STRICT/COMPATIBILITY 结果
能力矩阵报告
```

Stop Gate：

```text
HTTP、动态变量、嵌套 JSON、数组、知识、邮件、报工和定时均有明确结论
```

### Phase 8：部署与联调手册

实现：

```text
.env.example
requirements.txt
Dockerfile
Gunicorn 启动命令
smoke_test.py
platform-test-guide.md
```

最终联调门禁：

连续完成三次正常闭环：

```text
扫描
→ 创建工单
→ 派工
→ 知识检索
→ 邮件
→ 主动报工
→ 周期复位
```

并完成一次异常闭环：

```text
派工
→ FAIL 点检
→ 异常报工
→ 不复位周期
```

---

## 18. 自动化测试清单

### 18.1 规则测试

```text
999T 使用 50,000 阈值
1000T 使用 30,000 阈值
阈值前一模次不触发
刚好达到阈值时触发
超过阈值时触发
缺少开发吨位返回错误
current_count 小于 baseline 返回错误
```

### 18.2 时间提醒测试

```text
注塑满两个月生成提醒
注塑未满两个月不生成提醒
钣金不生成两个月提醒
两个月提醒不能创建工单
两年无产量停止自动提醒
```

### 18.3 预警和工单测试

```text
重复扫描不重复创建开放预警
同一预警不能重复创建工单
关闭或复位后新 cycle_version 可生成新预警
```

### 18.4 派工测试

```text
候选数组格式正确
不可用人员不进入候选
技能不匹配人员不进入候选
自动派工排序稳定
指定不存在人员返回错误
已派工工单不能重复改派，除非后续明确增加接口
```

### 18.5 知识和邮件测试

```text
知识上下文字段完整
知识条目数组可保存和读取
邮件地址来自被派工人员
未派工不能生成邮件上下文
邮件成功和失败均可记录
```

### 18.6 报工测试

```text
非被派工人员不能报工
完整点检可正常完成
缺少必检项拒绝完成
FAIL 拒绝正常完成
NOT_APPLICABLE 缺少原因拒绝完成
异常报工必须填写说明
异常报工不复位周期
正常报工复位周期
暂停时长从实际工时中扣除
一次性报工要求显式 started_at
```

### 18.7 重复请求测试

```text
相同 client_request_id 和相同请求返回原结果
相同 client_request_id 和不同请求返回冲突
重复创建工单不产生第二张工单
重复正常报工不产生第二次周期复位
```

### 18.8 接口和报告测试

```text
统一成功响应
统一错误响应
request_id 自动生成
ProbeRun 可记录步骤
STRICT 与 COMPATIBILITY 结果可区分
最终报告状态正确
```

质量命令：

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py verify_probe_data
python scripts/smoke_test.py
```

---

## 19. 平台能力结果定义

每项能力使用以下状态之一：

```text
PASS_NATIVE
PASS_WITH_ADAPTER
MANUAL_VERIFIED
EXTERNAL_REQUIRED
BLOCKED
NOT_TESTED
```

含义：

| 状态 | 含义 |
|---|---|
| `PASS_NATIVE` | 平台原生完成，无需服务器额外适配 |
| `PASS_WITH_ADAPTER` | 平台原生不足，但 Django 兼容接口可补偿 |
| `MANUAL_VERIFIED` | 需要人工观察或截图确认 |
| `EXTERNAL_REQUIRED` | 需要外部定时器、邮件服务或网关 |
| `BLOCKED` | 当前平台无法完成且没有可靠替代方案 |
| `NOT_TESTED` | 尚未执行测试 |

报告至少输出：

| 能力 | 结果 | 证据 | 对正式方案的影响 |
|---|---|---|---|
| GET | `PASS_NATIVE` | 请求记录 | 无 |
| POST | `PASS_NATIVE` | 请求记录 | 无 |
| 嵌套 JSON | 待测 | 变量回传 | 可能需要扁平接口 |
| 数组遍历 | 待测 | 候选选择与点检数组 | 可能需要逐条接口 |
| 知识检索 | 待测 | 命中条目与来源 | 可能需要明确关键词 |
| 动态邮件 | 待测 | 收件人与消息 ID | 可能需要外部邮件服务 |
| 定时调用 | 待测 | heartbeat | 可能需要 Linux cron |
| 主动报工 | 待测 | WorkReport | 决定正式闭环形态 |

---

## 20. 建议提交顺序

```text
1. docs: add platform capability probe implementation plan
2. chore: scaffold open django probe server
3. feat: add probe molds and maintenance trigger rules
4. feat: add alerts and duplicate protection
5. feat: add work orders and deterministic assignment
6. feat: add knowledge context and snapshot callbacks
7. feat: add dynamic email context and notification receipts
8. feat: add assignee start pause resume and completion reports
9. feat: add abnormal reports and cycle reset history
10. feat: add platform capability report
11. test: cover rules api workflow and reporting
12. docs: add deployment and platform test runbook
```

每个 Phase 独立提交，达到 Stop Gate 后再进入下一阶段。

---

## 21. 完成标准

分支只有同时满足以下条件，才标记：

```text
READY_FOR_PLATFORM_TEST
```

验收条件：

- 全部接口无需认证即可访问；
- 系统不存在主管角色和审批节点；
- 不建立保养计划层；
- 吨位规则及 1000T 边界正确；
- 注塑两个月提醒不会创建工单；
- 两年无产量停止自动提醒；
- 模次预警可以创建工单；
- 工单可以自动或指定人员派工；
- 平台可以查询候选人员数组；
- 平台可以获取知识检索条件；
- 平台可以回写知识快照；
- 邮件上下文只包含被派工人员；
- 被派工人员可以主动开工或一次性报工；
- 正常报工直接完成并复位周期；
- 异常报工不复位周期；
- 重复调用不会生成重复工单或重复复位；
- 自动化测试全部通过；
- 连续完成三次正常闭环和一次异常闭环；
- 生成完整平台能力矩阵。

---

## 22. 分支与合并原则

实施分支：

```text
agent/platform-capability-probe-v1
```

平台测试完成前：

```text
不直接修改 main 的完整业务基线
不引入主管审批流程
不引入 API Key 和角色权限
不提前建设正式生产服务器
```

测试结束后分类处理：

```text
可复用：Django 骨架、规则计算、预警、工单、主动报工、测试和接口适配
仅测试保留：ProbeRun、ProbeStep、延迟/变量探测和能力报告接口
按结果决定：定时、邮件、数组兼容和正式数据库架构
```

是否合并到 `main`，必须以平台能力测试报告和负责人最终决定为准。

---

## 23. 最终结论

本分支要实现的不是完整企业模具管理系统，而是一个足够真实、足够简单、可快速联调的比赛平台能力探测服务器。

最终核心闭环冻结为：

```text
吨位规则扫描
→ 生成保养预警
→ 创建工单
→ 自动或指定人员派工
→ 平台检索知识并发送任务邮件
→ 被派工人员主动报工
→ 正常完成并复位周期
／
→ 异常报工且不复位周期
```

所有后续代码实现必须以本计划为 `agent/platform-capability-probe-v1` 分支的唯一实施基线。