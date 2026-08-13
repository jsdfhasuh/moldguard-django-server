# MoldGuard Django Test Server

面向模具保养智能体比赛的无角色、无鉴权外部测试服务器。

## 当前基线

```text
知识库：MOLDGUARD-KB-1.2
实施计划：V4.2
模型字段：V3.0
报工表单：REPORT-FORM-1.0
数据库：SQLite
端口：18080
数据：DEMO ONLY
```

发生业务规则、字段或流程冲突时，以最新知识库 `MOLDGUARD-KB-1.2` 为最终解释。

## 仓库结构

```text
docs/             方案、模型、接口、业务场景和决策记录
knowledge-base/   版本化知识库正文、发布清单和校验信息
```

知识库与 Django 代码分离管理，不将知识正文硬编码进业务代码。

## 最终知识库

- [知识库总入口](knowledge-base/README.md)
- [MOLDGUARD-KB-1.2 发布说明](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)
- [发布清单和校验报告](knowledge-base/releases/MOLDGUARD-KB-1.2/manifests/)

比赛平台只上传 `upload/` 下的两个 Markdown 文件，不同时上传完整审阅稿，避免重复召回。

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
- `LC109` 必须显式提供 `mold_category`；
- 正常报工直接完成，不设置主管验收；
- 报工链接由 Django 生成，智能体平台只负责放入邮件。

## 权威文档

- [文档索引](docs/README.md)
- [实施计划V4.2](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [模型字段V3.0](docs/models/2026-08-13-django-model-field-review.md)
- [邮件报工链接契约](docs/contracts/2026-08-13-mail-report-link-contract.md)
- [知识库V1.2发布记录](docs/knowledge/2026-08-13-moldguard-kb-v1.2-release.md)

建议实施分支：`agent/django-test-server-v1`
