# MoldGuard 文档状态索引

- **最后更新**：2026-08-13
- **当前服务器基线**：V4.0 Django Test Server
- **用途**：说明哪些文档是当前实施依据，哪些仅用于历史追溯

---

## 1. 当前权威文档

后续开发、测试和比赛联调应优先查看：

1. [Django测试服务器实施计划V4.0](plans/2026-08-12-moldguard-django-implementation-plan.md)
2. [智能体平台与Django测试服务器关系说明V2.0](architecture/2026-08-12-agent-platform-django-relationship.md)
3. [简化业务场景说明V2.0](business/2026-08-12-moldguard-business-scenarios.md)
4. [知识库与Django测试服务器对齐说明V2.0](knowledge/2026-08-12-moldguard-kb-django-alignment.md)
5. [Django模型字段审查表V1.0](models/2026-08-13-django-model-field-review.md)
6. [负责人决策清单（持续更新）](decisions/2026-08-12-owner-decision-checklist.md)
7. [测试服务器简化确认](decisions/2026-08-13-test-server-simplification-confirmation.md)

---

## 2. 已确认业务规则

| 规则 | 状态 | 文档 |
|---|---|---|
| 开发吨位 `<1000T=50,000`、`>=1000T=30,000` | `INTERNAL_CONFIRMED` | [触发规则确认](decisions/2026-08-13-maintenance-trigger-rule-confirmation.md) |
| 注塑模具每2个月仅提醒 | `INTERNAL_CONFIRMED` | [时间提醒与复位确认](decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md) |
| 保养、修模、换镶件、有效历史记录复位周期 | `INTERNAL_CONFIRMED` | [时间提醒与复位确认](decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md) |
| 无主管角色、无登录、无API鉴权 | `OWNER_CONFIRMED` | [测试服务器简化确认](decisions/2026-08-13-test-server-simplification-confirmation.md) |

---

## 3. 历史文档

以下文件用于记录方案演进，不再作为当前代码实现依据：

```text
plans/2026-08-12-moldguard-django-query-api-only-plan.md
plans/2026-08-13-moldguard-django-v3.2-trigger-rule-amendment.md
plans/2026-08-13-moldguard-django-v3.3-reminder-reset-amendment.md
decisions/2026-08-13-owner-decision-checklist-v1.1.md
decisions/2026-08-13-owner-decision-checklist-v1.2.md
```

这些文档中关于以下内容的设计已被V4.0覆盖：

```text
主管及业务角色权限
X-API-Key、JWT或用户登录
PostgreSQL生产部署
保养计划与送模状态
复杂规则审批和冲突模型
完整知识目录发布模型
```

发生冲突时，以V4.0实施计划和当前持续决策清单为准。

---

## 4. 当前开发顺序

```text
负责人审查模型字段F01—F10
→ 冻结模型范围
→ 创建 agent/django-test-server-v1
→ Phase 0 API合同和种子数据
→ Phase 1 Django骨架
→ Phase 2 模具、规则、周期和提醒
→ Phase 3 人员和工单
→ Phase 4 知识、邮件和点检
→ Phase 5 转修模、复位和统计
→ Phase 6 平台联调
```

---

## 5. 当前边界

```text
Django：模拟数据、规则计算、工单状态、点检结果、周期复位和统计
平台：对话、工作流、知识库、LLM和邮件发送
数据：DEMO ONLY
接口：无安全鉴权
数据库：SQLite
端口：18080
```
