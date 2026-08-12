# MoldGuard Django 只读查询 API 方案（已废止）

- **状态**：`SUPERSEDED`
- **原版本**：V0.1
- **废止日期**：2026-08-12
- **废止原因**：负责人决定保持原参赛材料中的完整业务闭环，Django 需要支持预警、工单、派工、过程追踪、报工、验收、归档和统计，不再采用只读查询服务器范围。

本文件仅用于记录早期方案决策，不得作为编码、测试、部署或参赛验收依据。

当前唯一权威实施计划：

- [`2026-08-12-moldguard-django-implementation-plan.md`](2026-08-12-moldguard-django-implementation-plan.md)

智能体平台与 Django 的职责说明：

- [`../architecture/2026-08-12-agent-platform-django-relationship.md`](../architecture/2026-08-12-agent-platform-django-relationship.md)

最终决策：

```text
Django 不发送邮件，也不保存完整知识库正文；
但 Django 必须保存预警、工单、最终派工、过程状态、报工、验收、知识快照、邮件结果、模具履历和统计数据。
```
