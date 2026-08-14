# MoldGuard AI 审核报工契约

- **版本**：`REPORT-REVIEW-2.1`
- **日期**：2026-08-14
- **知识库**：`MOLDGUARD-KB-1.2`
- **身份模式**：无登录；Django 使用工单 `assignee` 作为报工人员
- **员工入口**：仅 Django 邮件链接页面

## 1. 权责边界

```text
员工在 Django 页面提交文字和图片
→ Django 保存 ReportSubmission(PENDING_REVIEW)
→ Django Webhook 唤醒平台
→ 平台拉取锁定知识包、员工文字和全部图片
→ AI 回写 COMPLETE / ABNORMAL / NEEDS_MORE_INFO 建议
→ Django 校验并最终裁决
```

- 平台负责工作流、知识应用和 AI 建议。
- Django 是人员、工单状态、知识快照、告警、履历和周期复位的唯一权威。
- AI 不直接写 `WorkOrder.status`。
- 员工、平台和 AI 均不得提交或覆盖 `employee_id`、`assignee_id` 或 `work_order_id`。
- 不提供平台页面报工入口，也不提供 `POST /api/v1/work-orders/{id}/report-submissions`。
- 现有 `POST /api/v1/work-orders/{id}/report` 仅作为兼容的结构化终结接口保留；员工报工页面不直接调用它。

## 2. Django 页面提交

员工打开邮件中的地址：

```http
GET /report/{work_order_id}
```

页面展示工单、模具、被派工人、知识版本、知识哈希、点检知识和安全要求。页面不提供员工编号输入框。

员工提交：

```http
POST /report/{work_order_id}
Content-Type: multipart/form-data
```

| 字段 | 规则 |
|---|---|
| `submission_id` | 页面生成的全局幂等 ID |
| `report_form_schema_version` | 必须为 `REPORT-FORM-1.1` |
| `knowledge_package_hash` | 必须等于工单当前知识包哈希 |
| `report_text` | 1 至 2000 字符 |
| `images` | 1 至 10 张；JPEG、PNG 或 WebP；默认单张不超过 8 MiB |
| `actual_work_hours` | `>0` 且 `<=999.99` |
| `parts_replaced_text` | 可选；每行一个，最多 50 项 |

Django 根据文件签名识别图片类型，不信任扩展名或客户端 `Content-Type`。图片保存到默认文件存储；比赛容器持久化挂载 `/app/media`。

提交成功返回 HTTP 202 结果页。此时工单仍保持 `ASSIGNED`、`IN_PROGRESS` 或 `PAUSED`，不会创建最终履历、关闭告警或复位周期。

同一工单同时只允许一个 `PENDING_REVIEW` 提交。AI 回写 `NEEDS_MORE_INFO` 后，员工可在原链接看到补充原因并创建一批新的文字和图片；旧提交不能再改判。

## 3. Django 唤醒平台

Django 创建提交后调用：

```text
MOLDGUARD_REPORT_REVIEW_WEBHOOK_URL
```

Webhook 只发送定位字段：

```json
{
  "event": "REPORT_SUBMISSION_READY",
  "submission_id": "RPT-20260814-ABC123",
  "work_order_id": "WO-20260814-001",
  "review_context_url": "https://moldguard.example/api/v1/report-submissions/RPT-20260814-ABC123/review-context",
  "client_request_id": "review-dispatch-RPT-20260814-ABC123"
}
```

Webhook 不发送员工正文、图片字节、邮箱或凭据。Webhook 返回 2xx 只表示平台已被唤醒，不表示审核通过。

送达状态：

```text
PENDING / SENDING / DELIVERED / FAILED / NOT_CONFIGURED
```

Webhook 失败不删除材料、不改变工单状态。原 HTML 请求精确重放时可重试失败的唤醒。

## 4. 平台拉取审核上下文

```http
GET /api/v1/report-submissions/{submission_id}/review-context
```

响应 `data` 包含：

```text
submission.submission_id/status/report_text/actual_work_hours
submission.parts_replaced/source_fault_id
submission.evidence[].evidence_id/url/content_type/byte_size/sha256/original_name
work_order.work_order_id/status/type/mold/trigger/assignee
knowledge_package
knowledge_snapshot_version
knowledge_package_hash
review_callback_url
review_contract
```

Django 图片地址：

```http
GET /api/v1/report-submissions/{submission_id}/evidence/{evidence_id}
```

平台必须读取员工文字、全部图片和锁定知识包。只看文字、文件名、URL 字符串或 HTTP 200 不能形成 `COMPLETE` 或 `ABNORMAL` 建议。

## 5. AI 审核回写

```http
POST /api/v1/report-submissions/{submission_id}/review
Content-Type: application/json
```

完成建议示例：

```json
{
  "client_request_id": "review-RPT-001-001",
  "decision": "COMPLETE",
  "assessment_summary": "文字和图片能够证明全部必检项已完成",
  "confidence": "0.9500",
  "knowledge_package_hash": "abc123...",
  "inspection_results": [
    {
      "knowledge_id": "CHK-INJ-001",
      "result": "PASS",
      "not_applicable_reason": "",
      "abnormal_note": ""
    }
  ],
  "abnormal_items": [],
  "abnormal_next_action": null,
  "reason_codes": ["ALL_REQUIRED_ITEMS_CONFIRMED"],
  "knowledge_sources": ["MOLDGUARD-KB-1.2"],
  "review_model": "verified-vision-model"
}
```

| `decision` | Django 行为 |
|---|---|
| `COMPLETE` | 复用 NORMAL 校验；通过后完成工单、创建履历并按矩阵复位周期 |
| `ABNORMAL` | 复用 ABNORMAL 校验；进入 `ABNORMAL_REPORTED`，不结单、不复位 |
| `NEEDS_MORE_INFO` | 关闭本批审核，工单状态不变，员工必须提交一批新材料 |

`COMPLETE` 或 `ABNORMAL` 的置信度必须达到 `MOLDGUARD_AI_REVIEW_MIN_CONFIDENCE`，默认 `0.7500`。达到阈值仍不代表通过；Django 还会校验全部必检项、FAIL/异常组合、知识哈希和当前工单状态。

## 6. 幂等与并发

- 所有写请求必须携带全局唯一 `client_request_id`。
- 同一 ID 和同一请求精确重放，返回 `data.replayed=true`。
- 同一 ID 对应不同请求返回 `CLIENT_REQUEST_CONFLICT`。
- Django 锁定工单后检查是否已有 `PENDING_REVIEW` 提交。
- `FINALIZED` 提交不能再次审核。
- `NEEDS_MORE_INFO` 提交不能用新审核请求改判；必须由员工创建新提交。

## 7. 关键错误码

| HTTP | 错误码 | 含义 |
|---:|---|---|
| 400 | `INVALID_REPORT_IMAGE` | 图片为空、格式不支持或缺少图片 |
| 400 | `REPORT_IMAGE_TOO_LARGE` | 单张图片超过限制 |
| 404 | `REPORT_SUBMISSION_NOT_FOUND` | 报工提交不存在 |
| 404 | `REPORT_EVIDENCE_NOT_FOUND` | 图片证据不存在 |
| 409 | `REPORT_REVIEW_PENDING` | 工单已有待审核提交 |
| 409 | `REPORT_REVIEW_ALREADY_FINALIZED` | 提交已经完成 Django 裁决 |
| 409 | `REPORT_REVIEW_NEEDS_NEW_SUBMISSION` | 旧材料已要求补充，必须创建新提交 |
| 409 | `AI_REVIEW_CONFIDENCE_TOO_LOW` | AI 置信度低于自动裁决阈值 |
| 409 | `KNOWLEDGE_PACKAGE_HASH_MISMATCH` | 提交、审核或工单知识哈希不一致 |

## 8. 平台视觉能力硬门槛

当前已核验的“小天平台大模型”节点把输入作为纯文本构造消息，不消费图片文件。当前平台请求适配器因此只允许回写 `NEEDS_MORE_INFO`。

以下任一能力完成真实图片验证后，才能启用 `COMPLETE` 或 `ABNORMAL`：

1. 能读取图片二进制或图片 URL 内容的多模态模型节点。
2. 已验证的文件到多模态消息桥接组件。
3. 已验证的外部视觉审核 API，并由平台安全调用。

验证必须证明模型读取了实际像素，例如更换图片内容会改变审核结论。仅把图片 URL 拼进提示词不算验证。

## 9. 部署配置

```text
MOLDGUARD_REPORT_REVIEW_WEBHOOK_URL
MOLDGUARD_REPORT_REVIEW_WEBHOOK_TIMEOUT=10
MOLDGUARD_REPORT_MAX_IMAGES=10
MOLDGUARD_REPORT_IMAGE_MAX_BYTES=8388608
DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE=100663296
MOLDGUARD_AI_REVIEW_MIN_CONFIDENCE=0.7500
DJANGO_MEDIA_ROOT=/app/media
```

反向代理的请求体上限必须覆盖允许的总图片大小；当前比赛 Nginx 模板使用 `client_max_body_size 96m`。
