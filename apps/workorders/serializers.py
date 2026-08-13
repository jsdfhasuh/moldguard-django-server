from decimal import Decimal

from rest_framework import serializers


class AssignSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    employee_id = serializers.CharField(max_length=64)


class ClientRequestSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)


class PauseSerializer(ClientRequestSerializer):
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class RemarksSerializer(ClientRequestSerializer):
    remarks = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class KnowledgeItemSerializer(serializers.Serializer):
    knowledge_id = serializers.CharField(max_length=120)
    item = serializers.CharField(max_length=500)
    criteria = serializers.CharField(max_length=2000)
    method = serializers.CharField(max_length=200)
    required = serializers.BooleanField()


class KnowledgeSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    knowledge_snapshot_version = serializers.CharField(max_length=64)
    title = serializers.CharField(max_length=240)
    items = KnowledgeItemSerializer(many=True, allow_empty=False)
    safety_notes = serializers.ListField(
        child=serializers.CharField(max_length=2000), required=False, default=list
    )
    source_documents = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, default=list
    )


class EmailResultSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    status = serializers.ChoiceField(choices=["FAILED", "SENT"])
    message_id = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    sent_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    knowledge_package_hash = serializers.CharField(min_length=64, max_length=64)
    error_message = serializers.CharField(
        max_length=4000, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        if attrs["status"] == "SENT":
            if not attrs.get("message_id", "").strip():
                raise serializers.ValidationError({"message_id": "SENT结果必须提供message_id"})
            if attrs.get("sent_at") is None:
                raise serializers.ValidationError({"sent_at": "SENT结果必须提供sent_at"})
        elif not attrs.get("error_message", "").strip():
            raise serializers.ValidationError({"error_message": "FAILED结果必须提供error_message"})
        return attrs


class InspectionResultSerializer(serializers.Serializer):
    knowledge_id = serializers.CharField(max_length=120)
    result = serializers.ChoiceField(choices=["PASS", "FAIL", "NOT_APPLICABLE"])
    not_applicable_reason = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )
    abnormal_note = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, default=""
    )


class AbnormalItemSerializer(serializers.Serializer):
    item = serializers.CharField(min_length=1, max_length=500, trim_whitespace=True)
    description = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)


class ReportSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    report_type = serializers.ChoiceField(choices=["NORMAL", "ABNORMAL"])
    report_summary = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)
    inspection_results = InspectionResultSerializer(many=True, allow_empty=False)
    abnormal_items = AbnormalItemSerializer(many=True, required=False, default=list)
    photos = serializers.ListField(
        child=serializers.CharField(max_length=2000), required=False, default=list, max_length=10
    )
    parts_replaced = serializers.ListField(
        child=serializers.JSONField(), required=False, default=list, max_length=50
    )
    source_fault_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True, default=None
    )
    actual_work_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("999.99"),
    )
    abnormal_next_action = serializers.ChoiceField(
        choices=["CONTINUE_PROCESSING", "CREATE_REPAIR_TASK"],
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    knowledge_package_hash = serializers.CharField(min_length=64, max_length=64)

    def validate_inspection_results(self, value):
        identifiers = [item["knowledge_id"] for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise serializers.ValidationError("knowledge_id不允许重复")
        return value

    def validate(self, attrs):
        if "employee_id" in self.initial_data:
            raise serializers.ValidationError(
                {"employee_id": "客户端不得提交employee_id，服务器使用工单assignee"}
            )
        return attrs
