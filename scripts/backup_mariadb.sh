#!/bin/sh
set -eu

compose_env=${MOLDGUARD_ENV_FILE:-.env.competition}
runtime_dir=${MOLDGUARD_RUNTIME_DIR:-./runtime/competition}
backup_dir=${MOLDGUARD_BACKUP_DIR:-${runtime_dir}/backups}
compose_project=${COMPOSE_PROJECT_NAME:-moldguard-competition}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
target=${backup_dir}/moldguard-competition-${timestamp}.sql.gz
dump_file=
gzip_file=

cleanup() {
    [ -z "$dump_file" ] || rm -f "$dump_file"
    [ -z "$gzip_file" ] || rm -f "$gzip_file"
}

trap cleanup EXIT HUP INT TERM

if [ ! -f "$compose_env" ]; then
    echo "Environment file not found: ${compose_env}" >&2
    exit 2
fi

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
umask 077
[ ! -e "$target" ] || {
    echo "Backup already exists: ${target}" >&2
    exit 1
}

dump_file=$(mktemp "${backup_dir}/.moldguard-competition-${timestamp}.XXXXXX.sql")
gzip_file=$(mktemp "${backup_dir}/.moldguard-competition-${timestamp}.XXXXXX.sql.gz")

COMPOSE_PROJECT_NAME="$compose_project" docker compose --env-file "$compose_env" exec -T mariadb \
    sh -eu -c '
        defaults_file=$(mktemp)
        cleanup_defaults() {
            rm -f "$defaults_file"
        }
        trap cleanup_defaults EXIT HUP INT TERM
        chmod 600 "$defaults_file"
        printf "[client]\nuser=root\npassword=%s\n" "$MARIADB_ROOT_PASSWORD" >"$defaults_file"
        mariadb-dump --defaults-extra-file="$defaults_file" \
            --single-transaction --quick --lock-tables=false --routines --triggers \
            "$MARIADB_DATABASE"
    ' > "$dump_file"

test -s "$dump_file"
gzip -9 -c "$dump_file" > "$gzip_file"
gzip -t "$gzip_file"
test -s "$gzip_file"
chmod 600 "$gzip_file"
mv "$gzip_file" "$target"
gzip_file=

echo "$target"
