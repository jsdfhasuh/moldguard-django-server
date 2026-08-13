# MoldGuard Competition Server

面向模具保养智能体比赛的无角色、无鉴权外部业务测试服务器。

## 当前基线

```text
知识库：MOLDGUARD-KB-1.2
业务功能计划：V4.2
比赛代码快速实施计划：V1.0
模型字段：V3.0
报工表单：REPORT-FORM-1.0
可复用测试代码：agent/platform-capability-probe-v1@2ed0b59
目标实施分支：agent/competition-server-v1
本地测试数据库：SQLite
比赛部署数据库：MariaDB
端口：18080
数据：DEMO ONLY
```

发生业务规则、字段或流程冲突时，以最新知识库 `MOLDGUARD-KB-1.2` 为最终解释。

## 当前代码策略

测试分支已经实现 Django/DRF 工程、预警、工单、派工、知识快照、邮件结果、正常/异常报工、幂等、测试及 Docker/MariaDB 部署。

比赛服务器不从空仓库重写，而是：

```text
从 agent/platform-capability-probe-v1 创建比赛分支
→ 同步 main 的最终知识库和业务契约
→ 增量改造触发规则、字段、report_url和异常闭环
→ 沿用现有 Docker Compose + MariaDB + Nginx 部署
```

## 仓库结构

```text
docs/             方案、模型、接口、业务场景、决策和快速实施计划
knowledge-base/   解压后的最终知识文档、发布清单和校验信息
```

知识库与 Django 代码分离管理，不将知识正文硬编码进业务代码。仓库不保存 ZIP 交付包。

## 最终知识库

- [知识库总入口](knowledge-base/README.md)
- [MOLDGUARD-KB-1.2 发布说明](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)
- [发布清单和校验报告](knowledge-base/releases/MOLDGUARD-KB-1.2/manifests/)

比赛平台只上传 `upload/` 下的两个 Markdown 文件，不上传发布清单或校验报告。

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
- [比赛服务器快速代码实施计划V1.0](docs/plans/2026-08-13-moldguard-competition-server-fast-track-plan.md)
- [业务功能计划V4.2](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [模型字段V3.0](docs/models/2026-08-13-django-model-field-review.md)
- [邮件报工链接契约](docs/contracts/2026-08-13-mail-report-link-contract.md)
- [知识库MOLDGUARD-KB-1.2](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
