from rest_framework import serializers

from .models import MaintenanceAlert, Mold


class MoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mold
        fields = [
            "mold_id",
            "mold_name",
            "mold_type",
            "status",
            "development_tonnage",
            "current_count",
            "cycle_baseline_count",
            "cycle_baseline_time",
            "cycle_version",
            "last_production_at",
            "last_reset_type",
            "last_reset_event_id",
            "created_at",
            "updated_at",
        ]


class MaintenanceAlertSerializer(serializers.ModelSerializer):
    mold_id = serializers.CharField(source="mold.mold_id", read_only=True)

    class Meta:
        model = MaintenanceAlert
        fields = [
            "alert_id",
            "mold_id",
            "alert_type",
            "cycle_version",
            "cycle_count_snapshot",
            "threshold_snapshot",
            "trigger_basis_json",
            "status",
            "created_at",
            "updated_at",
        ]


class AlertScanSerializer(serializers.Serializer):
    mold_ids = serializers.ListField(
        child=serializers.CharField(max_length=40),
        required=False,
        allow_empty=False,
    )
    client_request_id = serializers.CharField(max_length=120, required=False)
