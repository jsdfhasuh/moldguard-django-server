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
├─ 模具台账、开发吨位、模次和位置
├─ 版本化规则、审批和冲突治理
├─ 保养预警、时间提醒与保养计划
├─ 计划确认、关闭机会和送模
├─ 工单创建、候选人员和派工
├─ 点检模板、逐项结果和验收
├─ 不合格转修模与周期复位
├─ 知识快照和邮件结果回写
├─ 模具履历、工时和统计
└─ 权限、幂等、事务和审计
```

## 已确认的当前自动保养触发规则

状态：`INTERNAL_CONFIRMED`

当前实际业务对钣金和注塑模具**不区分一级、二级、三级保养**。自动保养提醒统一按照模具开发吨位执行：

| 开发吨位 | 自动提醒周期 |
|---:|---:|
| `<1000T` | 每累计生产50,000模次 |
| `>=1000T` | 每累计生产30,000模次 |

以下内容只作为历史标准或保养作业知识参考，不参与当前自动提醒、自动计划和自动派单：

```text
精密/普通/小型模具的3万、5万、10万模次
一保、二保、三保相关模次
零件级历史周期
外部A/B/C参考
```

## 已确认的每2个月提醒

状态：`INTERNAL_CONFIRMED`

当前按D03原业务语境，注塑模具继续保留每2个月提醒：

```text
cycle_baseline_time + 2 calendar months
→ 生成提醒记录
→ 智能体平台发送提醒
→ 不自动创建保养计划
→ 不自动创建工单
→ 不自动派工
```

该时间提醒不能覆盖或替代3万/5万吨位模次触发规则。

本次确认未扩大到钣金模具；后续如需启用，必须另行确认。

## 已确认的周期复位规则

状态：`INTERNAL_CONFIRMED`

以下事件均允许复位保养周期：

```text
保养完成
修模完成
换镶件完成
有效历史记录导入
```

复位同时更新：

```text
cycle_baseline_count
cycle_baseline_time
cycle_version
last_reset_type
last_reset_event_id
```

下一次3万/5万模次触发和注塑每2个月提醒均从新基线重新计算。

历史记录导入使用记录中的实际业务发生模次和时间，不使用上传时间；旧于当前基线的记录默认只归档，不自动倒退周期。

## 权威确认记录

- [钣金与注塑模具自动保养触发规则确认](docs/decisions/2026-08-13-maintenance-trigger-rule-confirmation.md)
- [每2个月提醒与周期复位规则确认](docs/decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md)
- [V3.2自动保养触发规则修订](docs/plans/2026-08-13-moldguard-django-v3.2-trigger-rule-amendment.md)
- [V3.3提醒与周期复位修订](docs/plans/2026-08-13-moldguard-django-v3.3-reminder-reset-amendment.md)

## 知识库基线

当前对齐：

```text
MoldGuard_模具保养知识库_上传包V0.1.zip
知识条目：353条
点检标准：22条
故障与标准工时：78条
```

知识包V0.1原有条目仍保留原始权威标签。当前正式吨位规则、时间提醒和周期复位规则通过独立业务确认记录建立，不静默修改历史知识来源。

知识库中的冲突阈值和保养等级资料可以用于检索、解释、点检和作业指导，但不得覆盖Django返回的当前规则。

## 系统分工

### 智能体平台负责

- 用户自然语言交互；
- 工作流和Agent编排；
- 点检、操作、安全、储放、故障等知识库；
- RAG检索和来源引用；
- LLM生成预警、时间提醒、任务、催办、验收和分析说明；
- 展示候选人员并让主管最终确认；
- 组装含点检知识的任务邮件；
- 发送邮件和提醒；
- 回写知识快照、邮件结果和提醒通知结果。

### Django负责

- 模具数据、模次、开发吨位、位置、寿命和闲置状态；
- 当前正式吨位规则及其他规则的版本、来源、审批、冲突和适用范围；
- 吨位模次触发、注塑2个月提醒、寿命提醒和闲置提醒分离；
- `MaintenanceCycle`、周期版本和四类复位事件；
- 自动/手动保养计划；
- 计划确认、关闭次数、送模和要求交模时间；
- 工单、候选人员、最终派工和状态机；
- 开工、暂停、恢复、逐项点检、报完工和验收；
- 点检不合格转修模；
- 知识目录版本、知识快照和邮件发送结果；
- 模具履历、工时、完成率、超时和人员负荷；
- API Key、操作人权限、幂等、事务和审计。

### Django不负责

- 自建向量知识库、Embedding或Rerank；
- 调用大模型；
- SMTP、邮件模板和邮件发送；
- 企业微信、钉钉或短信发送；
- 独立前端；
- 让知识库历史阈值覆盖当前正式吨位规则；
- 将2个月提醒自动升级成计划或派工；
- 对真实MES、ERP或排产系统执行生产写入。

## 当前状态

```text
完整技术计划：V3.1 TECHNICAL_BASELINE
触发规则修订：V3.2 NORMATIVE_AMENDMENT
提醒与复位修订：V3.3 NORMATIVE_AMENDMENT
已确认规则：
  MAINT_TRIGGER_TONNAGE_V1 / INTERNAL_CONFIRMED
  TWO_MONTH_REMINDER_V1 / INTERNAL_CONFIRMED
  MAINTENANCE_CYCLE_RESET_V1 / INTERNAL_CONFIRMED
剩余负责人决策：OWNER_DECISIONS_REQUIRED
知识库基线：MoldGuard KB V0.1
系统状态：NOT_IMPLEMENTED
下一步：确认D07、D09—D18 + Gate -1平台验证
建议实施分支：agent/django-full-workflow-v1
```

以下内容已可进入Phase 0合同、模型和测试设计：

```text
development_tonnage字段
3万/5万吨位触发
当前不区分保养等级
注塑每2个月仅提醒
MaintenanceCycle
CycleResetEvent
保养/修模/换镶件/历史导入复位
新旧周期和提醒失效规则
```

其余未确认业务不得由开发人员或LLM自行补齐。

## 权威文档

- [负责人决策清单V1.2](docs/decisions/2026-08-13-owner-decision-checklist-v1.2.md)
- [自动保养触发规则确认记录](docs/decisions/2026-08-13-maintenance-trigger-rule-confirmation.md)
- [每2个月提醒与周期复位确认记录](docs/decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md)
- [V3.2触发规则修订](docs/plans/2026-08-13-moldguard-django-v3.2-trigger-rule-amendment.md)
- [V3.3提醒与周期复位修订](docs/plans/2026-08-13-moldguard-django-v3.3-reminder-reset-amendment.md)
- [完整实施计划V3.1](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [智能体平台与Django关系说明V1.1](docs/architecture/2026-08-12-agent-platform-django-relationship.md)
- [知识库与Django对齐说明](docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md)
- [智能体业务场景说明](docs/business/2026-08-12-moldguard-business-scenarios.md)

历史文档：

- [负责人决策清单V1.1](docs/decisions/2026-08-13-owner-decision-checklist-v1.1.md)
- [负责人决策清单V1.0](docs/decisions/2026-08-12-owner-decision-checklist.md)
- [已废止的只读查询API方案](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

## 技术基线

- Python 3.12
- Django 5.2 LTS
- Django REST Framework 3.16系列
- PostgreSQL 16
- API前缀 `/api/v1`
- Docker Compose + Nginx + Gunicorn
- Django内部端口 `18080`
- 公网HTTPS `443`
- `X-API-Key` + 操作人权限 + `Idempotency-Key`

## 参赛主闭环

```text
按开发吨位和周期模次扫描预警
→ 注塑2个月提醒（仅通知，独立支线）
→ 待确认保养计划
→ 主管确认 / 关闭
→ 排产与送模
→ 创建工单
→ 候选匹配与主管派工
→ 知识检索与邮件
→ 开工 / 暂停 / 恢复
→ 逐项点检与报完工
→ 验收完成或转修模
→ 保养/修模/换镶件/历史记录触发周期复位
→ 履历更新和统计分析
```

业务代码必须在 `agent/django-full-workflow-v1` 分支实施，并按V3.1、V3.2和V3.3共同组成的当前基线分阶段验收。