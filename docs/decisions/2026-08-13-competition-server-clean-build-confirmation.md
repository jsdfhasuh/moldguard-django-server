# MoldGuard 比赛服务器干净重建确认

- **状态**：`OWNER_CONFIRMED`
- **日期**：2026-08-13
- **目标分支**：`agent/competition-server-v1`
- **完整计划**：V5.0

## 1. 确认结论

比赛服务器不采用“快速改造测试分支”的方式实施。

正式实现必须：

```text
从main创建新分支
按MOLDGUARD-KB-1.2和V5.0重新编码
建立新的Django应用、模型和初始迁移
```

## 2. 测试分支定位

参考分支：

```text
agent/platform-capability-probe-v1@2ed0b59bbf74c5171860481ab2b1de2294bbfc9d
```

允许参考：

- 统一JSON响应；
- Request-ID；
- client_request_id幂等思想；
- 数据库事务和行锁；
- 自动化测试组织；
- Docker Compose、MariaDB、Gunicorn和Nginx部署经验；
- 种子、重置、验证和冒烟测试思路。

禁止：

- 合并测试分支；
- cherry-pick测试分支提交；
- 复制旧迁移；
- 继续使用platform_probe应用；
- 继续暴露/probe接口；
- 继承旧触发规则、旧字段或旧异常报工模型。

## 3. 权威基线

```text
MOLDGUARD-KB-1.2
→ Django完整实施计划V5.0
→ 模型字段V3.0
→ REPORT-FORM-1.0
```

快速实施计划V1.0已废止并从仓库删除。
