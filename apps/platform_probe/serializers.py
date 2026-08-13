from rest_framework import serializers

from .models import (
    AbnormalReport,
    Employee,
    KnowledgeSnapshot,
    MaintenanceAlert,
    MaintenanceHistory,
    Mold,
    NotificationReceipt,
    PauseSegment,
    ProbeRun,
    ProbeStep,
    WorkOrder,
    WorkOrderEvent,
    WorkReport,
)


class OpenAPIEnvelopeSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    data = serializers.JSONField()
    request_id = serializers.CharField()


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
    client_request_id = serializers.CharField(max_length=120)


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


class EmployeeActionSerializer(serializers.Serializer):
    employee_id = serializers.CharField(max_length=40)
    occurred_at = serializers.DateTimeField(required=False)
    client_request_id = serializers.CharField(max_length=120)


class PauseActionSerializer(EmployeeActionSerializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class InspectionResultSerializer(serializers.Serializer):
    knowledge_id = serializers.CharField(max_length=120)
    item = serializers.CharField(max_length=500)
    result = serializers.ChoiceField(choices=["PASS", "FAIL", "NOT_APPLICABLE"])
    note = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class CompleteReportSerializer(serializers.Serializer):
    employee_id = serializers.CharField(max_length=40)
    started_at = serializers.DateTimeField(required=False)
    completed_at = serializers.DateTimeField()
    work_summary = serializers.CharField()
    inspection_results = InspectionResultSerializer(many=True, allow_empty=False)
    attachments = serializers.ListField(child=serializers.JSONField(), required=False, default=list)
    client_request_id = serializers.CharField(max_length=120)

    def validate_inspection_results(self, items):
        knowledge_ids = [item["knowledge_id"] for item in items]
        if len(knowledge_ids) != len(set(knowledge_ids)):
            raise serializers.ValidationError("点检结果中knowledge_id不能重复")
        return items


class AbnormalReportCreateSerializer(serializers.Serializer):
    employee_id = serializers.CharField(max_length=40)
    abnormal_type = serializers.CharField(max_length=100, allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    inspection_results = InspectionResultSerializer(many=True, allow_empty=False)
    started_at = serializers.DateTimeField(required=False)
    completed_at = serializers.DateTimeField(required=False)
    client_request_id = serializers.CharField(max_length=120)


class PauseSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PauseSegment
        fields = ["pause_id", "paused_at", "resumed_at", "reason", "created_at"]


class WorkReportSerializer(serializers.ModelSerializer):
    inspection_results = serializers.JSONField(source="inspection_results_json")
    attachments = serializers.JSONField(source="attachments_json")
    employee_id = serializers.CharField(source="employee.employee_id")

    class Meta:
        model = WorkReport
        fields = [
            "report_id",
            "employee_id",
            "report_type",
            "started_at",
            "completed_at",
            "paused_seconds",
            "actual_minutes",
            "work_summary",
            "inspection_results",
            "attachments",
            "cycle_reset",
            "client_request_id",
            "created_at",
        ]


class AbnormalReportSerializer(serializers.ModelSerializer):
    inspection_results = serializers.JSONField(source="inspection_results_json")

    class Meta:
        model = AbnormalReport
        fields = [
            "abnormal_report_id",
            "abnormal_type",
            "description",
            "inspection_results",
            "client_request_id",
            "created_at",
        ]


class MaintenanceHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceHistory
        fields = [
            "history_id",
            "event_type",
            "count_snapshot",
            "occurred_at",
            "cycle_version_before",
            "cycle_version_after",
            "created_at",
        ]


class ProbeRunCreateSerializer(serializers.Serializer):
    platform_name = serializers.CharField(max_length=120)
    tester = serializers.CharField(max_length=120)
    mode = serializers.ChoiceField(choices=ProbeRun.Mode.choices)
    client_request_id = serializers.CharField(max_length=120)


class CapabilityResultSerializer(serializers.Serializer):
    capability_code = serializers.ChoiceField(
        choices=[f"P{index:02d}" for index in range(5, 12)] + ["P13"]
    )
    status = serializers.ChoiceField(choices=ProbeStep.Status.choices)
    evidence = serializers.CharField(required=False, allow_blank=True)
    impact = serializers.CharField(required=False, allow_blank=True)


class ProbeVariableTestSerializer(serializers.Serializer):
    dynamic_variables = serializers.JSONField()
    nested_json = serializers.JSONField()
    array_items = serializers.ListField(child=serializers.JSONField())
    capability_results = CapabilityResultSerializer(many=True, required=False, default=list)
    client_request_id = serializers.CharField(max_length=120)

    def validate_capability_results(self, items):
        codes = [item["capability_code"] for item in items]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("capability_code不能重复")
        mode = self.context["probe_run"].mode
        if mode == ProbeRun.Mode.STRICT and any(
            item["status"] == ProbeStep.Status.PASS_WITH_ADAPTER for item in items
        ):
            raise serializers.ValidationError("STRICT模式不能标记PASS_WITH_ADAPTER")
        return items


class SchedulerHeartbeatSerializer(serializers.Serializer):
    run_id = serializers.CharField(max_length=40)
    platform_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    heartbeat_at = serializers.DateTimeField(required=False)
    evidence = serializers.CharField(required=False, allow_blank=True)
    client_request_id = serializers.CharField(max_length=120)
