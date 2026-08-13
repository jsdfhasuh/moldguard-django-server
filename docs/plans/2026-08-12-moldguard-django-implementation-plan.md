# MoldGuard Django 最小测试服务器实施计划

- **计划状态**：`FINAL_FROZEN_MINIMAL_TEST_SERVER`
- **系统状态**：`NOT_IMPLEMENTED`
- **版本**：V4.1
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **默认分支**：`main`
- **建议实施分支**：`agent/django-test-server-v1`
- **系统定位**：比赛智能体平台使用的最小外部模拟业务服务器
- **数据性质**：`DEMO ONLY`
- **知识库基线**：`MoldGuard_模具保养知识库_上传包V0.1.zip`
- **权威性**：本文件替代 V4.0 及更早计划，作为后续编码、测试和联调的唯一实施基线

---

## 1. 最终目标

Django 只实现比赛演示真正需要的模拟数据、规则计算和工单状态，不按照企业生产系统建设。

保留主链路：

```text
查询模具
→ 扫描保养提醒
→ 创建工单
→ 查询候选人员并派工
→ 平台检索知识并发送邮件
→ 开工 / 暂停 / 恢复
→ 提交点检和报完工
→ 验收完成 / 退回 / 转修模
→ 周期复位
→ 查询工时和完成率
```

智能体平台负责对话、流程、知识库、LLM 和邮件；Django 负责模拟业务事实和状态。

---

## 2. 本版进一步删除的内容

V4.1 按“能删就删”的原则，删除以下功能：

```text
历史记录导入
历史导入批次和导入行
来源文件、来源记录编号和导入哈希
主管、管理员、计划员等角色
用户登录和任何 API 鉴权
保养计划、两次关闭机会和送模状态
健康评分
排产锁定状态
复杂规则审批、冲突和多版本规则表
一级、二级、三级保养模型
独立 MaintenanceRule 数据表
独立 MaintenanceCycle 数据表
独立 CycleResetEvent 数据表
独立 KnowledgeSnapshot 数据表
独立 NotificationRecord 数据表
独立 InspectionResult 数据表
独立 RepairReferral 数据表
独立 IdempotencyRecord 数据表
完整修模工单
故障标准数据库
点检照片上传
知识快照多版本
邮件抄送、邮件主题模板和附件记录
PostgreSQL、Redis、Celery、Nginx强制配置
生产级安全、审计和容灾
```

历史知识仍保留在比赛平台知识库中，但 Django 不导入历史规则或历史业务记录。

---

## 3. 最终系统分工

### 3.1 智能体平台负责

- 用户自然语言交互；
- Workflow / Agent 编排；
- 定时或手动触发巡检；
- 点检、操作、安全和验收知识库；
- RAG 检索与来源展示；
- LLM 生成预警、任务和分析说明；
- 展示候选人员并让平台操作人员选择；
- 生成和发送邮件；
- 将单份知识快照和邮件结果回写 Django。

### 3.2 Django 负责

- 模拟模具、开发吨位、累计模次、周期基线和位置；
- 30,000 / 50,000 模次触发规则；
- 注塑模具每 2 个自然月信息提醒；
- 保养到期提醒；
- 模拟人员、技能、负荷、产线和测试邮箱；
- 工单创建、派工、状态机和时间线；
- 单份点检 JSON、单份知识快照 JSON 和单次邮件结果；
- 报完工、验收、退回和转修模状态；
- 保养、修模、换镶件后的周期复位；
- 系统生成的模具履历、工时和完成率统计；
- 演示数据初始化、重置和备份。

### 3.3 Django 不负责

- 历史数据文件导入；
- 用户、主管或业务权限；
- API Key、Token、JWT 或登录态；
- 大模型和向量检索；
- SMTP 和邮件发送；
- 真实 MES、ERP 或排产系统；
- 生产级安全和长期公网运行。

---

## 4. 已确认业务规则

### 4.1 自动保养触发

钣金和注塑模具不区分一级、二级、三级保养。

```text
开发吨位 < 1000T  → 周期模次达到 50,000 时触发
开发吨位 >= 1000T → 周期模次达到 30,000 时触发
```

代码中使用两个常量规则，不建立规则数据表：

```text
MAINT-TONNAGE-LT1000-V1
MAINT-TONNAGE-GTE1000-V1
```

计算：

```text
cycle_count = current_count - cycle_baseline_count
next_due_count = cycle_baseline_count + threshold
remaining_count = max(threshold - cycle_count, 0)
overdue_count = max(cycle_count - threshold, 0)
usage_percent = cycle_count / threshold × 100
```

开发吨位为空时返回：

```text
DEVELOPMENT_TONNAGE_NOT_CONFIGURED
```

### 4.2 每 2 个月提醒

当前仅适用于注塑模具：

```text
cycle_baseline_time + 2 calendar months
→ 创建信息提醒
→ 平台发送提醒
→ 不自动创建工单
→ 不自动派工
```

### 4.3 周期复位

保留三类复位：

```text
保养完成
修模完成
换镶件完成
```

**删除“上传历史记录复位周期”。**

复位直接更新 Mold：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version + 1
last_reset_type
last_reset_at
```

并创建一条系统履历 `MaintenanceRecord`。

---

## 5. 最终模型范围

V4.1 只建立 6 个持久化模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

不再建立其他业务模型。

---

## 6. 模型字段

## 6.1 Mold

```text
mold_id                    # 唯一业务编号
mold_name
mold_type                  # INJECTION / SHEET_METAL
development_tonnage
current_count
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type            # INITIAL / MAINTENANCE / REPAIR / INSERT_REPLACEMENT
last_reset_at
location
production_line
status                     # IN_PRODUCTION / IN_STORAGE / UNDER_REPAIR / DISABLED
knowledge_profile_code
created_at
updated_at
```

不保存：

```text
模具等级
模具类别
腔数
一级位置和二级位置拆分
上次保养模次重复字段
上次保养时间重复字段
健康评分
历史导入信息
```

## 6.2 Alert

```text
alert_id
mold
alert_type                 # MAINTENANCE_DUE_COUNT / MAINTENANCE_TIME_REMINDER
cycle_version
cycle_count_snapshot
threshold_snapshot         # 时间提醒可为空
usage_percent_snapshot     # 时间提醒可为空
status                     # OPEN / ACKNOWLEDGED / CLOSED
dedupe_key                 # 唯一，防止重复扫描
created_at
closed_at
```

## 6.3 Employee

```text
employee_id
employee_name
email
production_line
skills_json
current_load
on_duty
available
created_at
updated_at
```

不保存班组、技师等级、账号和权限。

## 6.4 WorkOrder

```text
work_order_id
alert
mold
status
priority                   # NORMAL / HIGH / URGENT
standard_hours
required_finish_at
assigned_employee
required_skills_json
knowledge_profile_code
knowledge_snapshot_json    # 单份JSON
inspection_items_json      # 模板和结果统一JSON
email_recipient
email_status               # NOT_SENT / SENT / FAILED
email_message_id
email_sent_at
email_error
assigned_at
started_at
pause_started_at
paused_seconds
reported_at
accepted_at
completion_summary
repair_reason
create_key                 # 唯一，防止重复建单
created_at
updated_at
```

工时不重复落库，通过时间字段动态计算：

```text
派工至报工总历时
等待开工时长
实际执行时长
暂停时长
```

## 6.5 WorkOrderEvent

```text
work_order
event_type
from_status
to_status
operator_name              # 可空，仅演示
remarks
request_key                # 可空，重复请求时复用
created_at
```

## 6.6 MaintenanceRecord

只保存系统产生的履历，不支持文件导入：

```text
record_id
mold
work_order                 # 可空
record_type                # MAINTENANCE / REPAIR / INSERT_REPLACEMENT
occurred_at
occurred_count
result
note
request_key                # 唯一，防止重复复位
created_at
```

创建记录后同步更新 Mold 的周期基线。

---

## 7. 工单状态机

```text
PENDING_ASSIGNMENT
ASSIGNED
IN_PROGRESS
PAUSED
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
IN_PROGRESS → PENDING_ACCEPTANCE
PENDING_ACCEPTANCE → COMPLETED
PENDING_ACCEPTANCE → IN_PROGRESS
PENDING_ACCEPTANCE → TRANSFERRED_TO_REPAIR
```

不再单独设置 `PENDING_INSPECTION`。点检结果在报完工时一次校验。

---

## 8. 点检最小实现

点检模板和结果统一保存在：

```text
WorkOrder.inspection_items_json
```

结构示例：

```json
[
  {
    "knowledge_id": "KB-INS-001",
    "item": "模腔清洁",
    "criteria": "无残料、无油污",
    "result": "PASS",
    "note": ""
  }
]
```

约束：

- 每项必须有 `PASS`、`FAIL` 或 `NOT_APPLICABLE`；
- `FAIL` 必须填写 `note`；
- `NOT_APPLICABLE` 必须填写 `note`；
- 存在 `FAIL` 时不能验收完成，只能退回或转修模。

不保存图片引用，不建立点检子表。

---

## 9. 知识和邮件最小实现

### 9.1 知识上下文

Django只返回：

```text
mold_type
knowledge_profile_code
trigger_rule_id
threshold
```

平台负责检索知识。

### 9.2 知识快照

一个工单只保存一份：

```text
knowledge_snapshot_json
```

允许平台重复提交覆盖，保留最后一次内容即可；不做版本管理。

### 9.3 邮件结果

邮件由平台发送，Django仅把最后一次结果保存到 WorkOrder：

```text
email_recipient
email_status
email_message_id
email_sent_at
email_error
```

不保存主题、抄送、附件和多次尝试历史。

---

## 10. API 范围

### 服务和演示数据

```http
GET  /api/v1/health
GET  /api/v1/meta
POST /api/v1/demo/reset
```

### 模具和提醒

```http
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
POST /api/v1/alerts/scan
GET  /api/v1/alerts
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
POST /api/v1/work-orders/{work_order_id}/inspection
POST /api/v1/work-orders/{work_order_id}/report-complete
POST /api/v1/work-orders/{work_order_id}/accept
POST /api/v1/work-orders/{work_order_id}/reject
POST /api/v1/work-orders/{work_order_id}/transfer-to-repair
POST /api/v1/work-orders/{work_order_id}/cancel
```

### 知识与邮件

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge
POST /api/v1/work-orders/{work_order_id}/email-result
```

### 其他周期复位

```http
POST /api/v1/molds/{mold_id}/repair-completed
POST /api/v1/molds/{mold_id}/insert-replaced
```

**删除：**

```http
POST /api/v1/molds/{mold_id}/history-records
POST /api/v1/maintenance-history/imports
```

### 履历和统计

```http
GET /api/v1/molds/{mold_id}/records
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
```

删除复杂超时、停机、趋势、同比和环比接口。

---

## 11. 请求与稳定性

无鉴权。请求头只保留：

```http
Content-Type: application/json
X-Request-ID: <optional>
Idempotency-Key: <recommended>
```

不建立通用幂等数据表：

- Alert 使用 `dedupe_key`；
- WorkOrder 使用 `create_key`；
- WorkOrderEvent 使用 `request_key`；
- MaintenanceRecord 使用 `request_key`。

重复请求返回已存在结果，不重复写入。

---

## 12. 演示数据

最小准备：

```text
6套模具
2条代码常量规则
4名模拟人员
4张工单
1份注塑点检JSON
1份钣金点检JSON
1条邮件成功状态
1条点检失败转修模状态
```

覆盖：

```text
<1000T的50,000模次规则
>=1000T的30,000模次规则
正常、即将到期、到期和超期
注塑2个月提醒
保养完成复位
修模完成复位
换镶件完成复位
无候选人员
邮件失败
点检失败转修模
```

不准备历史导入场景。

---

## 13. 实施阶段

### Phase 0：字段与 API 合同

- 冻结 6 个模型；
- 冻结状态和错误码；
- 准备 6 套模具和 4 名人员；
- 验证平台 GET / POST。

### Phase 1：Django 骨架

- Django、DRF、SQLite；
- 统一响应；
- Request-ID；
- `/health`、`/meta`、`/demo/reset`；
- pytest 和 Ruff。

### Phase 2：模具和提醒

- Mold；
- 代码常量规则；
- Alert；
- maintenance-status；
- alerts/scan；
- 2个月提醒。

### Phase 3：人员和工单

- Employee；
- WorkOrder；
- WorkOrderEvent；
- 候选查询；
- 派工和状态机。

### Phase 4：知识、邮件和点检

- knowledge-context；
- knowledge JSON；
- email-result；
- inspection JSON；
- 报完工、验收和转修模。

### Phase 5：复位、履历和统计

- MaintenanceRecord；
- 保养验收复位；
- 修模完成复位；
- 换镶件完成复位；
- 工时与完成率。

### Phase 6：平台联调

连续完成 3 次：

```text
扫描提醒
→ 创建工单
→ 派工
→ 知识与邮件
→ 开工/暂停
→ 点检/报完工
→ 验收与复位
→ 统计
```

---

## 14. Definition of Done

系统达到以下条件即可标记：

```text
READY_FOR_COMPETITION_TEST
```

- [ ] 仅 6 个业务模型；
- [ ] 无历史导入代码；
- [ ] 无用户、主管、角色和鉴权；
- [ ] 无健康评分；
- [ ] 无计划、送模和关闭次数；
- [ ] 无复杂规则表；
- [ ] 无独立知识、邮件、点检和转修模子表；
- [ ] 30,000 / 50,000 规则准确；
- [ ] 注塑 2 个月提醒只通知；
- [ ] 保养、修模、换镶件复位正确；
- [ ] 工单、派工、状态、点检和验收可演示；
- [ ] 工时和完成率可查询；
- [ ] 演示数据可一键重置；
- [ ] 全量测试通过；
- [ ] 连续 3 次平台演示无重复工单和 5xx。

---

## 15. 最终结论

MoldGuard Django 的最终实现是：

> **一个无鉴权、无角色、使用 SQLite、只有 6 个业务模型的比赛模拟服务器。**

它保留预警、工单、派工、知识随单、过程状态、点检、验收、周期复位和基础统计；删除历史导入、健康评分、计划送模、复杂规则治理、多版本知识、复杂邮件记录和生产级设施，优先保证开发简单、平台容易调用、比赛现场稳定。