from decimal import Decimal

from rest_framework import serializers


class StrictBooleanField(serializers.BooleanField):
    default_error_messages = {"invalid": "必须是JSON布尔值。"}

    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid", input=data)
        return data


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
    criteria = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    method = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    required = StrictBooleanField()
    title = serializers.CharField(max_length=240, required=False, allow_blank=True)
    knowledge_type = serializers.CharField(max_length=120, required=False, allow_blank=True)
    content = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    source = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        content = attrs.get("content", "")
        if not attrs["criteria"] and not content:
            raise serializers.ValidationError("criteria和content至少填写一个")
        if not attrs["criteria"]:
            attrs["criteria"] = content
        return attrs


class KnowledgeSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    knowledge_snapshot_version = serializers.CharField(max_length=64, required=False)
    catalog_version = serializers.CharField(max_length=64, required=False, write_only=True)
    title = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    items = KnowledgeItemSerializer(many=True, allow_empty=False)
    safety_notes = serializers.ListField(
        child=serializers.CharField(max_length=2000), required=False, default=list
    )
    source_documents = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, default=list
    )

    def validate(self, attrs):
        catalog_version = attrs.pop("catalog_version", "")
        snapshot_version = attrs.get("knowledge_snapshot_version", "")
        if catalog_version and snapshot_version and catalog_version != snapshot_version:
            raise serializers.ValidationError(
                {"catalog_version": "catalog_version与knowledge_snapshot_version必须一致"}
            )
        version = snapshot_version or catalog_version
        if not version:
            raise serializers.ValidationError(
                {
                    "knowledge_snapshot_version": (
                        "必须提供knowledge_snapshot_version或catalog_version"
                    )
                }
            )
        attrs["knowledge_snapshot_version"] = version

        if catalog_version:
            required_platform_fields = ("title", "knowledge_type", "content", "source")
            item_errors = {}
            for index, item in enumerate(attrs["items"]):
                missing = [field for field in required_platform_fields if not item.get(field)]
                if missing:
                    item_errors[index] = f"平台知识项缺少字段：{', '.join(missing)}"
            if item_errors:
                raise serializers.ValidationError({"items": item_errors})

            for item in attrs["items"]:
                item["criteria"] = item["content"]

            if not attrs["title"]:
                first_title = attrs["items"][0]["title"]
                suffix = f"等{len(attrs['items'])}项" if len(attrs["items"]) > 1 else ""
                attrs["title"] = f"{first_title}{suffix}"[:240]
            if not attrs["source_documents"]:
                attrs["source_documents"] = list(
                    dict.fromkeys(item["source"] for item in attrs["items"])
                )
        elif not attrs["title"]:
            raise serializers.ValidationError({"title": "知识包title不能为空"})

        return attrs


class SendEmailSerializer(ClientRequestSerializer):
    def validate(self, attrs):
        unexpected = sorted(set(self.initial_data) - {"client_request_id"})
        if unexpected:
            raise serializers.ValidationError(
                {name: ["send-email不接受此字段"] for name in unexpected}
            )
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


class ReportSubmissionCreateSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    report_text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)
    actual_work_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("999.99"),
    )
    images = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        max_length=10,
        write_only=True,
    )
    parts_replaced = serializers.ListField(
        child=serializers.JSONField(), required=False, default=list, max_length=50
    )
    source_fault_id = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True, default=None
    )
    knowledge_package_hash = serializers.CharField(min_length=64, max_length=64)

    def validate(self, attrs):
        unexpected_fields = sorted(
            {
                "employee_id",
                "assignee_id",
                "work_order_id",
                "source",
                "image_urls",
            }.intersection(self.initial_data)
        )
        if unexpected_fields:
            raise serializers.ValidationError(
                {name: "Django报工页面不接受此字段" for name in unexpected_fields}
            )
        return attrs


class ReportReviewSerializer(serializers.Serializer):
    client_request_id = serializers.CharField(max_length=120)
    decision = serializers.ChoiceField(choices=["COMPLETE", "ABNORMAL", "NEEDS_MORE_INFO"])
    assessment_summary = serializers.CharField(min_length=1, max_length=4000, trim_whitespace=True)
    confidence = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        min_value=Decimal("0"),
        max_value=Decimal("1"),
    )
    knowledge_package_hash = serializers.CharField(min_length=64, max_length=64)
    inspection_results = InspectionResultSerializer(many=True, required=False, default=list)
    abnormal_items = AbnormalItemSerializer(many=True, required=False, default=list)
    abnormal_next_action = serializers.ChoiceField(
        choices=["CONTINUE_PROCESSING", "CREATE_REPAIR_TASK"],
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    reason_codes = serializers.ListField(
        child=serializers.CharField(max_length=120), required=False, default=list, max_length=20
    )
    knowledge_sources = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False, default=list, max_length=20
    )
    review_model = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=""
    )

    def validate_inspection_results(self, value):
        identifiers = [item["knowledge_id"] for item in value]
        if len(identifiers) != len(set(identifiers)):
            raise serializers.ValidationError("knowledge_id不允许重复")
        return value

    def validate(self, attrs):
        unexpected = sorted(
            {"employee_id", "assignee_id", "work_order_id", "report_type"}.intersection(
                self.initial_data
            )
        )
        if unexpected:
            raise serializers.ValidationError(
                {name: "AI审核不得覆盖Django权威身份或状态字段" for name in unexpected}
            )
        decision = attrs["decision"]
        results = attrs.get("inspection_results", [])
        if decision != "NEEDS_MORE_INFO" and not results:
            raise serializers.ValidationError(
                {"inspection_results": "完成或异常建议必须提供逐项点检结论"}
            )
        if decision == "COMPLETE":
            if any(item["result"] == "FAIL" for item in results):
                raise serializers.ValidationError(
                    {"inspection_results": "COMPLETE建议不得包含FAIL点检项"}
                )
            if attrs.get("abnormal_items"):
                raise serializers.ValidationError(
                    {"abnormal_items": "COMPLETE建议不得包含异常项目"}
                )
            if attrs.get("abnormal_next_action"):
                raise serializers.ValidationError(
                    {"abnormal_next_action": "COMPLETE建议不得包含异常后续动作"}
                )
        elif decision == "ABNORMAL":
            has_fail = any(item["result"] == "FAIL" for item in results)
            if not has_fail and not attrs.get("abnormal_items"):
                raise serializers.ValidationError(
                    {"abnormal_items": "ABNORMAL建议必须包含FAIL点检项或异常项目"}
                )
            if not attrs.get("abnormal_next_action"):
                raise serializers.ValidationError(
                    {"abnormal_next_action": "ABNORMAL建议必须指定后续动作"}
                )
        return attrs
