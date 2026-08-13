# MoldGuard Django 测试服务器简化确认

- **确认状态**：`OWNER_CONFIRMED`
- **版本**：V1.0
- **确认日期**：2026-08-13
- **适用项目**：MoldGuard 模具保养智能预警与管理智能体
- **影响范围**：Django 实现、接口契约、部署方案、业务场景和平台联调

---

## 1. 确认结论

MoldGuard Django 当前定位为比赛使用的外部测试服务器，不是企业正式生产系统。

因此冻结以下简化决策：

1. 不建立主管角色；
2. 不建立 Django 业务角色和权限体系；
3. 公共 API 不使用 API Key、Token、登录态或用户鉴权；
4. 智能体平台可以直接调用查询和写入接口；
5. 派工、验收、关闭、转修模等动作由平台流程中的人工选择或按钮触发，但 Django 不验证操作者角色；
6. 请求可携带可选的 `operator_id`、`operator_name`，只用于演示日志，不作为权限依据；
7. 保留数据库事务、状态机、唯一约束和幂等处理，它们用于防止重复写入和非法状态，不属于安全鉴权；
8. 服务器只保存模拟模具、模拟人员和测试邮箱，不保存真实生产敏感数据。

---

## 2. Django 删除的实现

删除或不实现：

```text
accounts 应用
用户登录
角色表
角色权限矩阵
主管角色
PLATFORM_SERVICE 角色
X-API-Key
JWT / Token
OAuth
写接口角色校验
Admin 来源 IP 限制
HSTS 和生产级安全门禁
```

Django Admin 不是参赛主链路。演示数据优先通过 management command 和 JSON 种子文件维护；如保留 Admin，只用于本机调试。

---

## 3. 仍然保留的业务保护

即使测试服务器无鉴权，仍保留：

```text
工单状态机
数据库事务
行级锁（需要时）
唯一约束
重复工单检查
Idempotency-Key（建议）
Request-ID
错误码
操作时间线
周期复位审计
```

原因：这些能力用于保证演示流程稳定，防止平台重试造成重复工单、重复派工或重复周期复位。

---

## 4. 派工与验收调整

### 派工

```text
Django 返回候选人员
→ 平台操作人员选择候选人
→ 平台调用 assign 接口
→ Django 校验人员是否存在、在岗、可用、负荷和技能
→ 保存派工结果
```

Django 不检查选择者是否为主管。

### 验收

```text
平台展示点检结果和知识库验收要求
→ 平台操作人员选择通过、退回或转修模
→ 调用 Django 对应接口
→ Django 只校验工单状态和数据完整性
```

Django 不检查验收者角色。

---

## 5. 接口请求调整

删除：

```http
X-API-Key
Authorization
actor_role
```

保留：

```http
X-Request-ID: <optional>
Idempotency-Key: <recommended-for-write-actions>
Content-Type: application/json
```

写请求可选记录：

```json
{
  "operator_id": "TEST-OPERATOR-01",
  "operator_name": "比赛演示操作员"
}
```

缺少操作人信息时，Django 使用：

```text
operator_id = TEST_PLATFORM
operator_name = 智能体平台
```

---

## 6. 部署简化

参赛测试版默认采用：

```text
一个 Django 服务
SQLite 数据库
端口 18080
HTTP 直接访问
```

推荐启动：

```bash
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:18080
```

也可使用单进程 Gunicorn：

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:18080 --workers 1 --threads 4
```

如比赛平台只允许 HTTPS，可在外部增加反向代理或隧道，但不作为 Django 项目必需组件。

---

## 7. 风险边界

由于没有鉴权：

1. 服务器只能使用 DEMO 数据；
2. 不得接入真实 MES、ERP、邮箱通讯录或生产数据库；
3. 不得将端口长期暴露在互联网并保存真实数据；
4. 比赛结束后应停止服务或限制网络访问；
5. 未来企业落地时必须重新设计登录、权限、认证和安全部署。

---

## 8. 最终结论

```text
主管角色：不实现
业务角色权限：不实现
API 安全鉴权：不实现
业务状态机：保留
幂等和事务：保留
数据性质：DEMO ONLY
部署定位：比赛测试服务器
```

本确认优先于早期实施计划中关于主管角色、API Key、角色权限和生产安全部署的内容。