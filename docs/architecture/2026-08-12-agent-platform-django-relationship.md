# 智能体平台与 Django 测试服务器关系说明

- **版本**：V3.1
- **日期**：2026-08-13
- **知识库基线**：MOLDGUARD-KB-1.2

> 智能体平台负责对话、工作流、知识检索和 AI 审核建议；Django 负责触发计算、工单状态、SMTP 派工邮件、员工图片报工和最终裁决。

## 1. 关系图

```text
智能体平台
├─ 对话与工作流
├─ 知识库/RAG
├─ 拉取Django报工材料并生成审核建议
└─ 回写知识包、调用send-email与回写审核建议
          │ HTTP + JSON
          ▼
Django测试服务器
├─ 模具与触发规则
├─ 自动建单和派工
├─ 渲染并通过SMTP发送派工邮件
├─ report_url、报工网页与图片存储
├─ 报工Webhook、审核上下文与最终裁决
├─ 正常/异常状态机
├─ 周期复位和履历
└─ 工时统计
```

## 2. 核心时序

```text
Django扫描并自动建单
→ 平台调用Django确定性自动派工
→ Django返回被派工人员和report_url
→ Django返回知识检索上下文
→ 平台检索并组装本工单知识包
→ 平台回写知识包并调用Django send-email
→ Django发送纯文本和HTML派工邮件
→ 人员点击 report_url
→ Django展示同一知识快照
→ 人员上传完成说明和现场图片
→ Django保存材料并Webhook唤醒平台
→ 平台拉取锁定知识包、文字和图片，回写AI建议
→ Django完成、进入异常闭环或要求补充材料
```

## 3. 权威边界

Django权威：模具字段、规则ID、阈值、工单状态、周期基准、报工结果和工时。

知识库权威：触发规则解释、保养步骤、点检判定、安全要求、故障工时候选和直接报工规则。

平台负责知识检索、知识包组装、工作流编排和 AI 审核建议，并通过 `POST /work-orders/{id}/knowledge` 把实际检索结果提交给 Django。Django 校验、保存、计算哈希和使用该知识包，不访问平台知识库，也不生成知识正文。平台不得注入或改写 Django 邮件的收件人、主题、正文、链接和状态，也不得直接写工单状态、周期或履历。

## 4. 邮件链接职责

- Django生成 `report_url=/report/{work_order_id}`；
- Django从工单和知识快照渲染邮件，并通过SMTP发往 `work_order.assignee.email`；
- 平台只能调用 `send-email`，不能提供收件人、主题、正文、HTML或发件人；
- `email-context` 只供预览和调试，外部没有 `email-result` 写入口；
- 报工页面由Django模板渲染；
- 员工只在 Django 页面提交文字和真实图片，不存在平台页面报工入口；
- Django 保存材料后通过 Webhook 唤醒平台，平台再读取审核上下文；
- 无登录、无主管角色；
- AI 只给建议，Django 最终决定完成、异常或要求补充；
- 未验证图片能进入多模态模型时，平台只能回写 `NEEDS_MORE_INFO`。
