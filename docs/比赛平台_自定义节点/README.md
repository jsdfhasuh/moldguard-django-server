# MoldGuard 比赛平台自定义节点

流程 01 和流程 02 使用 V2 单输出组件。在小天 AI 平台的“自定义组件”中依次粘贴、验证并保存：

1. `MoldGuard_请求信封_V2.py`
2. `MoldGuard_单输入HTTP_V2.py`
3. `MoldGuard_响应信封_V2.py`
4. `MoldGuard_知识快照信封_V2.py`

以下三个旧版组件为已存在的流程 04 和回退保留，不再用于新建的流程 01/02：

1. `MoldGuard_请求适配器.py`
2. `MoldGuard_响应适配器.py`
3. `MoldGuard_知识快照构建器.py`

## 设计边界

- 平台正式知识库名称为 `模具保养知识库`；`MOLDGUARD-KB-1.2` 是目录版本，不是知识库显示名称。
- V2 请求信封只生成单个 `Data`，内含 `method/url/json_body/context`，不发送网络请求。
- V2 单输入 HTTP 只执行信封中的 HTTP 请求，并原样传递 `context`；它不执行派工、知识或邮件业务规则。
- V2 响应信封只解析 HTTP Data，输出一个带业务数据的 `Message`；成功/失败由平台原生“如果-否则”节点路由。
- 知识库检索由平台“我的知识库”节点执行；Django 不访问平台知识库。
- V2 知识快照信封把平台检索结果转换为受控 `items[]`，并生成单个知识快照请求 `Data`。
- Django 校验、保存并哈希知识包，随后自行渲染和发送邮件。
- 员工只在 Django 邮件链接页面提交文字和图片。平台没有员工报工页面，也不向 Django 提交远程图片 URL。
- Django 保存报工材料后通过 Webhook 唤醒平台；平台只读取审核上下文并回写审核建议。
- 流程 01/02 的 HTTP 调用由画布上独立的 `MoldGuard 单输入 HTTP V2` 执行，不隐藏在业务信封组件内。
- V2 组件不保存 API Key、不访问数据库、不直接发送邮件。

## 报工审核安全门

当前已核验的“大模型”节点只消费文本，不会读取聊天输入的图片文件。因此请求适配器中的
`MULTIMODAL_REVIEW_VERIFIED` 固定为 `False`，审核回写只接受：

```text
decision = NEEDS_MORE_INFO
```

当前配置若尝试回写 `COMPLETE` 或 `ABNORMAL`，组件会直接报错，不会调用 Django。只有在真实验证某个多模态节点或文件桥接能读取审核上下文中的全部图片后，才允许修改该门禁并启用完整审核分支。把图片 URL 拼进文字提示词不算视觉验证。

## V2 响应信封变量映射

| 响应类型 | 主变量 | 次变量 | 成功条件 |
|---|---|---|---|
| 扫描预警响应 | `work_order_id` | `alert_id` | `200 + SUCCESS + TRIGGERED + MAINTENANCE_TRIGGERED + 非空工单/预警ID` |
| 自动派工响应 | `employee_id`（读取 `assignee_id`） | `work_order_id` | `200 + SUCCESS + 非空 assignee_id` |
| 知识上下文响应 | `search_query` | `knowledge_profile_code` | `200 + SUCCESS + mold_type + profile_code` |
| 知识快照响应 | `code` | 空 | `200 + SUCCESS` |
| 派工邮件响应 | `email_status` | `message_id` | `200 + SUCCESS + SENT + 非空 email_message_id` |
| 报工审核上下文响应 | `submission_id` | `primary_evidence_url` | `200 + SUCCESS + submission_id + 至少一张证据` |
| 报工审核回写响应 | `work_order_status` | `submission_status` | `200 + SUCCESS + FINALIZED 或 NEEDS_MORE_INFO` |
| 定时心跳响应 | `code` | `request_id` | `200 + SUCCESS` |

V2 响应信封的文本中包含 `[MOLDGUARD_OK]` 或 `[MOLDGUARD_FAIL]`。原生“如果-否则”节点使用 `contains [MOLDGUARD_OK]` 判定，并把同一 Message 从“真/假”端口继续传递。后续请求信封只接受“真”分支中 `success=true` 的业务信封。

## 审核接口

平台只调用以下报工审核接口：

```text
GET  /api/v1/report-submissions/{submission_id}/review-context
POST /api/v1/report-submissions/{submission_id}/review
```

不存在平台报工提交操作，也不存在：

```text
POST /api/v1/work-orders/{id}/report-submissions
```

Django Webhook 只含 `submission_id`、`work_order_id` 和 `review_context_url` 等定位字段。员工正文、图片和知识快照必须由平台通过审核上下文接口读取。

## 知识快照严格规则

检索结果只有同时具备以下字段才会进入 `items[]`：

```text
knowledge_id
title
item
knowledge_type
content
source
required
```

`required` 必须是真正的布尔值。节点不会根据正文猜测缺失字段。若平台知识库返回的 metadata 不完整，可在“受控备用知识项 JSON”中显式配置经过确认的知识项。

平台将构建结果 POST 到 `/api/v1/work-orders/{work_order_id}/knowledge`。不得改成 Django 主动检索，也不得把 AI 生成文本作为知识包提交。
