# MoldGuard 最小模型范围确认

- **确认状态**：`OWNER_CONFIRMED`
- **版本**：V1.0
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server
- **确认目标**：整体按最简单方向实现，删除历史导入及其他非主链路能力

---

## 1. 确认结论

Django 只保留比赛主链路需要的功能：

```text
模具查询
提醒扫描
工单
候选人员和派工
知识与邮件结果
开工、暂停、点检和验收
转修模状态
保养、修模、换镶件复位
基础工时和完成率
```

删除：

```text
历史记录导入
历史导入批次与行
历史导入复位
主管及业务角色
API鉴权
保养计划、送模和两次关闭机会
健康评分
排产锁定状态
复杂规则数据表和审批模型
完整修模工单
故障标准数据库
多版本知识快照
邮件抄送、附件和尝试历史
点检照片
生产级数据库与基础设施
```

---

## 2. 周期复位范围修订

此前确认的四类复位改为三类：

```text
保养完成
修模完成
换镶件完成
```

`HISTORY_RECORD_IMPORTED` 从复位类型、接口、模型、种子数据和测试中删除。

Django 不提供历史记录上传或导入 API。

---

## 3. 最终模型

只建立：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

当前周期字段直接保存在 `Mold`；点检、知识快照和邮件结果直接保存在 `WorkOrder`；复位履历统一保存在 `MaintenanceRecord`。

---

## 4. 当前权威计划

```text
docs/plans/2026-08-12-moldguard-django-implementation-plan.md V4.1
```

发生冲突时，V4.1 和本确认优先于 V4.0、V3.x 以及早期模型字段文档。