# MoldGuard Django Server

面向“模具保养智能预警与管理智能体”比赛项目的外部虚拟业务服务器、规则引擎和工单状态中心。

## 最终架构

```text
比赛智能体平台
├─ 自然语言交互
├─ 工作流编排
├─ 点检知识库与 RAG
├─ LLM 内容生成
├─ 主管确认
└─ 邮件生成与发送
          │ HTTPS + JSON
          ▼
MoldGuard Django Server
├─ 模具台账与保养标准
├─ 健康评分与预警记录
├─ 工单创建与去重
├─ 候选人员与派工结果
├─ 工单状态机与过程追踪
├─ 知识快照与邮件结果回写
├─ 报工、验收与模具履历
├─ 工时和完成率统计
└─ 权限、幂等与审计日志
```

## 系统分工

### 智能体平台负责

- 用户自然语言交互；
- Chatflow、Workflow、Agent 编排；
- 点检要求、操作指导书、故障案例等知识库；
- RAG 检索和 LLM 生成；
- 展示候选人员并让主管最终确认；
- 任务内容组装；
- 邮件生成和发送；
- 将知识快照和邮件结果回写 Django；
- 基于 Django 统计数据生成分析结论。

### Django 负责

- 模具台账、模次和位置；
- 保养标准、标准版本和标准工时；
- 参赛健康评分和红黄绿预警；
- 预警扫描与预警记录；
- 人员、技能、负荷、在岗状态和邮箱；
- 候选人员资格计算与稳定排序；
- 保养工单、派工结果和状态机；
- 开工、暂停、恢复、异常、报工和验收；
- 知识下发快照和邮件发送结果记录；
- 工单归档、模具履历、工时和完成率统计；
- API Key、操作人权限、幂等、事务和审计。

### Django 不负责

- 自建知识库、Embedding、Rerank 或向量数据库；
- 调用大模型；
- SMTP、Mailpit、邮件模板和邮件发送；
- 企业微信、钉钉或短信发送；
- 独立前端；
- 对真实 MES、ERP 或排产系统执行生产写入。

## 当前状态

```text
权威计划：V3.0 FINAL_FROZEN
系统状态：NOT_IMPLEMENTED
下一步：Gate -1 比赛平台能力验证
建议实施分支：agent/django-full-workflow-v1
```

## 权威文档

- 完整实施计划：[`docs/plans/2026-08-12-moldguard-django-implementation-plan.md`](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- 智能体平台与 Django 关系说明：[`docs/architecture/2026-08-12-agent-platform-django-relationship.md`](docs/architecture/2026-08-12-agent-platform-django-relationship.md)

早期只读方案仅用于历史对照，不再作为开发依据：

- [`docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md`](docs/plans/2026-08-12-moldguard-django-query-api-only-plan.md)

## 技术基线

- Python：3.12
- Django：5.2 LTS
- Django REST Framework：3.16 系列
- PostgreSQL：16
- API 前缀：`/api/v1`
- 部署：Docker Compose + Nginx + Gunicorn
- Django 内部端口：`18080`
- 公网入口：HTTPS `443`
- 认证：`X-API-Key` + 操作人权限校验

## 最终演示闭环

```text
预警扫描
→ 创建工单
→ 候选匹配
→ 主管派工
→ 知识检索
→ 邮件发送与回写
→ 开工/暂停/报工
→ 验收归档
→ 工时和完成率分析
```

后续业务代码必须在 `agent/django-full-workflow-v1` 分支实施，并按权威计划中的 Gate 和 Stop Gate 分阶段验收。
