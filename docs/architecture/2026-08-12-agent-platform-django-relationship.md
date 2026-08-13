# 智能体平台与 Django 测试服务器关系说明

- **版本**：V3.0
- **日期**：2026-08-13
- **知识库基线**：MOLDGUARD-KB-1.2

> 智能体平台负责对话、工作流和知识检索；Django负责触发计算、工单状态、SMTP派工邮件和邮件链接报工。

## 1. 关系图

```text
智能体平台
├─ 对话与工作流
├─ 知识库/RAG
└─ 回写本次知识包并调用send-email
          │ HTTP + JSON
          ▼
Django测试服务器
├─ 模具与触发规则
├─ 自动建单和派工
├─ 渲染并通过SMTP发送派工邮件
├─ report_url与报工网页
├─ 正常/异常状态机
├─ 周期复位和履历
└─ 工时统计
```

## 2. 核心时序

```text
Django扫描并自动建单
→ 平台查询候选并选择人员
→ Django assign 返回邮箱和 report_url
→ 平台检索一份点检知识包
→ 平台回写知识包并调用Django send-email
→ Django发送纯文本和HTML派工邮件
→ 人员点击 report_url
→ Django展示同一知识快照
→ 人员提交正常或异常报工
→ Django完成或进入异常闭环
```

## 3. 权威边界

Django权威：模具字段、规则ID、阈值、工单状态、周期基准、报工结果和工时。

知识库权威：触发规则解释、保养步骤、点检判定、安全要求、故障工时候选和直接报工规则。

平台负责知识检索和工作流编排，但不得注入或改写Django邮件的收件人、主题、正文、链接和状态。

## 4. 邮件链接职责

- Django生成 `report_url=/report/{work_order_id}`；
- Django从工单和知识快照渲染邮件，并通过SMTP发往 `work_order.assignee.email`；
- 平台只能调用 `send-email`，不能提供收件人、主题、正文、HTML或发件人；
- `email-context` 只供预览和调试，外部没有 `email-result` 写入口；
- 报工页面由Django模板渲染；
- 无登录、无主管角色；
- 正常报工直接完成，异常报工进入异常流程。
