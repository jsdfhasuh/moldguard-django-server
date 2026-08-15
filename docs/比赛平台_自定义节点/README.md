# MoldGuard 比赛平台自定义节点

流程 01 当前使用以下四个已经审核并注册的平台组件。下列源码文件只用于版本追溯，不得因为阅读本文而重新粘贴、修改、重命名或注册：

1. `MoldGuard_请求信封_V2.py`
2. `MoldGuard_单输入HTTP_V2.py`
3. `MoldGuard_响应信封_V2.py`
4. `MoldGuard_知识快照信封_V4.py`

画布显示名以当前注册版本为准：请求信封和响应信封显示为 `V3（单输出）`，知识快照信封显示为 `V4（单输出）`，单输入 HTTP 仍显示为 `V2`。V3/V4 是平台组件身份版本；HTTP Data 内的 `moldguard.request.v2` / `moldguard.response.v2` 是后端信封协议版本，两者不要求相同。

原来的 `MoldGuard_知识快照信封_V2.py` 和 `MoldGuard_知识快照信封_V3.py` 保留用于历史流程兼容。当前流程 01 只从已审核组件库选择 V4，不覆盖 V2/V3，也不重新注册 V4。

流程 02 当前只使用以下一个已经审核的自定义组件：

1. `MoldGuard_豆包多模态_V1.py`

流程 02 的 GET、POST、条件路由和中文结果展示全部使用平台原生节点，不连接请求信封 V3、响应信封 V3、知识快照信封 V4 或单输入 HTTP V2；知识快照 V4 只供流程 01 使用。

以下三个旧版组件只为历史流程备份和回退保留。当前四个正式流程均不使用：

1. `MoldGuard_请求适配器.py`
2. `MoldGuard_响应适配器.py`
3. `MoldGuard_知识快照构建器.py`

## 设计边界

- 平台正式知识库名称为 `模具保养知识库`；`MOLDGUARD-KB-1.2` 是目录版本，不是知识库显示名称。
- 请求信封 V3 只生成单个 `Data`，内含 `method/url/json_body/context`，不发送网络请求。
- 流程 01 手动版由平台“当前日期”与“提示词”节点把“开始检查”等指令和北京时间拼成系统运行批次；定时版先用“定时触发器 + 解析器”生成 `定时检查-{timestamp}`，再与北京时间拼接。请求信封本身不读取当前时间。
- `扫描预警` 不接收或发送 `mold_ids`；请求体只带由上游系统运行批次派生的 `client_request_id`，由 Django 扫描全部非禁用模具。
- 同一次运行的自动派工、知识快照和发信请求复用 `context.demo_run_id`，不会分别重新取时间。
- V2 单输入 HTTP 只执行信封中的 HTTP 请求，并原样传递 `context`；它不执行派工、知识或邮件业务规则。
- 响应信封 V3 只解析 HTTP Data，输出一个带业务数据的 `Message`；成功/失败由平台原生“如果-否则”节点路由。
- 知识库检索由平台“我的知识库”节点执行；Django 不访问平台知识库。
- 流程 01 使用“解析器 + 提示词 + 大模型”把真实检索内容整理成只含 `title/content/source` 的严格 JSON。当前画布在大模型后再接一个原生“解析器”的 `原文模式 (Stringify)`，其 `parsed_text` 同时供调试聊天输出和 V4 知识快照信封使用；该解析器只解开 Message 文本，不修复非法 JSON。V4 继续负责兼容运行包装、补齐内部字段并生成单个知识快照请求 `Data`。
- Django 校验、保存并哈希知识包，随后自行渲染和发送邮件。
- 员工只在 Django 邮件链接页面提交文字和图片。平台没有员工报工页面，也不向 Django 提交远程图片 URL。
- Django 保存报工材料后通过 Webhook 唤醒平台；平台只读取审核上下文并回写审核建议。
- 豆包多模态节点只负责通用的提示词、图片和模型调用，不内置 MoldGuard 审核规则。
- 审核规则、中文输出要求和 Django POST JSON 契约全部配置在画布上的原生“提示词”节点。
- 流程 01 的 HTTP 调用由 `MoldGuard 单输入 HTTP V2` 执行；流程 02 的 GET 和 POST 使用平台原生 `JSON HTTP 请求`。
- 流程 02 使用原生“消息转数据”和“解析器”把豆包 `Message.data` 转为 POST JSON；模型失败由原生模板固定回写 `NEEDS_MORE_INFO`。
- 单输出组件不保存 API Key、不访问数据库、不直接发送邮件。

## 豆包多模态 V1

`MoldGuard 豆包多模态 V1（批量图片）` 复用平台
`MODEL_PROVIDERS_DICT["豆包AI"]` 的原生模型字段和全局 `bytedance` API Key。它把模型输入明确构造成：

```python
HumanMessage(
    content=[
        {"type": "text", "text": prompt_text},
        {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
    ]
)
```

节点支持 1 至 10 张图片，输入可以是：

- Django 公网图片 URL；
- 平台文件节点返回的 `file_path` 或二进制 `result`；
- `ChatInput.files` 中的临时文件；
- JPEG、PNG、WebP 本地文件；
- `data:image/*;base64,...` Data URL。

URL 会作为独立 `image_url` 内容块发送；本地文件和二进制会先按文件签名校验，再转换为
Data URL。完全相同的图片会去重，图片顺序保持不变。节点不会把 URL 拼入提示词冒充视觉输入。

默认使用 `严格 JSON` 模式：

- `Message.text` 以 `[DOUBAO_OK]` 或 `[DOUBAO_FAIL]` 开头，供聊天输出中文展示；
- 严格 JSON 中存在合法 `decision` 时，文本还包含 `[DOUBAO_DECISION=...]`，供原生安全门精确路由；
- 成功时 `Message.data` 是模型返回的 JSON 对象，可连接 Django 回写请求；
- 图片、模型或 JSON 失败时 `Message.data={}`，流程 02 的原生条件和模板会安全生成 `NEEDS_MORE_INFO`。

豆包节点不内置 Django 字段白名单。流程 02 的提示词必须要求模型只输出 Django serializer 接受的键，
并把逐图观察和补充要求写入中文 `assessment_summary`。Django 会继续拒绝错误哈希、非法枚举、低置信度和身份字段。

流程 02 的图片来源必须连接 `03_GET报工审核上下文.response`，图片字段路径填写：

```text
body.data.submission.evidence
```

不要把 `05_校验审核上下文.true_result` 接到图片来源。节点 05 的真分支只触发节点 07 的审核提示词；原始图片数组始终从节点 03 的 HTTP 响应 Data 读取。

流程 02 还应把“允许的图片域名”设置为：

```text
moldguard.oracle.19970219.xyz
```

## 报工审核安全门

平台原生“大模型”节点仍然只消费文本。新的豆包多模态节点已在代码层构造图片内容块，但在平台完成
“更换图片像素会改变模型观察或结论”的端到端验证前，流程 02 的原生条件节点 10 只放行：

```text
decision = NEEDS_MORE_INFO
```

模型提前输出 `COMPLETE`、`ABNORMAL`、无效 JSON 或调用失败时，节点 10 的假分支会触发原生模板，固定回写
`NEEDS_MORE_INFO`。至少两张真实图片的像素对照测试通过后，只需把节点 10 改为
`contains [DOUBAO_OK]`；不修改或重新注册 V3 信封。把图片 URL 拼进文字提示词不算视觉验证。

## 响应信封 V3 变量映射（流程 01 与兼容用途）

| 响应类型 | 主变量 | 次变量 | 成功条件 |
|---|---|---|---|
| 扫描预警响应 | `work_order_id` | `alert_id` | `200 + SUCCESS + results[] 中存在 TRIGGERED + MAINTENANCE_TRIGGERED + 非空工单/预警ID` |
| 自动派工响应 | `employee_id`（读取 `assignee_id`） | `work_order_id` | `200 + SUCCESS + 非空 assignee_id` |
| 知识上下文响应 | `search_query` | `knowledge_profile_code` | `200 + SUCCESS + mold_type + profile_code` |
| 知识快照响应 | `code` | 空 | `200 + SUCCESS` |
| 派工邮件响应 | `email_status` | `message_id` | `200 + SUCCESS + SENT + 非空 email_message_id` |
| 报工审核上下文响应 | `submission_id` | `primary_evidence_url` | `200 + SUCCESS + submission_id + 至少一张证据` |
| 报工审核回写响应 | `work_order_status` | `submission_status` | `200 + SUCCESS + FINALIZED 或 NEEDS_MORE_INFO` |
| 定时心跳响应 | `code` | `request_id` | `200 + SUCCESS` |

响应信封 V3 的文本中包含 `[MOLDGUARD_OK]` 或 `[MOLDGUARD_FAIL]`。原生“如果-否则”节点使用 `contains [MOLDGUARD_OK]` 判定，并把同一 Message 从“真/假”端口继续传递。后续请求信封只接受“真”分支中 `success=true` 的业务信封。

## 审核接口

流程 02 的原生 `JSON HTTP 请求` 只调用以下报工审核接口：

```text
GET  /api/v1/report-submissions/{submission_id}/review-context
POST /api/v1/report-submissions/{submission_id}/review
```

不存在平台报工提交操作，也不存在：

```text
POST /api/v1/work-orders/{id}/report-submissions
```

Django Webhook 只含 `submission_id`、`work_order_id` 和 `review_context_url` 等定位字段。员工正文、图片和知识快照必须由平台通过审核上下文接口读取。

## 知识快照输入与内部字段

流程 01 先用“解析器”把 `模具保养知识库` 的 `list[Data]` 合并为文本，再由“提示词”约束平台原生“大模型”一次调用直接生成严格 JSON：

```json
{
  "results": [
    {
      "title": "分型面清洁与润滑",
      "content": "清除分型面异物，检查磨损并补充指定润滑脂。",
      "source": "模具保养知识库"
    }
  ]
}
```

`MoldGuard 知识快照信封 V4（单输出）`兼容上述 JSON `Message`、相同结构的 `Data`、单个
`{"title": ..., "content": ..., "source": ...}` 对象，以及位于 `text`、`page_content`、`data`、`message`、`output`、`result`、`response` 包装键内（最多 4 层）的 JSON。结构化 `Message.data.results` 或三字段对象优先；否则优先读取 `Message.text`，最后读取 `Message.data` 内的受支持包装。平台知识库和大模型都不需要生成 `knowledge_id`。该组件的 `knowledge_results` 端口在画布上仍显示“模块化提取结果”；当前流程 01 先把 `17C.response` 接入原生解析器的原文模式，再把 `17D.parsed_text` 接到这个历史名称端口。

V4 解析失败时，异常会附加安全输入诊断，包括输入类型、文本长度、文本 JSON 形状、`data` 类型、受控顶层键名、`results` 是否存在和三字段存在情况；当顶层 `data` 本身是列表时还会给出列表长度。诊断不打印完整知识正文或任何输入值；未知键名仅显示摘要，因此不会暴露邮箱、令牌、Cookie、Authorization 或会话标识的值。

节点会在请求 Django 前确定性补齐内部契约字段：

```text
knowledge_id   = KB-SHA256-<title/content/source 的 SHA-256>
item           = title
knowledge_type = MAINTENANCE_GUIDANCE
required       = true
```

相同的 `title/content/source` 始终生成相同 ID，并按该 ID 去重。`knowledge_text` 只保留标题、正文和来源，不显示内部 ID。`title`、`content`、`source` 任一为空时节点会明确报错；受控备用 JSON 也只需这三个字段。

平台将构建结果 POST 到 `/api/v1/work-orders/{work_order_id}/knowledge`。不得改成 Django 主动检索。大模型只能从真实检索内容中提炼可执行的保养与点检步骤，不得补写不存在的要求或来源，也不得把模次阈值、时间周期、规则编号、建单条件或周期复位逻辑写入知识快照。
