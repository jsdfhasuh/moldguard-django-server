# MoldGuard Django Server

面向“模具保养智能预警与管理智能体”比赛项目的外部 Django 查询服务。

## 项目定位

本仓库采用 **Django + Django REST Framework**，只向比赛智能体平台提供稳定、结构化、可解释的业务查询 API。

### Django 负责

- 模具台账查询；
- 保养标准查询；
- 距上次保养模次、周期使用率和预警等级等确定性计算；
- 黄色、红色待保养模具查询；
- 人员、技能、负荷、在岗状态和候选人员查询；
- 知识库检索上下文标签；
- 历史保养记录和基础统计查询；
- Django Admin 演示数据维护；
- OpenAPI、认证、日志、测试和部署。

### 比赛平台或其他外部渠道负责

- 自然语言交互；
- 工作流编排；
- 点检知识库及 RAG；
- LLM 内容生成；
- 最终人员确认；
- 任务内容组装；
- 邮件生成与发送；
- 后续任务交互。

### Django 不负责

- 邮件、SMTP、附件和邮件回写；
- 知识库、Embedding、Rerank 和向量数据库；
- 大模型调用；
- 工单创建、派工写入、开工、暂停、报工和验收；
- 定时任务、Celery 和 Redis；
- 企业微信、钉钉和短信通知；
- 独立前端。

比赛平台对 `/api/v1` 只允许 `GET`、`HEAD` 和 `OPTIONS`。演示数据通过 Django Admin 或 management command 维护。

## 当前状态

当前仓库处于实施计划冻结阶段，尚未开始业务代码实现。

权威实施计划：

- [`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)

早期只读方案草稿保留用于历史对照：

- [`docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md`](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

后续开发必须以权威实施计划为范围基线。

## 技术基线

- Python：3.12
- Django：5.2 LTS
- Django REST Framework：3.16
- API 前缀：`/api/v1`
- 默认数据库：SQLite（比赛演示）
- 生产入口：Nginx HTTPS
- Django 内部端口：`18080`

## 建议后续分支

```text
agent/django-query-api-v1
```

业务代码建议在该分支实施，通过 Draft PR 审阅后再决定是否合并到 `main`。
