# MoldGuard 文档索引

- **当前知识库**：`MOLDGUARD-KB-1.2`
- **业务功能基线**：V4.2
- **比赛代码快速实施计划**：V1.0
- **当前模型字段**：V3.0
- **当前报工表单**：`REPORT-FORM-1.0`
- **可复用测试代码**：`agent/platform-capability-probe-v1@2ed0b59`

## 当前权威文档

1. [比赛服务器快速代码实施计划V1.0](plans/2026-08-13-moldguard-competition-server-fast-track-plan.md)
2. [Django业务功能实施计划V4.2](plans/2026-08-12-moldguard-django-implementation-plan.md)
3. [Django模型字段V3.0](models/2026-08-13-django-model-field-review.md)
4. [邮件报工链接契约](contracts/2026-08-13-mail-report-link-contract.md)
5. [智能体平台与Django关系说明](architecture/2026-08-12-agent-platform-django-relationship.md)
6. [业务场景说明](business/2026-08-12-moldguard-business-scenarios.md)
7. [知识库与Django对齐说明](knowledge/2026-08-12-moldguard-kb-django-alignment.md)
8. [知识库权威确认](decisions/2026-08-13-kb-v1.2-authority-and-mail-report-confirmation.md)
9. [负责人决策状态](decisions/2026-08-12-owner-decision-checklist.md)

## 两份计划的关系

```text
V4.2：定义比赛服务器最终应实现什么业务能力
快速代码计划V1.0：根据现有测试分支，定义怎样最快改造成可部署比赛服务器
```

快速实施不从空仓库重写。代码以测试分支为起点，增量同步 `main` 的最终知识库和业务契约。

## 最终知识库正文

- [知识库总入口](../knowledge-base/README.md)
- [MOLDGUARD-KB-1.2发布说明](../knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](../knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

## 权威顺序

发生业务冲突时：

```text
MOLDGUARD-KB-1.2知识正文
→ V4.2业务功能计划
→ V3.0模型字段
→ REPORT-FORM-1.0接口契约
```

发生实施方式冲突时：

```text
比赛服务器快速代码实施计划V1.0
→ 测试分支现有实现
```

早期只读方案、V3.x修订、旧决策快照和与V1.2冲突的触发规则文件已经从仓库删除，不再作为开发依据。
