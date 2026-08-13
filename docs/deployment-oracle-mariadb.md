# Oracle 主机 Docker + MariaDB 部署说明

生产部署由 `compose.yaml` 管理：

```text
Nginx → 127.0.0.1:18080 → moldguard-api → 私有Docker网络 → moldguard-mariadb
                                                             ↓
                                                  runtime/mariadb
```

MariaDB 不暴露宿主端口。数据库文件、备份和 `.env` 均被 Git 忽略。
API 与 MariaDB 的 Docker 日志均限制为最多 3 个、每个 10 MB。

## 首次部署

在仓库根目录创建权限为 `600` 的 `.env`，至少设置：

```dotenv
DJANGO_SECRET_KEY=<随机值>
DJANGO_ALLOWED_HOSTS=moldguard.oracle.19970219.xyz,161.118.244.30,127.0.0.1,localhost
MARIADB_DATABASE=moldguard
MARIADB_USER=moldguard
MARIADB_PASSWORD=<随机值>
MARIADB_ROOT_PASSWORD=<不同的随机值>
```

随后执行：

```bash
mkdir -p runtime/mariadb runtime/backups
chmod 700 runtime runtime/mariadb runtime/backups
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:18080/api/v1/health
```

应用启动时会等待 MariaDB 健康，运行迁移，并且仅在业务表为空时写入演示数据。首次部署后应执行一次 `verify_probe_data`；重启容器不会重新覆盖或要求业务数据保持初始状态。

## Nginx

仓库模板位于 `deploy/nginx/moldguard.conf`。本机部署位置：

```bash
sudo install -m 644 deploy/nginx/moldguard.conf /etc/nginx/conf.d/out/moldguard.conf
sudo nginx -t
sudo systemctl reload nginx
```

HTTP 可通过主机公网 IP 访问。HTTPS 使用 `moldguard.oracle.19970219.xyz` 和现有通配证书；该主机名必须先在 DNS 中添加指向 Oracle 主机公网 IPv4/IPv6 的记录。

## 常用运维

```bash
# 状态与日志
docker compose ps
docker compose logs --tail=200 api
docker compose logs --tail=200 mariadb

# 重启
docker compose restart

# 更新代码后重建应用
git pull --ff-only
docker compose up -d --build

# Django 检查与数据校验
docker compose exec api python manage.py check
docker compose exec api python manage.py verify_probe_data
```

## 备份

```bash
./scripts/backup_mariadb.sh
```

备份默认写入 `runtime/backups/moldguard-<UTC时间>.sql.gz`，脚本完成前会执行 gzip 完整性校验。

建议把该命令加入 root 的定时任务，并将备份同步到另一台主机或对象存储。仅保存在同一块系统盘上的备份不能防止主机或磁盘故障。

## 恢复

恢复会覆盖当前数据库，必须先确认备份路径并停止 API 写入：

```bash
docker compose stop api
gzip -dc runtime/backups/moldguard-YYYYMMDDTHHMMSSZ.sql.gz \
  | docker compose exec -T mariadb sh -c \
    'exec mariadb --user=root --password="$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"'
docker compose start api
```

恢复后执行：

```bash
docker compose exec api python manage.py migrate --noinput
docker compose exec api python manage.py verify_probe_data
curl http://127.0.0.1:18080/api/v1/health
```
