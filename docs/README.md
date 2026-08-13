# MoldGuard 文档状态索引

- **最后更新**：2026-08-13
- **当前服务器基线**：V4.1 Minimal Django Test Server

---

## 1. 当前权威文档

1. [Django最小测试服务器实施计划V4.1](plans/2026-08-12-moldguard-django-implementation-plan.md)
2. [最终6个模型字段清单V2.1](models/2026-08-13-django-model-field-review.md)
3. [智能体平台与Django关系说明V2.1](architecture/2026-08-12-agent-platform-django-relationship.md)
4. [最小业务场景说明V2.1](business/2026-08-12-moldguard-business-scenarios.md)
5. [知识库与Django最小对齐说明V2.1](knowledge/2026-08-12-moldguard-kb-django-alignment.md)
6. [负责人决策清单](decisions/2026-08-12-owner-decision-checklist.md)
7. [最小模型范围确认](decisions/2026-08-13-minimal-model-scope-confirmation.md)
8. [测试服务器简化确认](decisions/2026-08-13-test-server-simplification-confirmation.md)

---

## 2. 当前已确认规则

| 规则 | 结论 |
|---|---|
| 自动保养触发 | `<1000T=50,000`，`>=1000T=30,000` |
| 保养等级 | 当前不区分一/二/三级 |
| 2个月提醒 | 注塑模具，仅提醒 |
| 周期复位 | 保养、修模、换镶件完成 |
| 历史导入 | 删除 |
| 角色和鉴权 | 删除 |
| 健康评分 | 删除 |
| 计划和送模 | 删除 |
| 模型数量 | 6个 |

---

## 3. 历史文档

以下文件只用于方案演进追溯，不再作为代码依据：

```text
plans/2026-08-12-moldguard-django-query-api-only-plan.md
plans/2026-08-13-moldguard-django-v3.2-trigger-rule-amendment.md
plans/2026-08-13-moldguard-django-v3.3-reminder-reset-amendment.md
decisions/2026-08-13-owner-decision-checklist-v1.1.md
decisions/2026-08-13-owner-decision-checklist-v1.2.md
```

发生冲突时，以V4.1、模型字段V2.1和当前负责人决策清单为准。

---

## 4. 当前开发顺序

```text
平台最小HTTP验证
→ 创建 agent/django-test-server-v1
→ Phase 0 字段与API合同
→ Phase 1 Django骨架
→ Phase 2 模具与提醒
→ Phase 3 人员与工单
→ Phase 4 知识、邮件与点检
→ Phase 5 复位、履历与统计
→ Phase 6 平台联调
```

---

## 5. 当前边界

```text
模型：6个
数据库：SQLite
接口：无鉴权
端口：18080
数据：DEMO ONLY
历史导入：无
平台：对话、知识库、LLM、邮件
Django：模拟数据、规则、工单状态和统计
```