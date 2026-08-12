# MoldGuard Django Server

面向“模具保养智能预警与管理智能体”比赛项目的外部虚拟业务服务器。

本仓库采用 **Django + Django REST Framework**，为比赛智能体平台提供模具台账、保养规则、人员匹配、工单流转、过程追踪、统计分析和审计接口。

## 架构决策

- 比赛平台负责：自然语言交互、知识库检索、LLM 生成、定时/手动工作流、邮件发送。
- Django 负责：结构化业务数据、确定性规则、候选人员筛选、工单状态机、统计和审计。
- Django **不负责**：自建知识库、向量检索、SMTP 邮件发送、企业微信/钉钉推送。
- 邮件发送结果可通过可选回调接口记录到 Django，便于追溯。

## 当前状态

当前仓库处于规划阶段，尚未开始业务代码实现。

实施计划见：

- 完整业务版：[`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- 只读查询 API 版：[`docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md`](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

## 建议仓库信息

- 仓库名称：`moldguard-django-server`
- 默认分支：`main`
- 建议可见性：`Private`
- Python：3.12
- Django：5.x
- API 前缀：`/api/v1`
