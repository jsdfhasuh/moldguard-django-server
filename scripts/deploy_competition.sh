#!/bin/sh
set -eu

compose_env=${MOLDGUARD_ENV_FILE:-.env.competition}
compose_project=${COMPOSE_PROJECT_NAME:-moldguard-competition}
base_url=${MOLDGUARD_LOCAL_BASE_URL:-http://127.0.0.1:18081}

if [ ! -f "$compose_env" ]; then
    echo "Environment file not found: ${compose_env}" >&2
    echo "Copy .env.competition.example to .env.competition and replace placeholders." >&2
    exit 2
fi

if grep -q 'replace-with-' "$compose_env"; then
    echo "Refusing deployment while placeholder secrets remain in ${compose_env}." >&2
    exit 2
fi

export COMPOSE_PROJECT_NAME="$compose_project"

docker compose --env-file "$compose_env" config --quiet
docker compose --env-file "$compose_env" build
docker compose --env-file "$compose_env" run --rm --no-deps api python manage.py check
docker compose --env-file "$compose_env" up -d
docker compose --env-file "$compose_env" ps
docker compose --env-file "$compose_env" logs --tail=200 api
docker compose --env-file "$compose_env" logs --tail=200 mariadb

docker compose --env-file "$compose_env" exec -T api python manage.py migrate --noinput
docker compose --env-file "$compose_env" exec -T api python manage.py seed_demo_data --if-empty

attempt=1
until curl --fail --silent --show-error "${base_url}/api/v1/health" >/dev/null; do
    if [ "$attempt" -ge 30 ]; then
        echo "Competition API did not become healthy after 60 seconds." >&2
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
done

report_base_url=$(docker compose --env-file "$compose_env" exec -T api \
    python -c 'import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); from django.conf import settings; print(settings.MOLDGUARD_PUBLIC_BASE_URL)')
[ -n "$report_base_url" ] || {
    echo "MOLDGUARD_PUBLIC_BASE_URL resolved to an empty value." >&2
    exit 1
}

python3 scripts/smoke_test.py \
    --base-url "$base_url" \
    --report-base-url "$report_base_url" \
    --workflow all \
    --reset-demo \
    --compose-env-file "$compose_env"
