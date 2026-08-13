# MoldGuard 模具保养智能体最小业务场景说明

- **版本**：V2.1
- **日期**：2026-08-13
- **适用项目**：2026年珠海市职工劳动和技能竞赛“AI智能体操作与应用”
- **服务器定位**：无角色、无鉴权、无历史导入的 Django 测试服务器
- **配套计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.1

---

## 1. 场景定位

比赛版只演示以下闭环：

```text
查询模具
→ 扫描保养提醒
→ 创建工单
→ 选择人员并派工
→ 检索点检知识并发邮件
→ 开工、暂停、恢复
→ 点检、报完工和验收
→ 合格归档或转修模
→ 周期复位
→ 工时和完成率分析
```

不展示主管权限、保养计划、送模、历史数据导入或完整修模流程。

---

## 2. 当前规则

### 自动保养提醒

| 开发吨位 | 周期阈值 |
|---:|---:|
| `<1000T` | 50,000模次 |
| `>=1000T` | 30,000模次 |

钣金和注塑当前不区分一级、二级、三级保养。

### 2个月提醒

当前只对注塑模具生成信息提醒：

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

历史记录导入已删除。

---

## 3. 场景总览

| 编号 | 场景 | P0 | 参赛展示 |
|---|---|---:|---|
| S01 | 查询模具保养状态 | 是 | 是 |
| S02 | 执行今日巡检 | 是 | 是 |
| S03 | 注塑模具2个月提醒 | 是 | 可选 |
| S04 | 创建工单 | 是 | 是 |
| S05 | 查询候选人员并派工 | 是 | 是 |
| S06 | 知识随单邮件 | 是 | 是 |
| S07 | 开工、暂停和恢复 | 是 | 是 |
| S08 | 点检和报完工 | 是 | 是 |
| S09 | 验收、退回或转修模 | 是 | 是 |
| S10 | 周期复位 | 是 | 是 |
| S11 | 工时和完成率分析 | 是 | 是 |

---

## 4. S01 查询模具保养状态

平台调用：

```http
GET /api/v1/molds/{mold_id}/maintenance-status
```

Django返回：

```text
模具编号、名称、类型
开发吨位
当前累计模次
周期基线模次和时间
当前周期模次
适用阈值
剩余或超期模次
使用率
是否到期
下一次2个月提醒时间（注塑）
```

平台根据这些事实生成自然语言说明。

---

## 5. S02 执行今日巡检

平台调用：

```http
POST /api/v1/alerts/scan
```

Django：

1. 读取模拟模具；
2. 按开发吨位选择30,000或50,000阈值；
3. 计算周期模次；
4. 创建模次到期提醒；
5. 创建注塑2个月信息提醒；
6. 使用唯一去重键防止重复提醒。

---

## 6. S03 注塑2个月提醒

Django创建：

```text
alert_type = MAINTENANCE_TIME_REMINDER
```

平台发送提醒。该提醒不能直接作为工单来源。

---

## 7. S04 创建工单

平台选择一条模次到期提醒后调用：

```http
POST /api/v1/work-orders
```

Django：

- 校验提醒和模具数据；
- 检查同一模具是否已有未关闭工单；
- 创建 `PENDING_ASSIGNMENT` 工单；
- 保存阈值、技能和知识画像快照。

不经过保养计划、送模或主管确认。

---

## 8. S05 候选人员和派工

平台调用：

```http
GET /api/v1/work-orders/{work_order_id}/candidates
```

Django按以下条件返回候选：

```text
技能匹配率 >= 80%
当前负荷 < 80%
在岗且可用
邮箱已配置
同产线优先
```

平台操作人员选择一人，再调用：

```http
POST /api/v1/work-orders/{work_order_id}/assign
```

Django重新校验人员状态并保存派工。

---

## 9. S06 知识随单邮件

Django返回：

```text
mold_type
knowledge_profile_code
trigger_rule_id
threshold
```

平台检索：

- 保养项目；
- 点检清单；
- 安全注意事项；
- 验收标准。

平台把最后一份知识包回写：

```http
POST /api/v1/work-orders/{work_order_id}/knowledge
```

发送邮件后回写最后一次结果：

```http
POST /api/v1/work-orders/{work_order_id}/email-result
```

Django不保存知识版本历史、邮件抄送或附件记录。

---

## 10. S07 开工、暂停和恢复

```http
POST /api/v1/work-orders/{id}/start
POST /api/v1/work-orders/{id}/pause
POST /api/v1/work-orders/{id}/resume
```

Django记录时间、暂停原因和工单事件。

---

## 11. S08 点检和报完工

平台把本次点检模板和结果以JSON提交：

```http
POST /api/v1/work-orders/{id}/inspection
```

每项结果：

```text
PASS
FAIL
NOT_APPLICABLE
```

约束：

- 每项必须填写；
- FAIL必须说明原因；
- NOT_APPLICABLE必须说明原因；
- 存在FAIL时不能验收完成。

报完工：

```http
POST /api/v1/work-orders/{id}/report-complete
```

工单进入 `PENDING_ACCEPTANCE`。

---

## 12. S09 验收、退回和转修模

平台操作人员选择：

```text
验收通过
退回继续处理
转修模
```

对应接口：

```http
POST /api/v1/work-orders/{id}/accept
POST /api/v1/work-orders/{id}/reject
POST /api/v1/work-orders/{id}/transfer-to-repair
```

转修模只保存工单状态和原因，不创建独立修模工单。

---

## 13. S10 周期复位

### 保养完成

验收通过后自动复位。

### 修模完成

```http
POST /api/v1/molds/{mold_id}/repair-completed
```

### 换镶件完成

```http
POST /api/v1/molds/{mold_id}/insert-replaced
```

三类事件均创建 `MaintenanceRecord` 并更新 Mold 周期基线。

不支持历史记录上传或导入。

---

## 14. S11 工时和完成率分析

Django提供：

```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/work-hours
GET /api/v1/analytics/order-completion
```

平台生成：

- 工单数量；
- 已完成数量；
- 完成率；
- 派工至报工总历时；
- 等待开工时间；
- 实际执行时间；
- 暂停时间。

---

## 15. 参赛演示建议

建议5分钟：

1. 扫描提醒；
2. 选择一套到期模具；
3. 创建工单；
4. 查询并选择候选人员；
5. 检索知识并发送邮件；
6. 开工、暂停、恢复；
7. 提交点检并报完工；
8. 验收完成并展示周期复位；
9. 查看工时和完成率；
10. 快速展示FAIL转修模。

---

## 16. 场景边界

```text
无角色
无鉴权
无历史导入
无保养计划和送模
无健康评分
无完整修模工单
无真实生产数据
```

比赛结束后停止测试服务器。