# MoldGuard 邮件点检知识与报工链接契约

- **版本**：REPORT-FORM-1.0
- **知识库**：MOLDGUARD-KB-1.2
- **服务器**：MoldGuard Django Test Server V4.2

## 1. 派工输出

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

## 2. 邮件要求

邮件包含工单信息、触发依据、本次适用的一份点检知识包、安全要求、要求完成时间以及 `report_url` 按钮。

## 3. 报工提交

```json
{
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
  "abnormal_next_action": null
}
```

## 4. 状态结果

- `NORMAL` 且校验通过：`COMPLETED`，按复位矩阵更新周期；
- `ABNORMAL`：`ABNORMAL_REPORTED`，不复位；
- 异常后可 `CONTINUE_PROCESSING` 或 `CREATE_REPAIR_TASK`；
- 重复正常报工返回原结果，不重复复位。
