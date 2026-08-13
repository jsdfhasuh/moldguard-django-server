# MoldGuard 比赛平台测试指南

本指南描述比赛智能体平台如何调用开放的 MoldGuard 探测服务器。所有路径以 `/api/v1` 为前缀，所有 POST 使用 JSON 且必须带唯一 `client_request_id`。不发送登录、Authorization、Token、API Key 或角色信息。

## 1. 连通性与探测运行

1. 调用 `GET /health` 和 `GET /meta`，确认 `authentication=NONE`。
2. 调用 `POST /probe/runs`：

```json
{
  "platform_name": "competition-agent-platform",
  "tester": "team-demo",
  "mode": "STRICT",
  "client_request_id": "probe-run-001"
}
```

3. 保存响应中的 `run_id`，动态拼接 `GET /probe/runs/{run_id}/context`。
4. 从 `data.challenge` 读取 `dynamic_variables`、`nested_json` 和 `array_items`，原样提交到 `POST /probe/runs/{run_id}/variable-test`。严格模式不要扁平化或逐条拆分数组。
5. 平台完成其他节点后，可在 `capability_results` 中回写 P05–P11 和 P13 的真实结果及证据。严格模式不能使用 `PASS_WITH_ADAPTER`；原生失败后另建 `COMPATIBILITY` run 验证适配方案。
6. 平台定时节点调用 `POST /probe/scheduler-heartbeat`，body 至少包含 `run_id` 和 `client_request_id`。
7. 调用 `GET /probe/runs/{run_id}/report` 查看矩阵。没有平台证据的能力保持 `NOT_TESTED`。

状态只能是：`PASS_NATIVE`、`PASS_WITH_ADAPTER`、`MANUAL_VERIFIED`、`EXTERNAL_REQUIRED`、`BLOCKED`、`NOT_TESTED`。

## 2. 扫描与预警

调用：

```http
POST /alerts/scan
```

```json
{"client_request_id":"platform-scan-001"}
```

遍历 `data.results`：

- `MAINTENANCE_DUE`：取 `alert_ids` 中模次预警，进入工单流程；
- `TWO_MONTH_REMINDER`：只展示“仅表示已满2个月，不代表模次保养条件已达到。”，不要创建工单；
- `IDLE_AUTO_REMINDER_DISABLED`：提示两年无产量停扫；
- `DEVELOPMENT_TONNAGE_NOT_CONFIGURED` / `INVALID_CYCLE_COUNT`：展示配置错误；
- `NO_ALERT_DUE`：结束该模具分支。

重复扫描使用新的请求 ID 时数据库也不会重复生成同周期预警；网络重试必须复用原请求 ID，服务器会重放原结果。

## 3. 工单与派工

1. `POST /alerts/{alert_id}/create-work-order`，保存 `work_order_id`。
2. `GET /work-orders/{work_order_id}/candidates`，确认平台能够遍历候选数组。
3. 二选一：
   - 自动：`POST /work-orders/{id}/auto-assign`，只传 `client_request_id`；
   - 指定：`POST /work-orders/{id}/assign`，传 `employee_id` 和 `client_request_id`。
4. 保存响应中的 `assigned_employee.employee_id` 与 `assigned_employee.email`。只有该员工能执行后续主动报工。

自动派工由 Django 按“可用、技能匹配、负荷升序、员工号升序”确定，平台不需要自行排序。

## 4. 知识检索与快照

1. `GET /work-orders/{id}/knowledge-context`。
2. 用 `mold_type`、`rule_id`、`knowledge_profile_code`、`query_keywords[]` 和 `required_types[]` 检索平台知识库。
3. 将实际使用条目回写 `POST /work-orders/{id}/knowledge-snapshot`：

```json
{
  "catalog_version":"competition-kb-v1",
  "items":[
    {
      "knowledge_id":"KB-INJECTION-001",
      "title":"型腔点检",
      "item":"检查模具表面及型腔",
      "knowledge_type":"INSPECTION_STANDARD",
      "content":"清洁后检查表面和型腔",
      "source":"competition-kb",
      "required":true
    }
  ],
  "client_request_id":"snapshot-001"
}
```

正常报工必须提交快照里所有 `required=true` 的 `knowledge_id`。

## 5. 动态邮件与结果回写

1. `GET /work-orders/{id}/email-context`。
2. 使用 `to[]`、`subject` 和 `template_variables` 生成并发送任务邮件。响应不会包含 `cc` 或主管地址。
3. 回写 `POST /work-orders/{id}/notifications`：

成功：

```json
{
  "status":"SENT",
  "message_id":"platform-message-001",
  "sent_at":"2026-08-13T15:00:00+08:00",
  "client_request_id":"notification-001"
}
```

失败：

```json
{
  "status":"FAILED",
  "error_message":"平台邮件服务超时",
  "client_request_id":"notification-002"
}
```

Django 只保存结果，不发送邮件。

## 6. 主动开工、暂停与恢复

被派工人员可依次调用：

```text
POST /work-orders/{id}/start
POST /work-orders/{id}/pause
POST /work-orders/{id}/resume
```

body 均包含 `employee_id` 和 `client_request_id`；可用 `occurred_at` 回写平台记录时间，暂停还可填 `reason`。暂停段会从实际工时中扣除。

平台也可跳过 start，从 `ASSIGNED` 一次性正常报工，但必须显式提交 `started_at` 与 `completed_at`，服务器不会猜开工时间。

## 7. 正常与异常报工

正常接口：`POST /work-orders/{id}/report-complete`。

- `employee_id` 必须等于被派工人员；
- 提交全部必检项；
- 不得存在 `FAIL`；
- `NOT_APPLICABLE` 必须填写 `reason`；
- `completed_at` 必须晚于 `started_at`。

成功后直接进入 `COMPLETED`，在同一事务内创建 WorkReport/履历、复位周期、关闭模次预警并返回下一触发模次，不存在主管验收节点。

有 `FAIL` 时改用 `POST /work-orders/{id}/report-abnormal`，传 `abnormal_type`、`description` 和至少一个带 `note` 的 FAIL 项。成功后进入 `ABNORMAL_REPORTED`；周期基准、周期版本和预警需求保持不变。

最后调用 `GET /work-orders/{id}/history` 核验事件、暂停段、报工、异常和履历证据。

## 8. 重试规则

平台对超时或网络错误重试时必须复用完全相同的 body 和 `client_request_id`。服务器返回首次成功响应，并在 `data` 增加 `replayed=true`。不能把同一 ID 用于另一个动作、对象或请求内容，否则返回 `CLIENT_REQUEST_CONFLICT`。

## 9. 平台实测结论

服务器本地测试只能证明 Django 契约和状态一致性。以下内容必须在比赛平台形成真实证据：

- 公网地址可访问与平台超时行为；
- 动态路径变量连续传递；
- 平台原生嵌套 JSON 和数组遍历；
- 平台知识库的实际检索命中；
- 平台邮件服务的动态收件人与消息 ID；
- 平台定时节点的真实调度；
- 平台工作流中的主动正常/异常报工。

最终状态是 `READY_FOR_PLATFORM_TEST`，不是 `READY_FOR_PRODUCTION`。
