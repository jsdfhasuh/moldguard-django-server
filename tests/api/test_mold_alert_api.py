import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.platform_probe.models import MaintenanceAlert, Mold


@pytest.fixture
def seeded_molds(db):
    call_command("seed_probe_data", verbosity=0)


@pytest.mark.django_db
def test_seed_and_verify_management_commands(seeded_molds):
    assert Mold.objects.count() == 7
    call_command("verify_probe_data", verbosity=0)


@pytest.mark.django_db
def test_seed_if_empty_does_not_overwrite_existing_demo_data(seeded_molds):
    mold = Mold.objects.get(pk="MOLD-TEST-001")
    mold.mold_name = "保留现有部署数据"
    mold.save(update_fields=["mold_name", "updated_at"])

    call_command("seed_probe_data", if_empty=True, verbosity=0)

    assert Mold.objects.get(pk="MOLD-TEST-001").mold_name == "保留现有部署数据"


@pytest.mark.django_db
def test_mold_list_detail_and_status(seeded_molds, api_client):
    listing = api_client.get("/api/v1/molds")
    detail = api_client.get("/api/v1/molds/MOLD-TEST-001")
    status = api_client.get("/api/v1/molds/MOLD-TEST-001/maintenance-status")

    assert listing.status_code == 200
    assert len(listing.data["data"]["molds"]) == 7
    assert detail.data["data"]["development_tonnage"] == 850
    assert status.data["data"]["threshold"] == 50_000
    assert status.data["data"]["maintenance_due"] is True


@pytest.mark.django_db
def test_missing_tonnage_and_invalid_count_use_named_errors(api_client):
    now = timezone.now()
    mold = Mold.objects.create(
        mold_id="MOLD-NEGATIVE",
        mold_name="负模次模具",
        mold_type=Mold.MoldType.INJECTION,
        development_tonnage=850,
        current_count=10,
        cycle_baseline_count=11,
        cycle_baseline_time=now,
    )
    missing = api_client.get("/api/v1/molds/DOES-NOT-EXIST")
    invalid = api_client.get(f"/api/v1/molds/{mold.mold_id}/maintenance-status")

    assert missing.status_code == 404
    assert missing.data["code"] == "MOLD_NOT_FOUND"
    assert invalid.status_code == 400
    assert invalid.data["code"] == "INVALID_CYCLE_COUNT"


@pytest.mark.django_db
def test_scan_creates_expected_alerts_without_duplicates(seeded_molds, api_client):
    first = api_client.post(
        "/api/v1/alerts/scan", {"client_request_id": "scan-first"}, format="json"
    )
    first_count = MaintenanceAlert.objects.count()
    second = api_client.post(
        "/api/v1/alerts/scan", {"client_request_id": "scan-second"}, format="json"
    )

    assert first.status_code == 200
    assert first_count == 5
    assert len(first.data["data"]["created_alert_ids"]) == 5
    assert second.status_code == 200
    assert second.data["data"]["created_alert_ids"] == []
    assert MaintenanceAlert.objects.count() == first_count

    mold_three = next(
        item for item in first.data["data"]["results"] if item["mold_id"] == "MOLD-TEST-003"
    )
    mold_four = next(
        item for item in first.data["data"]["results"] if item["mold_id"] == "MOLD-TEST-004"
    )
    mold_six = next(
        item for item in first.data["data"]["results"] if item["mold_id"] == "MOLD-TEST-006"
    )
    assert mold_three["result"] == "TWO_MONTH_REMINDER"
    assert mold_three["messages"] == ["仅表示已满2个月，不代表模次保养条件已达到。"]
    assert mold_four["result"] == "IDLE_AUTO_REMINDER_DISABLED"
    assert mold_six["result"] == "DEVELOPMENT_TONNAGE_NOT_CONFIGURED"
    assert not MaintenanceAlert.objects.filter(
        mold_id="MOLD-TEST-004", alert_type=MaintenanceAlert.AlertType.MAINTENANCE_DUE
    ).exists()


@pytest.mark.django_db
def test_alert_list_and_not_found_contract(seeded_molds, api_client):
    api_client.post("/api/v1/alerts/scan", {"client_request_id": "scan-alert-list"}, format="json")
    listing = api_client.get("/api/v1/alerts?alert_type=TWO_MONTH_REMINDER")
    missing = api_client.get("/api/v1/alerts/ALT-NOT-FOUND")

    assert listing.status_code == 200
    assert len(listing.data["data"]["alerts"]) == 1
    assert listing.data["data"]["alerts"][0]["mold_id"] == "MOLD-TEST-003"
    assert missing.status_code == 404
    assert missing.data["code"] == "ALERT_NOT_FOUND"
