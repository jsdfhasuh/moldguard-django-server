#!/bin/sh
set -eu

nginx_config=${MOLDGUARD_NGINX_CONFIG:-/etc/nginx/conf.d/out/moldguard.conf}
backup_config=${MOLDGUARD_NGINX_BACKUP:-${nginx_config}.before-competition}
old_health=${MOLDGUARD_OLD_HEALTH_URL:-http://127.0.0.1:18080/api/v1/health}

if [ ! -f "$backup_config" ]; then
    echo "Rollback backup not found: ${backup_config}" >&2
    exit 2
fi

cp "$backup_config" "$nginx_config"
nginx -t
systemctl reload nginx
curl --fail --silent --show-error "$old_health" >/dev/null

echo "Nginx restored from ${backup_config}; old service health is OK."
echo "The competition containers and database were intentionally left running."
