# MoldGuard Django Test Server

面向“模具保养智能预警与管理智能体”比赛项目的外部模拟业务服务器。

## 当前定位

```text
无主管角色
无用户登录
无API安全鉴权
仅使用DEMO数据
用于比赛平台联调和现场演示
```

Django仍保存模具提醒、工单、派工、点检、验收、周期复位和统计状态，但不按照企业生产系统建设。

## 最终架构

```text
比赛智能体平台
├─ 自然语言交互
├─ Workflow / Agent 编排
├─ MoldGuard知识库与RAG
├─ LLM内容生成
├─ 平台操作人员选择
└─ 邮件生成与发送
          │ HTTP + JSON
          ▼
MoldGuard Django Test Server
├─ 模具、吨位、模次和周期
├─ 保养提醒和2个月提醒
├─ 工单、候选人员和派工
├─ 开工、暂停、点检和验收
├─ 转修模和周期复位
├─ 知识快照和邮件结果
└─ 工时、完成率和超时统计
          │
          ▼
        SQLite
```

## 已确认规则

### 自动保养提醒

当前钣金和注塑模具不区分一级、二级、三级保养：

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 每累计生产50,000模次 |
| `>=1000T` | 每累计生产30,000模次 |

### 每2个月提醒

当前适用于注塑模具：

```text
每2个自然月生成提醒
只提醒
不自动创建工单
不自动派工
```

### 周期复位

以下事件复位周期：

```text
保养完成
修模完成
换镶件完成
有效历史记录导入
```

## 系统分工

### 智能体平台负责

- 对话和工作流；
- 知识库检索；
- LLM生成预警、任务和分析；
- 展示候选人员；
- 平台操作人员选择派工人和验收结果；
- 生成和发送邮件；
- 回写知识快照和邮件结果。

### Django负责

- 模拟模具、吨位、模次和位置；
- 30,000/50,000模次规则；
- 保养周期和2个月提醒；
- 工单和派工状态；
- 候选人员、技能、负荷和测试邮箱；
- 开工、暂停、恢复、点检和报完工；
- 验收、转修模和周期复位；
- 履历、工时和完成率统计；
- 演示数据重置。

### Django不负责

- 主管、管理员等业务角色；
- 用户登录和权限；
- X-API-Key、Token或JWT；
- 大模型和向量知识库；
- SMTP和邮件发送；
- 真实MES、ERP或排产系统；
- 生产级安全和容灾。

## 技术基线

```text
Python 3.12
Django 5.2 LTS系列
Django REST Framework 3.16系列
SQLite
端口18080
无API鉴权
```

最简运行：

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:18080
```

可选使用单进程Gunicorn。

## 当前状态

```text
权威计划：V4.0 FINAL_FROZEN_FOR_TEST_SERVER
模型字段：OWNER_FIELD_REVIEW_REQUIRED
系统状态：NOT_IMPLEMENTED
建议实施分支：agent/django-test-server-v1
数据性质：DEMO ONLY
```

## 当前权威文档

- [文档状态索引](docs/README.md)
- [Django测试服务器实施计划V4.0](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [Django模型字段审查表V1.0](docs/models/2026-08-13-django-model-field-review.md)
- [智能体平台与Django测试服务器关系说明V2.0](docs/architecture/2026-08-12-agent-platform-django-relationship.md)
- [简化业务场景说明V2.0](docs/business/2026-08-12-moldguard-business-scenarios.md)
- [知识库与Django测试服务器对齐说明V2.0](docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md)
- [负责人决策清单（持续更新）](docs/decisions/2026-08-12-owner-decision-checklist.md)
- [测试服务器简化确认](docs/decisions/2026-08-13-test-server-simplification-confirmation.md)
- [自动保养触发规则确认V1.1](docs/decisions/2026-08-13-maintenance-trigger-rule-confirmation.md)
- [每2个月提醒与周期复位确认V1.1](docs/decisions/2026-08-13-time-reminder-cycle-reset-confirmation.md)

早期V3.x复杂业务计划和历史决策快照只用于追溯，发生冲突时以V4.0和文档状态索引为准。

## 参赛主流程

```text
扫描提醒
→ 创建工单
→ 查询候选人员
→ 平台选择并派工
→ 知识检索与邮件
→ 开工/暂停/恢复
→ 逐项点检与报完工
→ 验收完成或转修模
→ 周期复位
→ 工时和完成率分析
```

## 测试服务器边界

由于没有鉴权：

- 只能使用模拟模具、模拟人员和测试邮箱；
- 不接真实生产数据库；
- 不长期暴露并保存真实数据；
- 比赛结束后应停止服务；
- 企业正式落地时必须重新设计认证、权限和安全部署。
