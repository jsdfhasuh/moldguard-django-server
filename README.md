# MoldGuard Django Server

面向“模具保养智能预警与管理智能体”比赛项目的外部 Django 查询服务。

## 项目定位

本仓库采用 **Django + Django REST Framework**，只向比赛智能体平台提供稳定、结构化、可解释的模具业务查询 API。

最终架构：

```text
比赛智能体平台
├─ 自然语言交互
├─ 工作流编排
├─ 点检知识库与 RAG
├─ LLM 内容生成
├─ 最终人员确认
└─ 邮件生成与发送
          │ HTTPS + JSON
          ▼
MoldGuard Django Query API
├─ 模具台账查询
├─ 保养标准查询
├─ 保养状态和预警计算
├─ 待保养模具查询
├─ 候选人员和邮箱查询
├─ 知识库检索上下文
├─ 聚合任务上下文
├─ 历史保养记录
└─ 基础统计
```

## Django 负责

- 模具台账查询；
- 保养标准查询；
- 距上次保养模次、周期使用率、剩余模次和预警等级等确定性计算；
- 黄色、红色待保养模具查询；
- 人员、技能、负荷、在岗状态、候选资格和邮箱查询；
- 知识库检索上下文标签；
- 平台生成任务邮件所需的聚合任务上下文；
- 历史保养记录和基础统计查询；
- Django Admin 演示数据维护；
- OpenAPI、认证、日志、测试和部署。

## 比赛平台或其他外部渠道负责

- 自然语言交互；
- 工作流编排；
- 点检知识库和 RAG；
- LLM 内容生成；
- 最终人员确认；
- 任务内容组装；
- 邮件生成与发送；
- 后续任务交互。

## Django 不负责

- 邮件、SMTP、附件和邮件回写；
- 知识库、Embedding、Rerank 和向量数据库；
- 大模型调用；
- 工单创建和最终派工写入；
- 开工、暂停、报工和验收；
- 定时任务、Celery 和 Redis；
- 企业微信、钉钉和短信通知；
- 独立前端。

比赛平台对 `/api/v1` 只允许：

```text
GET
HEAD
OPTIONS
```

演示数据通过 Django Admin 或 management command 维护。

## 当前状态

```text
计划状态：FINAL_FROZEN
计划版本：V2.0
业务代码：尚未开始
下一阶段：Phase 0 合同和演示规则冻结
```

## 权威实施计划

后续开发、测试、部署和比赛验收必须以以下文件为唯一范围基线：

- [`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)

早期草稿仅用于历史对照，不再作为开发依据：

- [`docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md`](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

## 技术基线

- Python：3.12
- Django：5.2 LTS 最新安全补丁版本
- Django REST Framework：3.16 系列
- API 前缀：`/api/v1`
- 数据库：SQLite（参赛演示）
- 部署：Docker Compose + Nginx + Gunicorn
- Django 内部端口：`18080`
- 公网入口：HTTPS `443`
- 认证：`X-API-Key`

## 最终核心接口

```text
GET /api/v1/health
GET /api/v1/meta

GET /api/v1/molds
GET /api/v1/molds/{mold_id}
GET /api/v1/molds/{mold_id}/maintenance-status
GET /api/v1/molds/due
GET /api/v1/molds/{mold_id}/knowledge-context
GET /api/v1/molds/{mold_id}/task-context

GET /api/v1/maintenance-standards
GET /api/v1/maintenance-standards/{standard_id}
GET /api/v1/maintenance-standards/match

GET /api/v1/staff
GET /api/v1/staff/{employee_id}
GET /api/v1/staff/available

GET /api/v1/maintenance-records
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/mold-history
```

## 建议实施分支

```text
agent/django-query-api-v1
```

业务代码应在该分支实施，通过 Draft PR 和计划中的 Stop Gate 审阅后，再决定是否合并到 `main`。
