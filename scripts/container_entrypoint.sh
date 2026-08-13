#!/bin/sh
set -eu

attempt=1
max_attempts=30

until python manage.py migrate --noinput; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Database migration failed after ${max_attempts} attempts." >&2
        exit 1
    fi
    echo "Database is not ready (attempt ${attempt}/${max_attempts}); retrying in 2 seconds."
    attempt=$((attempt + 1))
    sleep 2
done

python manage.py seed_demo_data --if-empty

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:18080 \
    --workers 1 \
    --threads 4 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
