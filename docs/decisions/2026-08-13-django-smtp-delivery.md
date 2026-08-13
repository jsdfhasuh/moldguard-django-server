# MoldGuard Django SMTP 派工邮件决议

- **状态**：`OWNER_ACCEPTED_IMPLEMENTATION_BASELINE`
- **日期**：2026-08-13
- **适用分支**：`agent/competition-server-v1`
- **覆盖范围**：所有把邮件生成、发送或发送结果回写归属于比赛智能体平台的旧设计

比赛智能体平台不支持发送邮件。正式比赛服务器由 Django 通过 SMTP 发送派工邮件。

## 1. 最终流程

```text
平台回写知识包
→ POST /api/v1/work-orders/{id}/send-email
→ Django渲染text/plain与text/html
→ Django通过SMTP发送到work_order.assignee.email
→ Django保存Message-ID、发送时间、结果和事件
→ 被派工人员打开邮件中的report_url报工
```

`GET /email-context` 仅供预览和调试。`POST /email-result` 不再是公开路由，调用方不能声明或伪造 `SENT`。

## 2. 外部副作用幂等

SMTP 发送不得放进现有 `replay_or_execute` 长事务：

1. 短事务创建 `ClientRequestRecord`，状态为 `102 / {"state":"IN_PROGRESS"}`，并把工单置为 `SENDING`；
2. 事务提交后，生成并持久化 Message-ID，再调用 SMTP；
3. 短事务同时保存工单结果、`WorkOrderEvent` 和最终幂等响应；
4. 同一 `client_request_id` 重放最终结果，不再次发送；
5. 正在发送时返回 `EMAIL_SEND_IN_PROGRESS`；
6. 超时、断连或进程中断导致结果不可确认时，保存 `OUTCOME_UNKNOWN`，返回 `EMAIL_SEND_OUTCOME_UNKNOWN`，禁止自动重发。

明确失败为 `FAILED`，可使用新的 `client_request_id` 重试。成功为 `SENT`，知识包立即锁定；新的发送请求返回 `EMAIL_ALREADY_SENT`。

## 3. 安全边界

- 请求只接受 `client_request_id`；
- 收件人固定为 `work_order.assignee.email`；
- 主题、正文、HTML和发件人均由服务器配置和模板产生；
- SMTP密码只来自运行环境，不写入Git、日志或API；
- HTML模板使用Django默认自动转义；
- 比赛部署必须显式使用 `django.core.mail.backends.smtp.EmailBackend`；
- 未配置真实 SMTP 时不得声称邮件已送达。

## 4. 配置

```text
EMAIL_BACKEND
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
EMAIL_USE_TLS
EMAIL_USE_SSL
EMAIL_TIMEOUT
DEFAULT_FROM_EMAIL
EMAIL_MESSAGE_ID_DOMAIN
```

`EMAIL_USE_TLS` 与 `EMAIL_USE_SSL` 互斥。开发和测试默认使用 locmem；比赛 Compose 设置 `MOLDGUARD_REQUIRE_SMTP=true` 进行启动期校验。
