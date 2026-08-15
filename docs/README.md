# MoldGuard 文档索引

- **当前知识库**：`MOLDGUARD-KB-1.2`
- **完整实施计划**：V5.0
- **阻塞项决议**：V5.1
- **一天后端优先计划**：V1.0
- **当前模型字段**：V3.1
- **当前员工报工契约**：`REPORT-REVIEW-2.1`
- **兼容结构化报工契约**：`REPORT-FORM-1.1`
- **目标实施分支**：`agent/competition-server-v1`
- **测试分支定位**：仅作为设计与风险参考，不复用代码

## 当前权威文档

1. [一天后端优先实施计划V1.0](plans/2026-08-13-moldguard-one-day-backend-first-plan.md)
2. [V5.1阻塞项决议](decisions/2026-08-13-v5.1-blocker-resolution.md)
3. [比赛服务器完整实施计划V5.0](plans/2026-08-12-moldguard-django-implementation-plan.md)
4. [Django模型字段V3.1](models/2026-08-13-django-model-field-review.md)
5. [AI审核报工契约REPORT-REVIEW-2.1](contracts/2026-08-14-ai-reviewed-report-contract.md)
6. [邮件与兼容结构化报工契约REPORT-FORM-1.1](contracts/2026-08-13-mail-report-link-contract.md)
7. [智能体平台与Django关系说明](architecture/2026-08-12-agent-platform-django-relationship.md)
8. [业务场景说明](business/2026-08-12-moldguard-business-scenarios.md)
9. [知识库与Django对齐说明](knowledge/2026-08-12-moldguard-kb-django-alignment.md)
10. [知识库权威确认](decisions/2026-08-13-kb-v1.2-authority-and-mail-report-confirmation.md)
11. [负责人决策状态V1.8](decisions/2026-08-12-owner-decision-checklist.md)
12. [干净重建决策](decisions/2026-08-13-competition-server-clean-build-confirmation.md)

## 比赛平台当前流程

平台实装名称、Flow ID、节点数和连线数以 [比赛平台流程总清单](比赛平台_独立流程/00_比赛必搭流程总清单.md) 为准：

1. [平台能力测试](比赛平台_独立流程/01_流程00_平台能力探测.md)
2. [预警派工与知识随单（手动触发版）](比赛平台_独立流程/02_流程01_预警派工与知识随单.md)
3. [预警派工与知识随单（定时触发版）](比赛平台_独立流程/04_流程01_定时触发版.md)
4. [Django 报工 AI 审核](比赛平台_独立流程/03_流程02_Django报工AI审核.md)

## 最终知识库正文

- [知识库总入口](../knowledge-base/README.md)
- [MOLDGUARD-KB-1.2发布说明](../knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

## 权威顺序

发生业务规则、字段或流程冲突时：

```text
MOLDGUARD-KB-1.2知识正文
→ V5.1阻塞项决议
→ V5.0完整实施计划
→ V3.1模型字段
→ REPORT-REVIEW-2.1员工报工契约
→ REPORT-FORM-1.1兼容结构化接口契约
```

当天的开发顺序和Codex执行方式，以“一天后端优先实施计划V1.0”为准。

## 测试分支与正式实现的关系

测试分支：

```text
agent/platform-capability-probe-v1@2ed0b59
```

只用于参考以下经验：统一响应、Request-ID、幂等、事务、测试组织、Docker/MariaDB部署和冒烟验证。

正式比赛服务器：

```text
从main创建agent/competition-server-v1
不合并测试分支
不cherry-pick测试分支
不复制旧迁移
不沿用platform_probe应用和/probe接口
```

早期只读方案、V3.x修订、快速改造计划、旧决策快照和与V1.2冲突的触发规则文件均已删除，不再作为开发依据。
