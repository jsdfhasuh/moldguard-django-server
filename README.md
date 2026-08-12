# MoldGuard Django Server

面向“模具保养智能预警与管理智能体”比赛项目的外部虚拟业务服务器、版本化规则引擎、保养计划与工单状态中心。

## 最终架构

```text
比赛智能体平台
├─ 自然语言交互
├─ Workflow / Agent 编排
├─ MoldGuard 知识库与 RAG
├─ LLM 内容生成
├─ 主管确认
└─ 邮件生成与发送
          │ HTTPS + JSON
          ▼
MoldGuard Django Server
├─ 模具台账、寿命和闲置状态
├─ 版本化规则、审批和冲突治理
├─ 保养预警与保养计划
├─ 计划确认、关闭机会和送模
├─ 工单创建、候选人员和派工
├─ 点检模板、逐项结果和验收
├─ 不合格转修模与周期复位
├─ 知识快照和邮件结果回写
├─ 模具履历、工时和统计
└─ 权限、幂等、事务和审计
```

## 知识库基线

当前对齐：

```text
MoldGuard_模具保养知识库_上传包V0.1.zip
知识条目：353 条
点检标准：22 条
故障与标准工时：78 条
```

知识库当前没有 `INTERNAL_CONFIRMED` 条目，并存在注塑/钣金多版本阈值、缺失字段和待确认转写。参赛使用独立 `DEMO_RULESET_V1` 和知识条目使用白名单；不得把全部 `INTERNAL_SOURCE` 自动当成企业正式规则。

## 系统分工

### 智能体平台负责

- 用户自然语言交互；
- 工作流和 Agent 编排；
- 点检、操作、安全、储放、故障等知识库；
- RAG 检索和来源引用；
- LLM 生成预警、任务、催办、验收和分析说明；
- 展示候选人员并让主管最终确认；
- 组装含点检知识的任务邮件；
- 发送邮件；
- 回写知识快照和邮件结果。

### Django 负责

- 模具数据、模次、位置、吨位、类别、寿命和闲置状态；
- 规则版本、来源、审批、冲突和适用范围；
- 保养提醒、寿命提醒和闲置提醒分离；
- 自动/手动保养计划；
- 计划确认、关闭次数、送模和要求交模时间；
- 工单、候选人员、最终派工和状态机；
- 开工、暂停、恢复、逐项点检、报完工和验收；
- 点检不合格转修模；
- 知识目录版本、知识快照和邮件发送结果；
- 模具履历、周期复位、工时、完成率、超时和人员负荷；
- API Key、操作人权限、幂等、事务和审计。

### Django 不负责

- 自建向量知识库、Embedding 或 Rerank；
- 调用大模型；
- SMTP、邮件模板和邮件发送；
- 企业微信、钉钉或短信发送；
- 独立前端；
- 未经审批自动采用知识库冲突规则；
- 对真实 MES、ERP 或排产系统执行生产写入。

## 当前状态

```text
权威计划：V3.1 FINAL_FROZEN_FOR_COMPETITION
知识库基线：MoldGuard KB V0.1
系统状态：NOT_IMPLEMENTED
下一步：Gate -1 比赛平台最小链路验证
建议实施分支：agent/django-full-workflow-v1
```

## 权威文档

- [完整实施计划 V3.1](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [智能体平台与 Django 关系说明 V1.1](docs/architecture/2026-08-12-agent-platform-django-relationship.md)
- [知识库与 Django 对齐说明](docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md)
- [智能体业务场景说明](docs/business/2026-08-12-moldguard-business-scenarios.md)

早期只读方案仅用于历史对照：

- [已废止的只读查询 API 方案](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

## 技术基线

- Python 3.12
- Django 5.2 LTS
- Django REST Framework 3.16 系列
- PostgreSQL 16
- API 前缀 `/api/v1`
- Docker Compose + Nginx + Gunicorn
- Django 内部端口 `18080`
- 公网 HTTPS `443`
- `X-API-Key` + 操作人权限 + `Idempotency-Key`

## 参赛主闭环

```text
预警扫描
→ 待确认保养计划
→ 主管确认 / 关闭
→ 排产与送模
→ 创建工单
→ 候选匹配与主管派工
→ 知识检索与邮件
→ 开工 / 暂停 / 恢复
→ 逐项点检与报完工
→ 验收完成或转修模
→ 履历更新、周期复位和统计分析
```

业务代码必须在 `agent/django-full-workflow-v1` 分支实施，并按 V3.1 计划中的 Gate 和 Stop Gate 分阶段验收。