# MoldGuard Django 测试服务器参赛实施计划

- **计划状态**：`FINAL_FROZEN_FOR_TEST_SERVER`
- **系统状态**：`NOT_IMPLEMENTED`
- **版本**：V4.0
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **建议实施分支**：`agent/django-test-server-v1`
- **系统定位**：比赛智能体平台使用的外部模拟业务服务器
- **数据性质**：`DEMO ONLY`
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **权威性**：本文件替代 V3.1、V3.2、V3.3 中与测试服务器范围冲突的内容，作为后续编码、测试和联调的唯一实施基线

---

## 1. 最终目标

Django 只承担比赛演示所需的模拟业务数据和状态，不按照企业生产系统建设。

系统保留原参赛材料中的核心链路：

```text
模具状态查询
→ 自动保养提醒
→ 创建保养工单
→ 候选人员查询与派工
→ 点检知识随邮件下发
→ 开工、暂停、恢复、报完工
→ 点检与验收
→ 合格归档 / 不合格转修模
→ 周期复位
→ 工时与完成率统计
```

智能体平台负责对话、工作流、知识库、LLM 和邮件；Django 负责可查询、可修改、可追溯的模拟业务状态。

---

## 2. 本版简化决策

### 2.1 不实现主管角色

Django 不建立：

```text
主管角色
管理员业务角色
计划员角色
分厂操作角色
保养人员权限角色
角色权限矩阵
```

业务流程中原本的“主管确认”统一改为：

```text
平台操作人员在流程节点中人工选择
→ 平台调用 Django 接口
→ Django 校验业务数据和状态
→ Django 保存结果
```

Django 不验证操作者是否为主管。

### 2.2 不实现安全鉴权

公共 API 不使用：

```text
X-API-Key
Authorization
Token / JWT
登录态
OAuth
用户权限校验
```

接口允许比赛平台直接访问。

写请求可选携带：

```json
{
  "operator_id": "TEST-OPERATOR-01",
  "operator_name": "比赛演示操作员"
}
```

该字段只用于日志展示，不作为安全凭证。未提供时默认：

```text
operator_id = TEST_PLATFORM
operator_name = 智能体平台
```

### 2.3 保留稳定性保护

以下能力不是安全鉴权，继续保留：

```text
数据库事务
状态机校验
唯一约束
重复工单检查
Idempotency-Key
Request-ID
统一错误码
周期复位审计
```

它们用于避免平台重试造成重复工单、重复派工和重复复位。

### 2.4 数据和部署简化

参赛测试版使用：

```text
Django + Django REST Framework
SQLite
单个 Django 进程
端口 18080
HTTP 直接访问
```

不要求：

```text
PostgreSQL
Redis
Celery
Nginx
HTTPS证书
独立前端
复杂账号系统
```

若比赛平台只允许 HTTPS，可在 Django 外部增加反向代理或临时隧道，但不是项目代码必需部分。

---

## 3. 智能体平台与 Django 分工

### 3.1 智能体平台负责

- 用户自然语言交互；
- Workflow / Agent 编排；
- 每日巡检或人工触发；
- 点检、操作、安全、验收和故障知识库；
- RAG 检索和来源引用；
- LLM 生成预警、任务、催办和分析说明；
- 展示候选人员并让操作人员选择；
- 生成和发送邮件；
- 将实际使用的知识和邮件结果回写 Django。

### 3.2 Django 负责

- 模具台账、开发吨位、当前模次和位置；
- 当前正式自动保养触发规则；
- 保养周期和周期复位；
- 模次提醒和注塑模具每2个月提醒；
- 保养预警；
- 工单、派工、状态机和时间线；
- 人员、技能、负荷和邮箱；
- 点检结果、报完工、验收和转修模记录；
- 知识快照和邮件结果记录；
- 履历、工时、完成率和超时统计；
- 演示数据初始化和重置。

### 3.3 Django 不负责

- 知识库向量检索；
- 调用大模型；
- 生成自然语言报告；
- SMTP 和邮件发送；
- 真实 MES、ERP、排产或身份系统；
- 生产级安全与权限治理。

---

## 4. 已确认业务规则

## 4.1 自动保养触发规则

状态：`INTERNAL_CONFIRMED`

钣金和注塑模具当前不区分一级、二级、三级保养，统一按照开发吨位触发：

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 每累计生产 50,000 模次 |
| `>=1000T` | 每累计生产 30,000 模次 |

计算：

```text
cycle_count = current_count - cycle_baseline_count
is_due = cycle_count >= count_threshold
remaining_count = max(count_threshold - cycle_count, 0)
overdue_count = max(cycle_count - count_threshold, 0)
```

开发吨位为空时返回：

```text
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
```

以下资料只作为知识参考，不参与自动触发：

```text
精密/普通/小型模具的3万、5万、10万模次
一保、二保、三保相关模次
零件级历史周期
外部A/B/C保养体系
```

## 4.2 每2个月提醒

状态：`INTERNAL_CONFIRMED`

当前适用于注塑模具：

```text
next_time_reminder_at = cycle_baseline_time + 2 calendar months
```

该提醒只能：

```text
创建提醒记录
→ 平台发送提醒
→ 记录提醒结果
```

不能：

```text
自动创建工单
自动派工
覆盖吨位模次规则
```

## 4.3 周期复位

状态：`INTERNAL_CONFIRMED`

以下事件复位周期：

```text
保养完成
修模完成
换镶件完成
有效历史记录导入
```

复位更新：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type
last_reset_event_id
```

历史记录使用实际发生模次和时间，不使用上传时间；早于当前基线的记录默认只归档，不自动倒退周期。

---

## 5. 简化业务流程

## 5.1 今日巡检

```text
平台调用 POST /api/v1/alerts/scan
→ Django读取模具
→ 按开发吨位选择3万或5万阈值
→ 返回正常、即将到期和已到期模具
→ 保存提醒记录
```

`alerts/scan` 同时返回：

```text
maintenance_due
maintenance_time_reminders
errors
```

时间提醒与模次到期必须分开。

## 5.2 创建工单

```text
平台选择一条模次到期提醒
→ POST /api/v1/work-orders
→ Django检查是否存在未关闭工单
→ 创建待派工工单
```

不再要求单独的主管确认角色。

## 5.3 候选人员与派工

```text
平台查询候选人员
→ Django按技能、负荷、产线和邮箱返回候选
→ 平台操作人员选择一人
→ POST /assign
→ Django重新校验候选人并保存派工
```

派工规则：

```text
技能匹配率 >= 80%
当前负荷 < 80%
同产线优先
邮箱已配置
高级技师可作为排序因素
```

## 5.4 知识随单和邮件

```text
平台读取工单知识上下文
→ 在知识库检索保养项目、点检、安全和验收要求
→ 回写知识快照
→ 平台发送邮件
→ 回写邮件结果
```

Django不发送邮件。

## 5.5 执行和点检

```text
已派工
→ 开工
→ 暂停 / 恢复
→ 提交点检结果
→ 报完工
→ 验收通过或转修模
```

点检项结果：

```text
PASS
FAIL
NOT_APPLICABLE
```

约束：

- 所有适用项填写后才能报完工；
- FAIL 必须填写异常说明；
- NOT_APPLICABLE 必须填写原因；
- 关键失败可转修模。

## 5.6 验收与复位

平台操作人员调用：

```text
accept
reject
transfer-to-repair
```

Django只检查工单状态和数据完整性，不检查角色。

验收通过后：

1. 工单变为 `COMPLETED`；
2. 创建保养履历；
3. 创建周期复位事件；
4. 更新周期基线；
5. 重算下一模次到期点；
6. 重算下一次2个月提醒；
7. 更新工时统计。

---

## 6. 技术基线

| 项目 | 测试服务器选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS 系列 |
| API | Django REST Framework 3.16 系列 |
| 数据库 | SQLite |
| 测试 | pytest + pytest-django |
| 质量检查 | Ruff |
| 运行端口 | 18080 |
| 运行方式 | runserver 或单进程 Gunicorn |
| API 鉴权 | 无 |
| 邮件 | 比赛平台发送 |
| 定时任务 | 比赛平台触发 |

---

## 7. 简化工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── .env.example
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── common/          # 响应、错误、request_id、幂等
│   ├── molds/           # 模具、规则、周期、提醒、复位
│   ├── staff/           # 人员、技能、负荷和候选查询
│   ├── workorders/      # 工单、派工、状态、点检、验收、知识和邮件记录
│   └── analytics/       # 工时、完成率和超时统计
├── data/demo/
├── docs/
├── tests/
├── scripts/
├── Dockerfile           # 可选
└── README.md
```

不建立：

```text
accounts
permissions
plans
standards
notifications
faults
audit
```

这些能力按测试需要合并到上述5个应用中。

---

## 8. 核心数据模型

## 8.1 Mold

```text
mold_id
mold_name
mold_type                  # INJECTION / SHEET_METAL
development_tonnage
current_count
location
production_line
status
created_at
updated_at
```

## 8.2 MaintenanceRule

测试版只保存当前规则：

```text
rule_id
mold_type_scope            # BOTH
min_tonnage
max_tonnage
count_threshold
authority                  # INTERNAL_CONFIRMED
version
is_active
```

默认种子：

```text
MAINT-TONNAGE-LT1000-V1  → 50000
MAINT-TONNAGE-GTE1000-V1 → 30000
```

## 8.3 MaintenanceCycle

```text
cycle_id
mold
cycle_version
baseline_count
baseline_time
count_threshold
next_due_count
next_time_reminder_at
status
```

## 8.4 CycleResetEvent

```text
reset_event_id
mold
reset_type
source_object_type
source_object_id
baseline_count_before
after_count
baseline_time_before
after_time
business_occurred_at
operator_id
operator_name
idempotency_key
created_at
```

复位类型：

```text
MAINTENANCE_COMPLETED
REPAIR_COMPLETED
INSERT_REPLACED
HISTORY_RECORD_IMPORTED
TEST_CORRECTION
```

## 8.5 Alert

```text
alert_id
mold
alert_type
rule_id
cycle_count
threshold
usage_percent
alert_level
status
created_at
```

类型：

```text
MAINTENANCE_DUE_COUNT
MAINTENANCE_TIME_REMINDER
```

## 8.6 Employee

```text
employee_id
employee_name
email
production_line
skills_json
current_load
on_duty
available
```

测试版不建立人员登录和权限。

## 8.7 WorkOrder

```text
work_order_id
alert
mold
status
priority
standard_hours
assigned_employee
assigned_at
started_at
reported_at
accepted_at
paused_seconds
completion_summary
created_at
updated_at
```

## 8.8 WorkOrderEvent

保存所有状态变化：

```text
event_type
from_status
to_status
operator_id
operator_name
remarks
created_at
```

## 8.9 InspectionResult

```text
work_order
knowledge_id
item_name
acceptance_criteria
result
abnormal_note
not_applicable_reason
performed_at
```

## 8.10 KnowledgeSnapshot

```text
work_order
catalog_version
knowledge_items_json
content_hash
created_at
```

## 8.11 NotificationRecord

```text
work_order
recipient_email
platform_message_id
status
sent_at
error_message
```

## 8.12 RepairReferral

```text
referral_id
work_order
reason
status
completed_at
```

## 8.13 MaintenanceRecord

```text
record_id
mold
work_order
maintenance_time
maintenance_count
actual_hours
result
```

---

## 9. 工单状态机

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

允许流转：

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

Django只校验状态，不校验操作者角色。

---

## 10. API 契约

## 10.1 请求头

```http
Content-Type: application/json
X-Request-ID: <optional>
Idempotency-Key: <recommended-for-write-actions>
```

没有：

```http
X-API-Key
Authorization
```

## 10.2 成功响应

```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": {},
  "request_id": "req-..."
}
```

## 10.3 错误响应

```json
{
  "code": "INVALID_STATE_TRANSITION",
  "message": "当前工单状态不允许执行该操作",
  "data": null,
  "request_id": "req-..."
}
```

## 10.4 核心接口

### 服务

```http
GET /api/v1/health
GET /api/v1/meta
POST /api/v1/demo/reset
```

### 模具和提醒

```http
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
GET  /api/v1/molds/{mold_id}/maintenance-cycle
GET  /api/v1/molds/{mold_id}/cycle-reset-events
POST /api/v1/alerts/scan
GET  /api/v1/alerts
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/alerts/{alert_id}/close
```

### 人员

```http
GET /api/v1/staff
GET /api/v1/staff/available
```

### 工单

```http
POST /api/v1/work-orders
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{work_order_id}
GET  /api/v1/work-orders/{work_order_id}/timeline
GET  /api/v1/work-orders/{work_order_id}/candidates
POST /api/v1/work-orders/{work_order_id}/assign
POST /api/v1/work-orders/{work_order_id}/start
POST /api/v1/work-orders/{work_order_id}/pause
POST /api/v1/work-orders/{work_order_id}/resume
POST /api/v1/work-orders/{work_order_id}/submit-for-inspection
POST /api/v1/work-orders/{work_order_id}/inspection-results
POST /api/v1/work-orders/{work_order_id}/report-complete
POST /api/v1/work-orders/{work_order_id}/accept
POST /api/v1/work-orders/{work_order_id}/reject
POST /api/v1/work-orders/{work_order_id}/transfer-to-repair
POST /api/v1/work-orders/{work_order_id}/cancel
```

### 知识与邮件回写

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge-snapshot
POST /api/v1/work-orders/{work_order_id}/notifications
GET  /api/v1/work-orders/{work_order_id}/notifications
```

### 周期复位

```http
POST /api/v1/molds/{mold_id}/repair-completed
POST /api/v1/molds/{mold_id}/insert-replaced
POST /api/v1/molds/{mold_id}/history-records
```

### 统计

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
GET /api/v1/analytics/overdue-orders
GET /api/v1/analytics/mold-history
```

---

## 11. 知识库与邮件关系

Django返回：

```text
mold_type
development_tonnage
trigger_rule_id
rule_version
knowledge_profile_code
knowledge_tags
```

平台检索：

```text
保养项目
点检清单
安全要求
验收标准
异常处理参考
```

平台回写知识快照，再发送邮件。

历史周期和保养等级资料可以出现在知识解释中，但不得覆盖 Django 返回的 30,000/50,000 模次当前规则。

---

## 12. 演示数据

最小准备：

```text
8套模具
2条正式吨位规则
6名模拟人员
8个技能
6条提醒
6张工单
注塑和钣金点检知识引用
1条邮件成功记录
1条邮件失败记录
1条点检失败转修模记录
```

必须覆盖：

- `<1000T` 的 50,000 模次规则；
- `>=1000T` 的 30,000 模次规则；
- 正常、即将到期、到期和超期；
- 注塑模具2个月提醒；
- 保养完成复位；
- 修模完成复位；
- 换镶件复位；
- 历史记录复位；
- 无候选人员；
- 邮件失败；
- 点检失败转修模。

管理命令：

```bash
python manage.py seed_demo_data
python manage.py reset_demo_data --confirm
python manage.py verify_demo_data
```

---

## 13. 测试要求

必须覆盖：

- 999.99T 使用 50,000 模次；
- 1000T 使用 30,000 模次；
- 开发吨位为空返回错误；
- 时间提醒只提醒，不建工单；
- 四类周期复位；
- 重复扫描不重复创建提醒；
- 重复创建工单返回已有工单；
- 候选人员筛选；
- 派工时重新校验人员状态；
- 全部合法和非法状态流转；
- 点检完整性；
- FAIL 和 NOT_APPLICABLE 约束；
- 邮件失败不回滚派工；
- 验收后生成履历并复位；
- 幂等键重复请求只执行一次；
- 无鉴权接口可以被平台直接调用；
- 重置演示数据后场景恢复。

质量门禁：

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
python manage.py check
pytest
python manage.py verify_demo_data
```

---

## 14. 实施阶段

### Phase 0：合同与演示数据

- 冻结字段、状态和错误码；
- 准备8套模具、6名人员和知识标签；
- 验证比赛平台可以调用无鉴权 GET/POST。

### Phase 1：Django骨架

- 初始化项目；
- 统一响应；
- Request-ID；
- 简单幂等；
- `/health` 和 `/meta`；
- pytest 和 Ruff。

### Phase 2：模具、规则、周期和提醒

- Mold；
- 两条吨位规则；
- MaintenanceCycle；
- CycleResetEvent；
- 时间提醒；
- `/alerts/scan`。

### Phase 3：人员和工单

- Employee；
- 候选查询；
- WorkOrder；
- 派工；
- 状态机和时间线。

### Phase 4：知识、邮件和点检

- knowledge-context；
- KnowledgeSnapshot；
- NotificationRecord；
- InspectionResult；
- 报完工和验收。

### Phase 5：转修模、复位和统计

- RepairReferral；
- 修模/换镶件/历史记录复位；
- MaintenanceRecord；
- 工时、完成率和超时。

### Phase 6：部署与平台联调

- SQLite持久化；
- 18080端口；
- 平台全链路；
- 连续3次演示；
- 比赛前备份数据库。

---

## 15. 部署

最简启动：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:18080
```

可选 Gunicorn：

```bash
gunicorn config.wsgi:application \
  --bind 0.0.0.0:18080 \
  --workers 1 \
  --threads 4
```

数据文件：

```text
data/db.sqlite3
```

比赛前备份：

```bash
python manage.py backup_demo_data
```

由于无鉴权，必须只使用模拟数据；比赛结束后停止服务。

---

## 16. 不在本测试服务器范围

- 企业账号、主管账号和人员登录；
- API Key、Token、权限和安全审计；
- 真实MES/ERP写入；
- 自动锁定真实排产；
- 自建邮件服务；
- 向量数据库；
- 完整修模工单流程；
- 备件和成本管理；
- 多基地、多租户和高并发；
- 生产级容灾、监控和合规。

---

## 17. Definition of Done

测试服务器达到以下条件即可标记：

```text
READY_FOR_COMPETITION_TEST
```

- [ ] 无主管角色和业务权限代码；
- [ ] API无鉴权，可被比赛平台直接调用；
- [ ] 只使用DEMO数据；
- [ ] 30,000/50,000吨位规则准确；
- [ ] 注塑2个月提醒只通知；
- [ ] 四类复位正确；
- [ ] 工单、派工、状态、点检和验收可演示；
- [ ] 知识快照和邮件结果可回写；
- [ ] 点检失败可转修模；
- [ ] 工时和完成率可查询；
- [ ] 重置命令可恢复完整演示场景；
- [ ] 全量测试通过；
- [ ] 连续3次平台演示无重复工单和5xx。

---

## 18. 最终冻结矩阵

| 决策项 | 最终结论 |
|---|---|
| 服务器定位 | 比赛测试服务器 |
| Django是否发送邮件 | 否 |
| 是否保留完整业务状态 | 是 |
| 是否有主管角色 | 否 |
| 是否有业务角色权限 | 否 |
| API是否鉴权 | 否 |
| 是否保留幂等和事务 | 是 |
| 数据库 | SQLite |
| 运行端口 | 18080 |
| HTTPS/Nginx | 可选，不是必需 |
| 自动触发规则 | `<1000T=50000`，`>=1000T=30000` |
| 保养等级 | 当前不区分 |
| 每2个月提醒 | 注塑模具，仅提醒 |
| 周期复位 | 保养、修模、换镶件、有效历史记录 |
| 知识库正文 | 比赛智能体平台 |
| 数据性质 | DEMO ONLY |
| 权威计划 | 本文件 V4.0 |

---

## 19. 最终结论

MoldGuard Django 的参赛实现不再按照企业生产系统建设，而是：

> **一个无鉴权、无角色、使用 SQLite 的 Django 模拟业务服务器。**

它仍保留模具规则、提醒、工单、派工、点检、验收、周期复位和统计，使智能体平台能够完整演示原方案中的预警、自动工单、过程追踪和工时分析；但去掉主管角色、安全鉴权、复杂部署和生产级治理，从而降低开发量和现场故障点。