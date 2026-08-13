# MoldGuard Competition Server

面向模具保养智能体比赛的无角色、无鉴权外部业务服务器。

## 当前基线

```text
知识库：MOLDGUARD-KB-1.2
完整实施计划：V5.0
模型字段：V3.0
报工表单：REPORT-FORM-1.0
目标实施分支：agent/competition-server-v1
本地测试数据库：SQLite
比赛部署数据库：MariaDB
端口：18080
数据：DEMO ONLY
```

发生业务规则、字段或流程冲突时，以最新知识库 `MOLDGUARD-KB-1.2` 为最终解释。

## 代码实施策略

比赛服务器从 `main` 创建新分支并重新编码，不复用测试分支代码：

```text
main
→ agent/competition-server-v1
→ 新建Django工程、应用、模型和初始迁移
→ 按V5.0完整实现并部署
```

测试分支：

```text
agent/platform-capability-probe-v1@2ed0b59
```

只用于参考统一响应、Request-ID、幂等、事务、测试组织和 Docker/MariaDB 部署经验；不合并、不 cherry-pick、不复制旧迁移，也不沿用 `platform_probe` 应用和 `/probe/*` 接口。

## 仓库结构

```text
docs/             完整实施计划、模型、接口、业务场景和决策
knowledge-base/   解压后的最终知识文档、发布清单和校验信息
```

仓库当前尚未在 `main` 实现业务代码。后续代码统一进入 `agent/competition-server-v1`。

## 最终知识库

- [知识库总入口](knowledge-base/README.md)
- [MOLDGUARD-KB-1.2 发布说明](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)
- [发布清单和校验报告](knowledge-base/releases/MOLDGUARD-KB-1.2/manifests/)

比赛平台只上传 `upload/` 下的两个 Markdown 文件，不上传发布清单或校验报告。

## 比赛主流程

```text
触发扫描并自动建单
→ 查询候选人员并派工
→ 平台检索点检知识
→ 平台发送含点检知识和report_url的邮件
→ 人员点击Django链接直接报工
→ 正常完成并复位 / 异常继续处理或关联修模
→ 查询工时、完成率和模具履历
```

## 关键规则

- 注塑：`<1000T=50,000`、`>=1000T=30,000`，另有2个月时间工单；
- 钣金：成型150,000，冲孔落料/连续/边板400,000；
- `LC109` 必须显式提供 `mold_category`；
- 正常报工直接完成，不设置主管验收；
- 报工链接由 Django 生成，智能体平台只负责放入邮件；
- 异常报工不结单、不复位，可继续处理或关联修模。

## 权威文档

- [文档索引](docs/README.md)
- [比赛服务器完整实施计划V5.0](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [模型字段V3.0](docs/models/2026-08-13-django-model-field-review.md)
- [邮件报工链接契约](docs/contracts/2026-08-13-mail-report-link-contract.md)
- [干净重建确认](docs/decisions/2026-08-13-competition-server-clean-build-confirmation.md)
- [知识库MOLDGUARD-KB-1.2](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
