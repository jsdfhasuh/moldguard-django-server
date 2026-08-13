#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backup_dir=${MOLDGUARD_BACKUP_DIR:-"$project_dir/runtime/backups"}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_path="$backup_dir/moldguard-$timestamp.sql.gz"
sql_tmp=
gzip_tmp=

cleanup() {
    [ -z "$sql_tmp" ] || rm -f "$sql_tmp"
    [ -z "$gzip_tmp" ] || rm -f "$gzip_tmp"
}

trap cleanup EXIT HUP INT TERM

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
[ ! -e "$backup_path" ] || {
    echo "Backup already exists: $backup_path" >&2
    exit 1
}

sql_tmp=$(mktemp "$backup_dir/.moldguard-$timestamp.XXXXXX.sql")
gzip_tmp=$(mktemp "$backup_dir/.moldguard-$timestamp.XXXXXX.sql.gz")

cd "$project_dir"
docker compose exec -T mariadb sh -eu -c '
    defaults_file=$(mktemp)
    cleanup_defaults() {
        rm -f "$defaults_file"
    }
    trap cleanup_defaults EXIT HUP INT TERM
    chmod 600 "$defaults_file"
    printf "[client]\nuser=root\npassword=%s\n" "$MARIADB_ROOT_PASSWORD" >"$defaults_file"
    mariadb-dump --defaults-extra-file="$defaults_file" \
        --single-transaction --quick --routines --triggers "$MARIADB_DATABASE"
' >"$sql_tmp"

[ -s "$sql_tmp" ] || {
    echo "MariaDB dump was empty; refusing to create a backup." >&2
    exit 1
}

gzip -9 -c "$sql_tmp" >"$gzip_tmp"
gzip -t "$gzip_tmp"
chmod 600 "$gzip_tmp"
mv "$gzip_tmp" "$backup_path"
gzip_tmp=

printf '%s\n' "$backup_path"
