from rest_framework import serializers

from .models import (
    Employee,
    KnowledgeSnapshot,
    MaintenanceAlert,
    Mold,
    NotificationReceipt,
    WorkOrder,
    WorkOrderEvent,
)


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


class KnowledgeItemSerializer(serializers.Serializer):
    knowledge_id = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=240, required=False, allow_blank=True)
    item = serializers.CharField(max_length=500)
    knowledge_type = serializers.CharField(max_length=80, required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(max_length=240, required=False, allow_blank=True)
    required = serializers.BooleanField(default=True)


class KnowledgeSnapshotCreateSerializer(serializers.Serializer):
    catalog_version = serializers.CharField(max_length=80)
    items = KnowledgeItemSerializer(many=True, allow_empty=False)
    client_request_id = serializers.CharField(max_length=120)


class KnowledgeSnapshotSerializer(serializers.ModelSerializer):
    items = serializers.JSONField(source="items_json")

    class Meta:
        model = KnowledgeSnapshot
        fields = ["snapshot_id", "catalog_version", "items", "created_at"]


class NotificationCreateSerializer(serializers.Serializer):
    recipient = serializers.EmailField(required=False)
    status = serializers.ChoiceField(choices=NotificationReceipt.Status.choices)
    message_id = serializers.CharField(max_length=160, required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    sent_at = serializers.DateTimeField(required=False, allow_null=True)
    client_request_id = serializers.CharField(max_length=120)

    def validate(self, attrs):
        if attrs["status"] == NotificationReceipt.Status.SENT and not attrs.get("message_id"):
            raise serializers.ValidationError({"message_id": "发送成功时必须填写消息ID"})
        if attrs["status"] == NotificationReceipt.Status.FAILED and not attrs.get("error_message"):
            raise serializers.ValidationError({"error_message": "发送失败时必须填写失败原因"})
        return attrs


class NotificationReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationReceipt
        fields = [
            "notification_id",
            "recipient",
            "status",
            "message_id",
            "error_message",
            "sent_at",
            "created_at",
        ]
