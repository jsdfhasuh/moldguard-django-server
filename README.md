# MoldGuard Django Test Server

面向模具保养智能体比赛的无角色、无鉴权外部测试服务器。

## 当前基线

```text
知识库：MOLDGUARD-KB-1.2
实施计划：V4.2
模型字段：V3.0
数据库：SQLite
端口：18080
数据：DEMO ONLY
```

发生冲突时，以最新知识库 V1.2 为最终解释。

## 主流程

```text
触发扫描并自动建单
→ 选择人员派工
→ 平台发送含点检知识和report_url的邮件
→ 人员点击链接直接报工
→ 正常完成并复位 / 异常继续处理或关联修模
→ 工时和履历查询
```

## 关键规则

- 注塑：`<1000T=50,000`、`>=1000T=30,000`，另有2个月时间工单；
- 钣金：成型150,000，冲孔落料/连续/边板400,000；
- LC109必须显式提供 `mold_category`；
- 正常报工直接完成，不设置主管验收；
- 报工链接由Django生成，智能体平台只负责放入邮件。

## 权威文档

- [文档索引](docs/README.md)
- [实施计划V4.2](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [模型字段V3.0](docs/models/2026-08-13-django-model-field-review.md)
- [邮件报工链接契约](docs/contracts/2026-08-13-mail-report-link-contract.md)

建议实施分支：`agent/django-test-server-v1`
