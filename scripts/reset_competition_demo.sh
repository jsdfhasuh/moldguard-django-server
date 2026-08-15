#!/bin/sh
set -eu

usage() {
    printf '%s\n' \
        "Usage: scripts/reset_competition_demo.sh" \
        "" \
        "Reset only the moldguard-competition DEMO business data." \
        "Type RESET at the interactive prompt to continue." \
        "This script does not deploy, restart containers, run smoke tests, or send email."
}

case "$#" in
    0)
        ;;
    1)
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            *)
                usage >&2
                exit 2
                ;;
        esac
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

expected_repo=/docker_volume/moldguard-competition-server-v1
script_dir=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
repo_dir=$(CDPATH= cd "${script_dir}/.." && pwd -P)
compose_file=${repo_dir}/compose.yaml
compose_env=${repo_dir}/.env.competition
compose_project=moldguard-competition
base_url=http://127.0.0.1:18081
settle_seconds=20

if [ "$repo_dir" != "$expected_repo" ]; then
    echo "Refusing to reset from repository: ${repo_dir}" >&2
    echo "Required repository: ${expected_repo}" >&2
    exit 2
fi

if [ ! -f "$compose_file" ]; then
    echo "Compose file not found: ${compose_file}" >&2
    exit 2
fi

if [ ! -f "$compose_env" ]; then
    echo "Environment file not found: ${compose_env}" >&2
    exit 2
fi

if grep -q 'replace-with-' "$compose_env"; then
    echo "Refusing reset while placeholder secrets remain in ${compose_env}." >&2
    exit 2
fi

compose() {
    docker compose \
        --project-name "$compose_project" \
        --env-file "$compose_env" \
        -f "$compose_file" \
        "$@"
}

verify_competition_health() {
    health_body=$(curl --fail --silent --show-error "${base_url}/api/v1/health")
    case "$health_body" in
        *'"service":"moldguard-competition-server"'*)
            ;;
        *)
            echo "The local health endpoint is not the competition service." >&2
            exit 2
            ;;
    esac
}

compose config --quiet

if ! compose exec -T api true; then
    echo "The competition API container is not running." >&2
    exit 2
fi

verify_competition_health

if [ ! -t 0 ]; then
    echo "Interactive confirmation is required." >&2
    exit 2
fi

printf '%s\n' \
    "Repository: ${repo_dir}" \
    "Compose project: ${compose_project}" \
    "This deletes all competition DEMO work orders, alerts, maintenance records," \
    "employees, molds, idempotency records, and associated report evidence." \
    "It then restores the canonical 10 molds and 4 employees."
printf 'Type RESET to continue: '
IFS= read -r confirmation
if [ "$confirmation" != "RESET" ]; then
    echo "Reset cancelled."
    exit 1
fi

echo "Resetting ${compose_project} DEMO data..."
compose exec -T api python manage.py reset_demo_data --confirm

compose exec -T api python manage.py verify_demo_data

verify_clean_counts() {
    compose exec -T api python manage.py shell -c '
from apps.common.models import ClientRequestRecord
from apps.molds.models import Alert, Mold
from apps.staff.models import Employee
from apps.workorders.models import (
    MaintenanceRecord,
    ReportEvidence,
    ReportSubmission,
    WorkOrder,
    WorkOrderEvent,
)

counts = {
    "molds": Mold.objects.count(),
    "employees": Employee.objects.count(),
    "work_orders": WorkOrder.objects.count(),
    "alerts": Alert.objects.count(),
    "maintenance_records": MaintenanceRecord.objects.count(),
    "work_order_events": WorkOrderEvent.objects.count(),
    "report_submissions": ReportSubmission.objects.count(),
    "report_evidence": ReportEvidence.objects.count(),
    "idempotency_records": ClientRequestRecord.objects.count(),
}
expected = {
    "molds": 10,
    "employees": 4,
    "work_orders": 0,
    "alerts": 0,
    "maintenance_records": 0,
    "work_order_events": 0,
    "report_submissions": 0,
    "report_evidence": 0,
    "idempotency_records": 0,
}
print("Post-reset counts:", counts)
if counts != expected:
    raise SystemExit(
        "Post-reset data is not clean. Stop or wait for the running platform flow, "
        "then run this script again."
    )
'
}

verify_clean_counts
echo "Waiting ${settle_seconds}s for a second late-write check..."
sleep "$settle_seconds"
verify_clean_counts
verify_competition_health

echo "Competition DEMO data reset and verification completed successfully."
