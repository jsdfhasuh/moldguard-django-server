#!/bin/sh
set -eu

compose_env=${MOLDGUARD_ENV_FILE:-.env.competition}
runtime_dir=${MOLDGUARD_RUNTIME_DIR:-./runtime/competition}
backup_dir=${MOLDGUARD_BACKUP_DIR:-${runtime_dir}/backups}
compose_project=${COMPOSE_PROJECT_NAME:-moldguard-competition}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
target=${backup_dir}/moldguard-competition-${timestamp}.sql.gz
dump_file=${backup_dir}/.moldguard-competition-${timestamp}.sql.tmp

if [ ! -f "$compose_env" ]; then
    echo "Environment file not found: ${compose_env}" >&2
    exit 2
fi

mkdir -p "$backup_dir"
umask 077

COMPOSE_PROJECT_NAME="$compose_project" docker compose --env-file "$compose_env" exec -T mariadb \
    sh -c 'exec mariadb-dump --single-transaction --quick --lock-tables=false -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
    > "$dump_file"

test -s "$dump_file"
gzip -c "$dump_file" > "$target"
gzip -t "$target"
test -s "$target"
chmod 600 "$target"
rm -f "$dump_file"
echo "$target"
