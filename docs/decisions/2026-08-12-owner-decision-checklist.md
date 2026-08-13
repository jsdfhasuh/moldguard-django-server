# MoldGuard 参赛实施负责人决策清单（持续更新）

- **状态**：`BUSINESS_SCOPE_CONFIRMED`
- **版本**：V1.6
- **最后更新**：2026-08-13
- **适用项目**：MoldGuard 模具保养智能预警与管理智能体
- **服务器定位**：无角色、无鉴权、无历史导入的最小 Django 测试服务器
- **权威计划**：`docs/plans/2026-08-12-moldguard-django-implementation-plan.md` V4.1
- **模型字段**：`docs/models/2026-08-13-django-model-field-review.md` V2.1

---

## 1. 当前进度

| 项目 | 状态 |
|---|---|
| 业务范围 D01—D18 | 已确认 |
| 模型范围 | 已确认：6个模型 |
| 平台能力 P01—P04 | 待验证 |
| 参赛材料 M01—M05 | 待确认 |
| 业务代码 | 尚未实现 |

---

## 2. 已确认业务范围

### D01｜自动执行规则

只使用两条当前规则：

```text
<1000T  → 50,000模次
>=1000T → 30,000模次
```

不增加寿命、闲置或历史规则自动触发。

### D02、D04、D05、D06｜吨位和保养等级

```text
钣金与注塑统一按开发吨位触发
当前不区分一级、二级、三级保养
历史分类周期只作为知识参考
```

### D03｜2个月提醒

```text
当前只适用于注塑模具
只提醒
不自动创建工单
不自动派工
```

### D07｜关闭机会

```text
不实现保养计划
不实现两次关闭机会
平台决定是否创建工单
```

### D08｜周期复位

保留：

```text
保养完成
修模完成
换镶件完成
```

删除：

```text
历史记录导入
历史导入复位
```

### D09｜健康评分

```text
不实现健康评分
只显示周期模次、阈值和使用率
```

### D10｜排产锁定

```text
Django不保存锁定状态
比赛版不演示真实或模拟排产锁定
```

### D11｜送模

```text
不实现保养计划和送模状态
工单只保存当前模具位置
```

### D12｜派工

```text
Django返回候选人员
→ 平台操作人员选择
→ Django重新校验并保存派工
```

无主管角色。

### D13｜人员负荷

```text
current_load 使用固定演示值
不根据工单自动计算
```

### D14｜点检

```text
所有点检项必须填写
FAIL必须说明
NOT_APPLICABLE必须说明
存在FAIL时不能验收完成
```

点检统一保存在 WorkOrder JSON，不建子表。

### D15｜转修模

```text
只把工单状态改为 TRANSFERRED_TO_REPAIR
保存 repair_reason
不建立 RepairReferral 和完整修模流程
```

修模完成时单独调用复位接口并生成履历。

### D16｜工时

保存工单时间点和累计暂停秒数，动态计算：

```text
派工至报工总历时
等待开工时长
实际执行时长
暂停时长
```

不重复保存工时结果字段。

### D17｜邮件

```text
只发送给选中的保养人员测试邮箱
不保存抄送、附件和邮件尝试历史
Django只保存最后一次发送结果
```

### D18｜身份和鉴权

```text
无用户登录
无主管或业务角色
无X-API-Key、Token或JWT
无操作人权限校验
```

---

## 3. 已确认模型范围

只建立：

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

明确删除：

```text
MaintenanceRule
MaintenanceCycle
CycleResetEvent
InspectionItemResult
KnowledgeSnapshot
NotificationRecord
RepairReferral
IdempotencyRecord
HistoryImportBatch
HistoryImportRow
```

完整字段见模型字段文档。

---

## 4. 平台 Gate -1 待验证

### P01｜HTTP

- [ ] 能访问 `http://<server>:18080`
- [ ] 能发送 GET 和 POST
- [ ] 能读取HTTP状态码和业务错误码
- [ ] 能配置超时和重试

### P02｜JSON和变量

- [ ] 能读取嵌套字段
- [ ] 能遍历候选人员和点检数组
- [ ] 能传递 mold_id、work_order_id、employee_id
- [ ] 能用上一步响应构造下一步请求
- [ ] 重试时复用 Idempotency-Key

### P03｜知识库

- [ ] 能按 knowledge_profile_code 过滤
- [ ] 能返回知识来源标识
- [ ] 能生成单份知识JSON并回写Django
- [ ] 历史阈值不会覆盖Django规则

### P04｜邮件

- [ ] 支持动态收件人
- [ ] 支持结构化正文
- [ ] 返回发送状态或消息ID
- [ ] 能回写Django最后一次邮件结果

---

## 5. 参赛材料待确认

### M01｜项目名称

推荐：

```text
MoldGuard模具卫士——模具保养智能预警与知识随单闭环智能体
```

### M02｜平台名称

建议把“Dify平台”改为“比赛智能体平台”。

### M03｜量化数字

以下数字应提供证据、改成目标值或删除：

```text
单基地约500套
寿命缩短30%—50%
2—4小时压缩至10秒
```

### M04｜演示数据

需要准备：

```text
6套模拟模具
4名模拟人员
测试收件邮箱
一条邮件失败状态
一条点检失败转修模状态
```

### M05｜测试服务器声明

答辩时明确：

```text
Django为无鉴权测试服务器
全部数据为DEMO
不接入真实生产系统
```

---

## 6. 当前结论

```text
业务和模型范围已经冻结
可以创建 agent/django-test-server-v1 开始编码
编码前只需完成平台最小HTTP验证
```

权威确认记录：

- [最小模型范围确认](2026-08-13-minimal-model-scope-confirmation.md)
- [测试服务器简化确认](2026-08-13-test-server-simplification-confirmation.md)
- [吨位触发规则确认](2026-08-13-maintenance-trigger-rule-confirmation.md)
- [2个月提醒与复位确认](2026-08-13-time-reminder-cycle-reset-confirmation.md)