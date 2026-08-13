from rest_framework import serializers

from .models import Employee, MaintenanceAlert, Mold, WorkOrder, WorkOrderEvent


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


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "employee_id",
            "employee_name",
            "email",
            "team",
            "skill_tags",
            "available",
            "current_load",
        ]


class WorkOrderSerializer(serializers.ModelSerializer):
    mold = MoldSerializer(read_only=True)
    alert_id = serializers.CharField(source="alert.alert_id", read_only=True)
    assigned_employee = EmployeeSerializer(read_only=True)

    class Meta:
        model = WorkOrder
        fields = [
            "work_order_id",
            "alert_id",
            "mold",
            "status",
            "assigned_employee",
            "assigned_at",
            "started_at",
            "completed_at",
            "required_finish_at",
            "knowledge_profile_code",
            "created_at",
            "updated_at",
        ]


class CreateWorkOrderSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)


class AssignSerializer(serializers.Serializer):
    employee_id = serializers.CharField(max_length=40)
    client_request_id = serializers.CharField(max_length=120)


class AutoAssignSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)


class WorkOrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrderEvent
        fields = ["event_id", "event_type", "event_data_json", "occurred_at", "created_at"]
