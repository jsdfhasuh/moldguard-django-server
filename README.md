# MoldGuard Competition Server

面向模具保养智能体比赛的无角色、无鉴权外部业务服务器。

## 当前基线

```text
知识库：MOLDGUARD-KB-1.2
完整实施计划：V5.0
阻塞项决议：V5.1
邮件发送决议：Django SMTP
一天后端优先计划：V1.0
模型字段：V3.1
报工表单：REPORT-FORM-1.1
目标实施分支：agent/competition-server-v1
本地测试数据库：SQLite
比赛部署数据库：MariaDB
容器内端口：18080
比赛宿主端口：127.0.0.1:18081
旧回退服务端口：127.0.0.1:18080
数据：DEMO ONLY
```

发生业务规则、字段或流程冲突时，以最新知识库 `MOLDGUARD-KB-1.2` 为最终解释。

## 代码实施策略

比赛服务器从 `main` 创建新分支并重新编码，不复用测试分支代码：

```text
main
→ agent/competition-server-v1
→ Codex一次性完成P0后端
→ 按单元/API/集成测试逐类Debug
→ 再完成HTML报工页面、异常关联修模和部署
```

测试分支：

```text
agent/platform-capability-probe-v1@2ed0b59
```

只用于参考统一响应、Request-ID、幂等、事务、测试组织和 Docker/MariaDB 部署经验；不合并、不 cherry-pick、不复制旧迁移，也不沿用 `platform_probe` 应用和 `/probe/*` 接口。

## 一天优先级

### P0 必须完成

```text
Django工程与7个模型
DEMO数据命令
注塑/钣金规则
扫描自动建单和合并触发
候选人员与指定派工
知识包、Django SMTP派工邮件和report_url
JSON正常/异常报工
履历、周期复位、幂等和核心测试
Docker/MariaDB可启动
```

### P1 后半段完成

```text
HTML报工页面
继续处理与关联修模
基础统计
tracking/overdue
Nginx/HTTPS和平台联调
```

## 仓库结构

```text
docs/             完整计划、V5.1决议、一天执行计划、模型和契约
knowledge-base/   解压后的最终知识文档、发布清单和校验信息
```

`agent/competition-server-v1` 已完成 P0、P1/P2 比赛范围，当前状态为
`READY_FOR_SMTP_CONFIGURATION`。实现包括 Django SMTP 双格式派工邮件、HTML 邮件链接报工、执行状态机、异常继续处理、
关联修模、tracking、基础统计、自动派工和蓝绿部署脚本。SQLite 全量测试、独立
MariaDB测试和 Nginx 回退已验证；新 SMTP 版本只有在配置真实 SMTP 与收件邮箱、
完成实际投递验证后才能恢复为 `READY_FOR_COMPETITION`。

当前部署使用独立 Compose 项目 `moldguard-competition`、独立目录
`runtime/competition/mariadb` 和宿主端口 `127.0.0.1:18081`。旧 `moldguard` 栈、
`127.0.0.1:18080` 及其数据库目录继续保留，用于快速回退。

## 最终知识库

- [知识库总入口](knowledge-base/README.md)
- [MOLDGUARD-KB-1.2 发布说明](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
- [触发保养标准](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/01_触发保养标准.md)
- [保养、点检、故障工时与邮件链接报工](knowledge-base/releases/MOLDGUARD-KB-1.2/upload/02_保养内容_点检_储放_故障工时与邮件链接报工.md)

比赛平台只上传 `upload/` 下的两个 Markdown 文件，不上传发布清单或校验报告。

## 比赛主流程

```text
触发扫描并自动建单
→ 查询候选人员并派工
→ 平台检索点检知识
→ 平台回写知识包并调用Django send-email
→ Django通过SMTP发送含点检知识和report_url的邮件
→ 人员点击Django链接直接报工
→ 正常完成并复位 / 异常继续处理或关联修模
→ 查询工时、完成率和模具履历
```

## 蓝绿部署与回退

- Competition 环境示例：`.env.competition.example`
- Compose：`compose.yaml`
- 部署脚本：`scripts/deploy_competition.sh`
- MariaDB 备份：`scripts/backup_mariadb.sh`
- Nginx 切换模板：`deploy/nginx/moldguard-competition.conf`
- 回退脚本：`scripts/rollback_competition.sh`
- 完整运行手册：[蓝绿部署与回退](docs/deployment-blue-green.md)

## 关键实现决议

- 同一周期模次和时间同时命中时只创建一张正式工单；
- 正常报工允许从 `ASSIGNED` 直接完成；
- 页面不输入员工编号，服务器使用工单 `assignee`；
- `current_load` 使用固定 DEMO 值，不自动增减；
- 未配置标准工时时返回 null，不猜测；
- `POST /api/v1/work-orders/{id}/send-email` 只接受 `client_request_id`；
- 收件人固定为工单 `assignee.email`，邮件由Django渲染并通过SMTP发送；
- `GET /email-context` 仅用于预览，公开 API 不提供 `POST /email-result`；
- SMTP发送成功后锁定知识包；发送中、结果未知或成功后均不可覆盖；
- SMTP外部副作用使用两阶段幂等，不把网络调用放进长数据库事务；
- 所有写 API 使用 `client_request_id` 精确重放；
- 异常报工不结单、不复位，可继续处理或关联修模。

## 权威文档

- [文档索引](docs/README.md)
- [一天后端优先实施计划V1.0](docs/plans/2026-08-13-moldguard-one-day-backend-first-plan.md)
- [Django SMTP派工邮件决议](docs/decisions/2026-08-13-django-smtp-delivery.md)
- [V5.1阻塞项决议](docs/decisions/2026-08-13-v5.1-blocker-resolution.md)
- [比赛服务器完整实施计划V5.0](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [模型字段V3.1](docs/models/2026-08-13-django-model-field-review.md)
- [报工契约REPORT-FORM-1.1](docs/contracts/2026-08-13-mail-report-link-contract.md)
- [知识库MOLDGUARD-KB-1.2](knowledge-base/releases/MOLDGUARD-KB-1.2/README.md)
