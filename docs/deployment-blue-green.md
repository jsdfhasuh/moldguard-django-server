# MoldGuard 比赛服务器蓝绿部署与回退

本运行手册适用于同一 Oracle Linux 主机上的两套并行服务：

```text
旧栈：moldguard             → 127.0.0.1:18080
新栈：moldguard-competition → 127.0.0.1:18081
正式域名：moldguard.oracle.19970219.xyz
```

旧栈、旧 MariaDB 目录和旧容器卷在比赛部署期间不得删除。禁止执行
`docker compose down -v`。

## 1. 准备 competition 环境

```bash
scripts/create_competition_env.sh
chmod 600 .env.competition
COMPOSE_PROJECT_NAME=moldguard-competition \
docker compose --env-file .env.competition config --quiet
```

生成脚本只在 `.env.competition` 不存在时创建文件，不会覆盖既有配置，也不会打印密钥。

部署前必须填写真实 SMTP 与比赛测试收件邮箱：

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
EMAIL_USE_TLS或EMAIL_USE_SSL（二选一或均关闭）
EMAIL_TIMEOUT=15
DEFAULT_FROM_EMAIL
EMAIL_MESSAGE_ID_DOMAIN
MOLDGUARD_SMTP_DELIVERY_VERIFIED=false
DEMO_EMPLOYEE_1_EMAIL ... DEMO_EMPLOYEE_4_EMAIL
MARIADB_HOST_BIND=127.0.0.1
MARIADB_HOST_PORT=13306
```

Compose 固定设置 `MOLDGUARD_REQUIRE_SMTP=true`，会拒绝 locmem/console、示例SMTP主机、
示例发件人和示例Message-ID域。`EMAIL_USE_TLS` 与 `EMAIL_USE_SSL` 同时为true时Django
启动失败。任何日志、命令回显和工单API均不得输出 SMTP 密码。

## 2. 并行部署与验证

```bash
COMPOSE_PROJECT_NAME=moldguard-competition \
scripts/deploy_competition.sh

curl -f http://127.0.0.1:18081/api/v1/health
curl -f http://127.0.0.1:18081/api/v1/meta
```

部署 smoke 会调用 `send-email` 并向当前 DEMO 工单被派工邮箱真实发送邮件。执行前必须
确认这些地址是授权测试邮箱。HTTP 200 与 `email_status=SENT` 只证明 SMTP 后端接受了
邮件；最终送达还必须人工检查收件箱中的纯文本/HTML内容、Message-ID、知识哈希和
`report_url`。只有人工确认实际送达后，才可把
`MOLDGUARD_SMTP_DELIVERY_VERIFIED` 改为 `true`；`/api/v1/meta` 随后才会报告
`READY_FOR_COMPETITION`。

新 MariaDB 固定使用 `runtime/competition/mariadb`，不得指向旧仓库的
`runtime/mariadb`。

MariaDB 宿主映射由 `MARIADB_HOST_BIND` 和 `MARIADB_HOST_PORT` 控制，示例默认只监听
`127.0.0.1:13306`。如测试环境明确需要公网访问，可显式设置为 `0.0.0.0:3306`，并在
主机防火墙和 Oracle Cloud 入站规则中同步放行 TCP 3306。公网 root 登录不应用于真实
生产数据。

## 3. 切换前备份

旧数据库在旧仓库执行：

```bash
cd /docker_volume/moldguard-django-server
scripts/backup_mariadb.sh
```

新数据库在 competition 仓库执行：

```bash
cd /docker_volume/moldguard-competition-server-v1
COMPOSE_PROJECT_NAME=moldguard-competition scripts/backup_mariadb.sh
```

同时保存 `docker compose ls`、`docker ps`、端口清单，并备份当前 Nginx 配置：

```bash
cp --preserve=mode,ownership,timestamps \
  /etc/nginx/conf.d/out/moldguard.conf \
  /etc/nginx/conf.d/out/moldguard.conf.before-competition
```

## 4. Nginx 切换

只有新栈测试和备份全部通过后才执行：

```bash
cp deploy/nginx/moldguard-competition.conf /etc/nginx/conf.d/out/moldguard.conf
nginx -t
systemctl reload nginx
```

Nginx 是优雅 reload；验证前应等待旧 worker 完全退出，再连续检查 health/meta
确实返回 `service=moldguard-competition-server`。

```bash
curl -f https://moldguard.oracle.19970219.xyz/api/v1/health
curl -f https://moldguard.oracle.19970219.xyz/api/v1/meta
curl -f https://moldguard.oracle.19970219.xyz/api/docs
```

随后运行正式域名 smoke：

```bash
COMPOSE_PROJECT_NAME=moldguard-competition \
python3 scripts/smoke_test.py \
  --base-url https://moldguard.oracle.19970219.xyz \
  --workflow all \
  --reset-demo \
  --compose-env-file .env.competition
```

## 5. 回退

任一步失败立即执行：

```bash
MOLDGUARD_NGINX_BACKUP=/etc/nginx/conf.d/out/moldguard.conf.before-competition \
scripts/rollback_competition.sh
```

回退脚本恢复旧配置、运行 `nginx -t`、reload，并检查旧 `18080` health。新栈和新
MariaDB 保留用于调试，不删除任何卷。

旧 API 如被人工停止，恢复命令为：

```bash
cd /docker_volume/moldguard-django-server && docker compose up -d api
```
