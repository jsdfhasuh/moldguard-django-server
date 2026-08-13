# MoldGuard 邮件点检知识与报工链接契约

- **版本**：`REPORT-FORM-1.1`
- **知识库**：`MOLDGUARD-KB-1.2`
- **计划**：V5.0 + V5.1
- **服务器**：MoldGuard Competition Server
- **身份模式**：无登录；服务器使用工单 `assignee` 作为报工人员

## 1. 派工输出

```json
{
  "code": "SUCCESS",
  "message": "派工成功",
  "data": {
    "work_order_id": "WO-20260813-001",
    "assignee_id": "EMP-001",
    "assignee_name": "张三",
    "assignee_email": "zhangsan@example.com",
    "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
    "knowledge_package_hash": "",
    "report_method": "WEB_FORM",
    "report_url": "https://moldguard.example.com/report/WO-20260813-001",
    "report_button_text": "提交报工情况",
    "report_form_schema_version": "REPORT-FORM-1.1"
  },
  "request_id": "req-001"
}
```

约束：

- `report_url` 只能由 Django 根据 `MOLDGUARD_PUBLIC_BASE_URL` 生成；
- 智能体平台不得自行拼接或改写链接；
- 客户端不在报工请求中提交 `employee_id`；
- 服务器以工单 `assignee` 作为报工人。

## 2. 知识包写入与锁定

```http
POST /api/v1/work-orders/{work_order_id}/knowledge
```

请求：

```json
{
  "client_request_id": "knowledge-WO-001-001",
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
  "safety_notes": ["设备停止、断电并防止误启动"],
  "source_documents": ["02_保养内容_点检_储放_故障工时与邮件链接报工.md"]
}
```

Django对规范化 JSON 计算：

```text
knowledge_package_hash = SHA-256
```

允许覆盖：

```text
email_status为NOT_SENT或FAILED
且工单尚未报工
```

禁止覆盖：

```text
email_status为SENDING、SENT或OUTCOME_UNKNOWN
或工单已有报工结果
```

错误码：

```text
KNOWLEDGE_PACKAGE_LOCKED
KNOWLEDGE_VERSION_MISMATCH
```

## 3. SMTP派工邮件

```http
GET /api/v1/work-orders/{work_order_id}/email-context
```

前置条件：

```text
工单已派工
知识包已保存
```

返回至少包含：

```text
assignee_email
email_subject
work_order
mold
trigger
required_finish_at
standard_hours
knowledge_package
knowledge_snapshot_version
knowledge_package_hash
report_url
report_button_text
report_form_schema_version
```

`email-context` 只用于预览和调试，不改变邮件状态。

Django发送接口：

```http
POST /api/v1/work-orders/{work_order_id}/send-email
```

请求只允许：

```json
{
  "client_request_id": "send-email-WO-001-001"
}
```

不得接受 `recipient`、`subject`、`body`、`html_body` 或 `from_email`。收件人固定为
`work_order.assignee.email`；主题和正文由Django模板渲染。

成功响应数据至少包含：

```text
work_order_id
old_email_status
new_email_status=SENT
email_message_id
email_sent_at
email_recipient
knowledge_snapshot_version
knowledge_package_hash
knowledge_locked_at
report_url
```

邮件同时包含 `text/plain` 与 `text/html`。两种正文都包含工单、模具、触发依据、
标准工时、完成期限、知识包全部点检项、安全注意事项、知识版本、知识哈希和
`report_url`。HTML保持Django默认自动转义。

状态：

```text
NOT_SENT / FAILED → SENDING → SENT
NOT_SENT / FAILED → SENDING → FAILED
NOT_SENT / FAILED → SENDING → OUTCOME_UNKNOWN
```

- `SENT` 锁定知识包，新发送ID返回 `EMAIL_ALREADY_SENT`；
- `FAILED` 不锁定，允许使用新ID重试；
- `OUTCOME_UNKNOWN` 锁定并禁止自动重发；
- 同一ID的最终结果精确重放，不再次发送；
- 相同ID处于占位期返回 `EMAIL_SEND_IN_PROGRESS`；
- 公开API和OpenAPI不提供 `email-result`。

SMTP发送使用专用两阶段幂等：先短事务提交102占位，再在事务外调用SMTP，最后短
事务同时保存工单结果、事件和幂等最终响应。

## 4. HTML 报工入口

```http
GET  /report/{work_order_id}
POST /report/{work_order_id}
```

页面展示：

```text
工单编号
模具编号和名称
工单类型
被派工人员（只读）
触发依据
要求完成时间
标准工时（有配置时）
知识快照版本
知识包哈希
本次点检知识和安全要求
```

页面表单不得提供员工编号输入框。

HTML隐藏字段：

```text
submission_id
report_form_schema_version=REPORT-FORM-1.1
knowledge_package_hash
```

## 5. JSON 报工接口

```http
POST /api/v1/work-orders/{work_order_id}/report
```

### 5.1 字段

| 字段 | 必填 | 规则 |
|---|---:|---|
| `client_request_id` | 是 | 最长120；全局幂等ID |
| `report_type` | 是 | `NORMAL` / `ABNORMAL` |
| `report_summary` | 是 | 1—2000字符 |
| `inspection_results` | 是 | 至少1项，不允许重复 `knowledge_id` |
| `abnormal_items` | 条件 | ABNORMAL时至少1项，或至少存在一个FAIL |
| `photos` | 否 | 最多10个URL或文本引用，不接收二进制 |
| `parts_replaced` | 否 | 最多50项 |
| `source_fault_id` | 否 | 知识库故障源表ID |
| `actual_work_hours` | 是 | `>0` 且 `<=999.99` |
| `abnormal_next_action` | 条件 | `CONTINUE_PROCESSING` / `CREATE_REPAIR_TASK` |
| `knowledge_package_hash` | 是 | 必须等于工单已锁定/当前知识包哈希 |

点检项：

| 字段 | 必填 | 规则 |
|---|---:|---|
| `knowledge_id` | 是 | 必须存在于工单知识包 |
| `result` | 是 | `PASS/FAIL/NOT_APPLICABLE` |
| `not_applicable_reason` | 条件 | `NOT_APPLICABLE`时必填 |
| `abnormal_note` | 条件 | `FAIL`时必填 |

### 5.2 NORMAL 请求

```json
{
  "client_request_id": "report-WO-001-normal",
  "report_type": "NORMAL",
  "report_summary": "已完成保养并逐项检查",
  "inspection_results": [
    {
      "knowledge_id": "CHK-INJ-001",
      "result": "PASS",
      "not_applicable_reason": "",
      "abnormal_note": ""
    }
  ],
  "abnormal_items": [],
  "photos": [],
  "parts_replaced": [],
  "source_fault_id": null,
  "actual_work_hours": 2.5,
  "abnormal_next_action": null,
  "knowledge_package_hash": "abc123..."
}
```

NORMAL校验：

```text
允许来源状态：ASSIGNED / IN_PROGRESS
全部required点检项已提交
不存在FAIL
NOT_APPLICABLE全部有原因
abnormal_items必须为空
abnormal_next_action必须为空
```

成功后：

```text
COMPLETED
创建MaintenanceRecord
按复位矩阵更新周期
关闭对应Alert
```

### 5.3 ABNORMAL 请求

```json
{
  "client_request_id": "report-WO-001-abnormal",
  "report_type": "ABNORMAL",
  "report_summary": "发现冷却水路堵塞",
  "inspection_results": [
    {
      "knowledge_id": "CHK-INJ-010",
      "result": "FAIL",
      "not_applicable_reason": "",
      "abnormal_note": "水路不通"
    }
  ],
  "abnormal_items": [
    {
      "item": "冷却水路",
      "description": "水路堵塞，常规保养无法处理"
    }
  ],
  "photos": [],
  "parts_replaced": [],
  "source_fault_id": null,
  "actual_work_hours": 1.5,
  "abnormal_next_action": "CONTINUE_PROCESSING",
  "knowledge_package_hash": "abc123..."
}
```

ABNORMAL校验：

```text
允许来源状态：ASSIGNED / IN_PROGRESS / PAUSED
至少一个FAIL或abnormal_item
异常说明非空
```

成功后：

```text
ABNORMAL_REPORTED
不创建最终MaintenanceRecord
不关闭Alert
不复位周期
```

## 6. 成功响应

```json
{
  "code": "SUCCESS",
  "message": "报工提交成功",
  "data": {
    "work_order_id": "WO-20260813-001",
    "old_status": "ASSIGNED",
    "new_status": "COMPLETED",
    "report_type": "NORMAL",
    "reported_at": "2026-08-13T18:00:00+08:00",
    "assignee_id": "EMP-001",
    "assignee_name": "张三",
    "actual_work_hours": "2.50",
    "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
    "knowledge_package_hash": "abc123...",
    "reset_count_cycle": true,
    "reset_time_cycle": true,
    "next_due_count": 200000,
    "next_due_time": "2026-10-13T18:00:00+08:00",
    "replayed": false
  },
  "request_id": "req-002"
}
```

相同请求重放时：

```text
replayed=true
```

## 7. HTTP 状态和错误码

| HTTP | 错误码 | 含义 |
|---:|---|---|
| 400 | `VALIDATION_ERROR` | 字段校验失败 |
| 400 | `INSPECTION_ITEMS_INCOMPLETE` | 必检项缺失 |
| 400 | `NOT_APPLICABLE_REASON_REQUIRED` | 不适用原因缺失 |
| 400 | `ABNORMAL_DESCRIPTION_REQUIRED` | 异常说明缺失 |
| 404 | `WORK_ORDER_NOT_FOUND` | 工单不存在 |
| 409 | `INVALID_WORK_ORDER_STATE` | 当前状态不允许报工 |
| 409 | `KNOWLEDGE_PACKAGE_REQUIRED` | 未保存知识包 |
| 409 | `KNOWLEDGE_VERSION_MISMATCH` | 知识版本不一致 |
| 409 | `KNOWLEDGE_PACKAGE_HASH_MISMATCH` | 知识哈希不一致 |
| 409 | `KNOWLEDGE_PACKAGE_LOCKED` | 已发送邮件或已报工，知识不可覆盖 |
| 409 | `EMAIL_ALREADY_SENT` | 邮件已经发送，不允许使用新ID重复发送 |
| 409 | `EMAIL_SEND_IN_PROGRESS` | 相同发送请求仍在执行 |
| 409 | `EMAIL_SEND_OUTCOME_UNKNOWN` | 历史发送结果不明，禁止自动重发 |
| 502 | `EMAIL_SEND_FAILED` | SMTP明确失败，可使用新ID重试 |
| 502 | `EMAIL_SEND_OUTCOME_UNKNOWN` | SMTP结果无法确认，不自动重试 |
| 409 | `REPORT_ALREADY_SUBMITTED` | 已完成工单重复提交不同内容 |
| 409 | `CLIENT_REQUEST_CONFLICT` | 相同幂等ID对应不同请求 |

## 8. HTML与JSON一致性

HTML和JSON接口必须调用同一个报工服务函数，使用相同：

```text
状态校验
点检完整性校验
知识哈希校验
幂等记录
事务
周期复位
响应数据
```

HTML提交成功后渲染结果页；已完成工单再次打开时只显示已提交结果。
