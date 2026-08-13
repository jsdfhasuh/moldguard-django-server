# MoldGuard Django 测试服务器实施计划

- **计划状态**：`FINAL_FROZEN_KB_ALIGNED`
- **版本**：V4.2
- **日期**：2026-08-13
- **目标仓库**：`jsdfhasuh/moldguard-django-server`
- **建议实施分支**：`agent/django-test-server-v1`
- **知识库基线**：`MOLDGUARD-KB-1.2`
- **服务器定位**：无角色、无鉴权、仅使用 DEMO 数据的比赛测试服务器
- **权威性**：本计划与知识库 V1.2 一致；发生冲突时，以知识库 V1.2 为最终解释

---

## 1. 最终目标

```text
扫描模具触发条件
→ 自动建立 PENDING_ASSIGNMENT 工单
→ 查询候选人员并派工
→ 平台检索本次点检知识
→ 平台发送含点检知识和报工链接的邮件
→ 被派工人员点击链接开工/点检/报工
→ 正常报工自动完成并按矩阵复位周期
→ 异常报工进入继续处理或关联修模闭环
→ 查询工时、完成率和模具履历
```

Django 负责模拟业务数据、触发计算、工单状态和报工表单；智能体平台负责对话、知识检索、内容生成和邮件发送。

---

## 2. 最高优先级规则

### 2.1 注塑模具

| 规则 ID | 条件 | 结果 |
|---|---|---|
| `INJ-COUNT-050K` | 开发吨位 `<1000T` 且本周期有效模次达到 50,000 | 自动建立 `CYCLE_COUNT_MAINTENANCE` 工单 |
| `INJ-COUNT-030K` | 开发吨位 `>=1000T` 且本周期有效模次达到 30,000 | 自动建立 `CYCLE_COUNT_MAINTENANCE` 工单 |
| `INJ-TIME-2M` | 最近有效周期保养完成后 2 个月；无记录时从首次生产日期起算 | 自动建立 `CYCLE_TIME_MAINTENANCE` 工单 |
| `INJ-NO-OUTPUT-2Y` | 连续 2 年未更新产量 | 停止自动触发，仍允许人工建单 |
| `INJ-RESET-REPAIR` | 修模或换镶件后完成适用保养、点检并正常报工 | 作为 `REPAIR_SYNC_MAINTENANCE`，复位两个周期 |

### 2.2 钣金模具

| 规则 ID | `mold_category` | 类型编码 | 阈值 |
|---|---|---|---:|
| `STAMP-FORM-150K` | `FORMING` | LC102、LC104、LC106、LC107 | 150,000 |
| `STAMP-PUNCH-400K` | `PUNCH_BLANKING` | LC101、LC103、LC105 | 400,000 |
| `STAMP-PROG-400K` | `CONTINUOUS` | LC109 | 400,000 |
| `STAMP-SIDE-400K` | `SIDE_PANEL` | LC109 | 400,000 |

`LC109` 必须显式提供 `mold_category`，不得根据名称或位置猜测。

### 2.3 周期计算

```text
cycle_mold_cycles
= effective_mold_cycles - baseline_effective_mold_cycles
```

首次纳入系统必须提供基准模次；缺失时不得按 0 推算。

---

## 3. 测试服务器边界

保留：

- 自动触发与自动建单；
- 模拟人员与派工；
- 邮件知识包和报工链接；
- 开工、暂停、直接报工；
- 正常完成与异常闭环；
- 周期复位和基础统计；
- 状态机、事务、去重键和 Request-ID。

不实现：

- 用户登录、主管角色、审批和验收角色；
- API Key、JWT、Token；
- 历史文件导入；
- 真实 MES/ERP；
- Django 邮件发送；
- 生产级安全、容灾和高并发；
- 独立前端系统。

报工页面仅使用 Django 模板，不视为独立前端。

---

## 4. 技术基线

| 项目 | 选择 |
|---|---|
| Python | 3.12 |
| Django | 5.2 LTS 系列 |
| API | Django REST Framework 3.16 系列 |
| 数据库 | SQLite |
| 端口 | 18080 |
| 运行 | `runserver` 或单进程 Gunicorn |
| 邮件 | 比赛平台发送 |
| 知识库 | 比赛平台维护 |
| 鉴权 | 无 |

---

## 5. 工程结构

```text
moldguard-django-server/
├── manage.py
├── pyproject.toml
├── config/
├── apps/
│   ├── common/          # 响应、异常、Request-ID、重复请求处理
│   ├── molds/           # 模具、触发计算和提醒
│   ├── staff/           # 模拟人员和候选匹配
│   ├── workorders/      # 工单、状态、报工页面、知识和邮件字段
│   └── analytics/       # 工时、完成率和履历查询
├── templates/
│   └── report_form.html
├── data/demo/
├── tests/
└── README.md
```

---

## 6. 持久化模型

只建立 6 个模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

字段以 `docs/models/2026-08-13-django-model-field-review.md` V3.0 为准。

---

## 7. 工单状态机

```text
PENDING_ASSIGNMENT
→ ASSIGNED
→ IN_PROGRESS
→ COMPLETED
```

异常分支：

```text
IN_PROGRESS → PAUSED → IN_PROGRESS
IN_PROGRESS → ABNORMAL_REPORTED
ABNORMAL_REPORTED → IN_PROGRESS
ABNORMAL_REPORTED → REPAIR_LINKED
REPAIR_LINKED → IN_PROGRESS
```

附加终态：

```text
CANCELLED
```

正常报工经校验后直接 `COMPLETED`，不增加主管验收节点。

---

## 8. 邮件报工链接方案

### 8.1 派工响应

`POST /api/v1/work-orders/{id}/assign` 返回：

```json
{
  "work_order_id": "WO-20260813-001",
  "assignee_id": "EMP-001",
  "assignee_name": "张三",
  "assignee_email": "zhangsan@example.com",
  "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
  "report_method": "WEB_FORM",
  "report_url": "http://server:18080/report/WO-20260813-001",
  "report_button_text": "提交报工情况",
  "report_form_schema_version": "REPORT-FORM-1.0"
}
```

`report_url` 由 Django 动态生成，不要求数据库持久化；智能体平台不得自行拼接。

### 8.2 邮件内容

邮件至少包含：

- 模具和工单信息；
- 触发规则与要求完成时间；
- 本次适用的一份点检知识包；
- 操作步骤、安全要求和异常处理；
- `提交报工情况` 按钮；
- 知识快照版本。

### 8.3 报工页面

```http
GET  /report/{work_order_id}
POST /report/{work_order_id}
```

同时提供 JSON 接口：

```http
POST /api/v1/work-orders/{work_order_id}/report
```

页面展示工单和同一知识快照，填写：

```text
report_type                 NORMAL / ABNORMAL
report_summary
inspection_results          PASS / FAIL / NOT_APPLICABLE
abnormal_items
photos
parts_replaced
source_fault_id
actual_work_hours
abnormal_next_action        CONTINUE_PROCESSING / CREATE_REPAIR_TASK
```

Django自动记录 `reported_at` 和报工时有效模次快照。

### 8.4 提交结果

正常报工：

```text
校验全部必检项
→ COMPLETED
→ 创建 MaintenanceRecord
→ 按工单复位矩阵更新两个基准
→ 返回 next_due_count / next_due_time
```

异常报工：

```text
ABNORMAL_REPORTED
→ 不结单
→ 不复位
→ 继续处理或创建关联修模任务
```

重复正常报工返回原结果，不重复结单或复位。

---

## 9. 周期复位

正式有效工单正常报工时：

```text
baseline_effective_mold_cycles = 报工时 effective_mold_cycles
baseline_maintenance_at = reported_at
```

复位两个周期的工单类型：

```text
CYCLE_COUNT_MAINTENANCE
CYCLE_TIME_MAINTENANCE
REPAIR_SYNC_MAINTENANCE
```

轻量保养和储放记录不复位；异常报工不复位。

---

## 10. API 清单

### 服务与演示数据

```http
GET  /api/v1/health
GET  /api/v1/meta
POST /api/v1/demo/reset
```

### 模具、扫描与工单自动创建

```http
GET  /api/v1/molds
GET  /api/v1/molds/{mold_id}
GET  /api/v1/molds/{mold_id}/maintenance-status
POST /api/v1/alerts/scan
GET  /api/v1/alerts
POST /api/v1/work-orders/manual
```

`alerts/scan` 对达到条件的模具自动建立工单，并在响应中返回 `work_order_id`。

### 人员与派工

```http
GET  /api/v1/staff
GET  /api/v1/work-orders/{work_order_id}/candidates
POST /api/v1/work-orders/{work_order_id}/assign
```

### 工单执行与报工

```http
GET  /api/v1/work-orders
GET  /api/v1/work-orders/{work_order_id}
GET  /api/v1/work-orders/{work_order_id}/timeline
POST /api/v1/work-orders/{work_order_id}/start
POST /api/v1/work-orders/{work_order_id}/pause
POST /api/v1/work-orders/{work_order_id}/resume
GET  /report/{work_order_id}
POST /report/{work_order_id}
POST /api/v1/work-orders/{work_order_id}/report
POST /api/v1/work-orders/{work_order_id}/continue-processing
POST /api/v1/work-orders/{work_order_id}/create-repair-task
POST /api/v1/work-orders/{work_order_id}/repair-completed
POST /api/v1/work-orders/{work_order_id}/cancel
```

### 知识与邮件结果

```http
GET  /api/v1/work-orders/{work_order_id}/knowledge-context
POST /api/v1/work-orders/{work_order_id}/knowledge
POST /api/v1/work-orders/{work_order_id}/email-result
```

### 履历与统计

```http
GET /api/v1/molds/{mold_id}/records
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
```

---

## 11. 演示数据

至少准备：

- 注塑 `<1000T` 50,000 模次触发；
- 注塑 `>=1000T` 30,000 模次触发；
- 注塑 2 个月触发；
- 钣金成型类 150,000 触发；
- 钣金冲孔/连续/边板类 400,000 触发；
- LC109 缺少类别错误；
- 正常邮件报工并复位；
- 异常报工继续处理；
- 异常报工关联修模；
- 邮件发送成功和失败状态。

---

## 12. 必测行为

- 基准模次缺失不得默认 0；
- 注塑 999.99T 与 1000T 边界；
- 注塑两个月起算和首次生产日期回退；
- 两年无产量更新停止自动触发；
- 钣金四类规则和 LC109 显式类别；
- 同类未完成工单不重复创建；
- 派工响应必须包含 Django 生成的 `report_url`；
- 邮件知识快照与报工页面一致；
- 正常报工自动完成和复位；
- 异常报工不完成、不复位；
- `CHK-STAMP-009` 不由服务器自动判定；
- 相似故障仅返回候选，不默认工时；
- 重复报工不重复结单；
- 重置命令恢复全部场景。

---

## 13. 实施阶段

1. **Phase 0**：冻结 V1.2 字段、状态、接口和演示数据；
2. **Phase 1**：Django 骨架、统一响应、SQLite、测试；
3. **Phase 2**：模具、触发规则、扫描和自动建单；
4. **Phase 3**：人员、候选和派工；
5. **Phase 4**：知识包、邮件结果和报工页面；
6. **Phase 5**：正常/异常报工、关联修模、周期复位和统计；
7. **Phase 6**：比赛平台全链路联调，连续 3 次成功演示。

---

## 14. Definition of Done

```text
READY_FOR_COMPETITION_TEST
```

- [ ] 知识库版本为 `MOLDGUARD-KB-1.2`；
- [ ] 触发规则完全按知识库第一部分；
- [ ] 无主管、无登录、无 API 鉴权；
- [ ] 工单自动创建、派工和邮件链接可用；
- [ ] 报工页面展示同一知识快照；
- [ ] 正常报工自动完成和正确复位；
- [ ] 异常闭环可继续处理或关联修模；
- [ ] 字段、API、知识包和 JSONL 契约一致；
- [ ] 全量测试和连续 3 次演示通过。
