# MoldGuard 文档索引

- **当前知识库**：`MOLDGUARD-KB-1.2`
- **完整实施计划**：V5.0
- **当前模型字段**：V3.0
- **当前报工表单**：`REPORT-FORM-1.0`
- **目标实施分支**：`agent/competition-server-v1`
- **测试分支定位**：仅作为设计与风险参考，不复用代码

## 当前权威文档

1. [比赛服务器完整实施计划V5.0](plans/2026-08-12-moldguard-django-implementation-plan.md)
2. [Django模型字段V3.0](models/2026-08-13-django-model-field-review.md)
3. [邮件报工链接契约](contracts/2026-08-13-mail-report-link-contract.md)
4. [智能体平台与Django关系说明](architecture/2026-08-12-agent-platform-django-relationship.md)
5. [业务场景说明](business/2026-08-12-moldguard-business-scenarios.md)
6. [知识库与Django对齐说明](knowledge/2026-08-12-moldguard-kb-django-alignment.md)
7. [知识库权威确认](decisions/2026-08-13-kb-v1.2-authority-and-mail-report-confirmation.md)
8. [负责人决策状态](decisions/2026-08-12-owner-decision-checklist.md)
9. [干净重建决策](decisions/2026-08-13-competition-server-clean-build-confirmation.md)

## 最终知识库正文

- [知识库总入口](../knowledge-base/README.md)
- [MOLDGUARD-KB-1.2发布说明](../knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

## 权威顺序

发生业务规则、字段或流程冲突时：

```text
MOLDGUARD-KB-1.2知识正文
→ V5.0完整实施计划
→ V3.0模型字段
→ REPORT-FORM-1.0接口契约
```

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
