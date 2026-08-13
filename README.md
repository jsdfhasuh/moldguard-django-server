# MoldGuard Django Test Server

面向“模具保养智能预警与管理智能体”比赛项目的最小外部模拟业务服务器。

## 当前定位

```text
无角色
无用户登录
无API鉴权
无历史导入
仅使用DEMO数据
SQLite
端口18080
```

Django只保留比赛主链路需要的模具、提醒、人员、工单、点检、验收、周期复位和基础统计。

## 架构

```text
比赛智能体平台
├─ 对话与工作流
├─ 知识库与RAG
├─ LLM生成
├─ 人员选择
└─ 邮件发送
          │ HTTP + JSON
          ▼
MoldGuard Django Test Server
├─ 模具与周期基线
├─ 30,000/50,000模次规则
├─ 模次到期和2个月提醒
├─ 模拟人员与候选匹配
├─ 工单、派工和状态机
├─ 点检JSON、知识JSON和邮件结果
├─ 保养/修模/换镶件复位
└─ 工时与完成率
          │
          ▼
        SQLite
```

## 已确认规则

### 自动保养提醒

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 50,000模次 |
| `>=1000T` | 30,000模次 |

钣金和注塑当前不区分一级、二级、三级保养。

### 每2个月提醒

当前只适用于注塑模具：

```text
只提醒
不自动创建工单
不自动派工
```

### 周期复位

```text
保养完成
修模完成
换镶件完成
```

历史记录导入及历史导入复位已经删除。

## 最终模型

只建立 6 个模型：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

不建立独立规则表、周期表、复位事件表、知识表、邮件表、点检表、转修模表和幂等表。

## 智能体平台负责

- 对话和工作流；
- 知识库检索；
- LLM生成预警、任务和分析；
- 展示候选人员并选择派工人；
- 发送邮件；
- 回写最后一份知识JSON和最后一次邮件结果。

## Django负责

- 模拟模具、吨位、模次、位置和周期基线；
- 规则计算和提醒扫描；
- 模拟人员、技能、负荷和邮箱；
- 工单、派工、状态和时间线；
- 点检JSON和验收；
- 转修模状态；
- 保养、修模、换镶件复位；
- 系统产生的履历、工时和完成率；
- 演示数据重置。

## 明确不做

```text
历史数据导入
主管和业务角色
用户登录和API安全鉴权
保养计划、送模和关闭机会
健康评分
排产锁定
复杂规则审批
完整修模流程
故障标准数据库
多版本知识快照
邮件抄送、附件和尝试历史
真实MES/ERP
生产级安全和容灾
```

## 技术基线

```text
Python 3.12
Django 5.2 LTS系列
Django REST Framework 3.16系列
SQLite
HTTP端口18080
```

最简启动：

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:18080
```

## 当前状态

```text
权威计划：V4.1 FINAL_FROZEN_MINIMAL_TEST_SERVER
模型字段：V2.1 FIELD_SCOPE_FROZEN
系统状态：NOT_IMPLEMENTED
实施分支：agent/django-test-server-v1
```

## 权威文档

- [Django最小测试服务器实施计划V4.1](docs/plans/2026-08-12-moldguard-django-implementation-plan.md)
- [最终6个模型字段清单V2.1](docs/models/2026-08-13-django-model-field-review.md)
- [智能体平台与Django关系说明V2.1](docs/architecture/2026-08-12-agent-platform-django-relationship.md)
- [最小业务场景说明V2.1](docs/business/2026-08-12-moldguard-business-scenarios.md)
- [知识库对齐说明V2.1](docs/knowledge/2026-08-12-moldguard-kb-django-alignment.md)
- [负责人决策清单](docs/decisions/2026-08-12-owner-decision-checklist.md)
- [最小模型范围确认](docs/decisions/2026-08-13-minimal-model-scope-confirmation.md)

## 参赛主流程

```text
扫描提醒
→ 创建工单
→ 查询候选并派工
→ 知识检索和邮件
→ 开工/暂停/恢复
→ 点检和报完工
→ 验收或转修模
→ 周期复位
→ 工时和完成率
```

由于服务器无鉴权，只能使用模拟数据，并在比赛结束后停止服务。