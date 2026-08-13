# MoldGuard Django 测试服务器简化确认

- **确认状态**：`OWNER_CONFIRMED`
- **版本**：V1.1
- **确认日期**：2026-08-13
- **适用系统**：MoldGuard Django Test Server V4.1

---

## 1. 最终定位

```text
比赛测试服务器
无角色
无用户登录
无API鉴权
无历史导入
仅使用DEMO数据
SQLite
端口18080
```

---

## 2. 最终保留功能

```text
模具查询
模次与2个月提醒
模拟人员和候选查询
工单创建与派工
工单状态机
点检JSON
知识JSON
邮件结果
验收或转修模
保养/修模/换镶件复位
工时与完成率
```

---

## 3. 最终删除功能

```text
主管及其他业务角色
账号、密码和权限
X-API-Key、Token、JWT
历史记录上传和导入
历史导入复位
保养计划、两次关闭机会和送模
健康评分
排产锁定
复杂规则表和审批
完整修模工单
故障标准数据库
点检图片
多版本知识快照
邮件抄送、附件和尝试历史
生产级数据库、容灾和安全治理
```

---

## 4. 最终模型

```text
Mold
Alert
Employee
WorkOrder
WorkOrderEvent
MaintenanceRecord
```

规则写在代码常量中；周期基线直接保存在 Mold；点检、知识和邮件结果直接保存在 WorkOrder；复位履历保存在 MaintenanceRecord。

---

## 5. 业务保护

虽然无鉴权，仍保留：

```text
状态机校验
数据库事务
唯一键和重复工单检查
提醒dedupe_key
工单create_key
事件request_key
履历request_key
Request-ID
统一错误码
```

这些用于演示稳定，不属于安全鉴权。

---

## 6. 部署

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:18080
```

数据文件：

```text
data/db.sqlite3
```

比赛平台直接通过 HTTP 调用。若平台强制 HTTPS，只在外部增加代理或隧道。

---

## 7. 风险边界

- 只使用模拟数据；
- 不接真实MES、ERP和真实员工通讯录；
- 不长期暴露公网；
- 比赛结束后停止服务；
- 企业正式版本需重新设计身份、权限和安全。

---

## 8. 权威结论

V4.1是最终最小测试服务器范围。早期V3.x和V4.0中关于历史导入、复杂模型、角色、鉴权、计划和生产部署的内容不再实施。