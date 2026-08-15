import base64
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _Field:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self):
        return dict(self.__dict__)


class _Component:
    def __init__(self, *args, **kwargs):
        self.status = None
        self.stopped_output = None

    def stop(self, output_name):
        self.stopped_output = output_name


class _Data:
    def __init__(self, data=None, text="", **kwargs):
        self.data = data or {}
        self.text = text

    def get_text(self):
        return self.text or str(self.data.get("text", ""))


class _Message:
    def __init__(self, text="", content="", data=None, **kwargs):
        self.text = text or content
        self.data = data or {}
        self.files = kwargs.get("files", [])


class _HumanMessage:
    def __init__(self, content):
        self.content = content


class _ProviderComponent:
    display_name = "豆包AI"
    last_kwargs = None
    model = None

    @classmethod
    def set(cls, **kwargs):
        instance = cls()
        cls.last_kwargs = kwargs
        instance.kwargs = kwargs
        instance.model = cls.model
        return instance

    def build_model(self):
        return getattr(self, "model", None)


def _install_langflow_stubs():
    langflow = types.ModuleType("langflow")
    custom = types.ModuleType("langflow.custom")
    io = types.ModuleType("langflow.io")
    schema = types.ModuleType("langflow.schema")
    schema_message = types.ModuleType("langflow.schema.message")
    langflow_base = types.ModuleType("langflow.base")
    langflow_base_models = types.ModuleType("langflow.base.models")
    model_constants = types.ModuleType("langflow.base.models.model_input_constants")
    langflow_helpers = types.ModuleType("langflow.helpers")
    global_api_key = types.ModuleType("langflow.helpers.global_api_key")
    langchain_core = types.ModuleType("langchain_core")
    langchain_messages = types.ModuleType("langchain_core.messages")

    custom.Component = _Component
    for name in (
        "BoolInput",
        "DataInput",
        "DropdownInput",
        "HandleInput",
        "IntInput",
        "MessageTextInput",
        "MultilineInput",
        "Output",
    ):
        setattr(io, name, _Field)
    schema.Data = _Data
    schema.Message = _Message
    schema_message.Message = _Message
    model_constants.MODEL_PROVIDERS_DICT = {
        "豆包AI": {
            "component_class": _ProviderComponent,
            "inputs": [
                _Field(name="model_name", value="doubao-test"),
                _Field(name="api_key", value=""),
            ],
            "prefix": "",
        }
    }
    global_api_key.get_global_api_key_sync = lambda _name: ""
    langchain_messages.HumanMessage = _HumanMessage

    sys.modules.update(
        {
            "langflow": langflow,
            "langflow.custom": custom,
            "langflow.io": io,
            "langflow.schema": schema,
            "langflow.schema.message": schema_message,
            "langflow.base": langflow_base,
            "langflow.base.models": langflow_base_models,
            "langflow.base.models.model_input_constants": model_constants,
            "langflow.helpers": langflow_helpers,
            "langflow.helpers.global_api_key": global_api_key,
            "langchain_core": langchain_core,
            "langchain_core.messages": langchain_messages,
        }
    )


def _load_module(name, filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_install_langflow_stubs()
REQUEST = _load_module("moldguard_request_adapter", "MoldGuard_请求适配器.py")
RESPONSE = _load_module("moldguard_response_adapter", "MoldGuard_响应适配器.py")
SNAPSHOT = _load_module("moldguard_snapshot_builder", "MoldGuard_知识快照构建器.py")
REQUEST_V2 = _load_module("moldguard_request_envelope_v2", "MoldGuard_请求信封_V2.py")
HTTP_V2 = _load_module("moldguard_single_input_http_v2", "MoldGuard_单输入HTTP_V2.py")
RESPONSE_V2 = _load_module("moldguard_response_envelope_v2", "MoldGuard_响应信封_V2.py")
SNAPSHOT_V2 = _load_module("moldguard_snapshot_envelope_v2", "MoldGuard_知识快照信封_V2.py")
SNAPSHOT_V3 = _load_module("moldguard_snapshot_envelope_v3", "MoldGuard_知识快照信封_V3.py")
MULTIMODAL = _load_module("moldguard_doubao_multimodal_v1", "MoldGuard_豆包多模态_V1.py")


class ComponentOutputTests(unittest.TestCase):
    def test_all_component_outputs_are_rendered_as_separate_ports(self):
        component_classes = (
            REQUEST.MoldGuardRequestAdapter,
            RESPONSE.MoldGuardResponseAdapter,
            SNAPSHOT.MoldGuardKnowledgeSnapshotBuilder,
        )

        for component_class in component_classes:
            with self.subTest(component=component_class.__name__):
                self.assertGreater(len(component_class.outputs), 1)
                self.assertTrue(
                    all(output.group_outputs is True for output in component_class.outputs)
                )

    def test_single_output_components_have_exactly_one_output(self):
        component_classes = (
            REQUEST_V2.MoldGuardRequestEnvelopeV2,
            HTTP_V2.MoldGuardSingleInputHttpV2,
            RESPONSE_V2.MoldGuardResponseEnvelopeV2,
            SNAPSHOT_V2.MoldGuardKnowledgeSnapshotEnvelopeV2,
            SNAPSHOT_V3.MoldGuardKnowledgeSnapshotEnvelopeV3,
            MULTIMODAL.MoldGuardDoubaoMultimodalV1,
        )

        for component_class in component_classes:
            with self.subTest(component=component_class.__name__):
                self.assertEqual(len(component_class.outputs), 1)

    def test_display_names_match_registered_platform_versions(self):
        expected_names = {
            REQUEST_V2.MoldGuardRequestEnvelopeV2: "MoldGuard 请求信封 V3（单输出）",
            HTTP_V2.MoldGuardSingleInputHttpV2: "MoldGuard 单输入 HTTP V2",
            RESPONSE_V2.MoldGuardResponseEnvelopeV2: "MoldGuard 响应信封 V3（单输出）",
            SNAPSHOT_V2.MoldGuardKnowledgeSnapshotEnvelopeV2: (
                "MoldGuard 知识快照信封 V2（单输出）"
            ),
            SNAPSHOT_V3.MoldGuardKnowledgeSnapshotEnvelopeV3: (
                "MoldGuard 知识快照信封 V3（单输出）"
            ),
            MULTIMODAL.MoldGuardDoubaoMultimodalV1: ("MoldGuard 豆包多模态 V1（批量图片）"),
        }

        for component_class, display_name in expected_names.items():
            with self.subTest(component=component_class.__name__):
                self.assertEqual(component_class.display_name, display_name)


class RequestAdapterTests(unittest.TestCase):
    def _component(self):
        component = REQUEST.MoldGuardRequestAdapter()
        component.base_url = "https://moldguard.oracle.19970219.xyz/"
        return component

    def test_scan_request(self):
        component = self._component()
        component.operation = component.SCAN
        component.demo_run_id = "DEMO-001"
        component.mold_ids = '["MOLD-1", "MOLD-2"]'
        result = component.build_request_data().data
        self.assertEqual(result["method"], "POST")
        self.assertTrue(result["url"].endswith("/api/v1/alerts/scan"))
        self.assertEqual(result["json_body"]["mold_ids"], ["MOLD-1", "MOLD-2"])
        self.assertEqual(result["json_body"]["client_request_id"], "DEMO-001-scan")

    def test_auto_assign_requires_gate_and_uses_scan_work_order(self):
        component = self._component()
        component.operation = component.AUTO_ASSIGN
        component.demo_run_id = "DEMO-001"
        component.work_order_id = "WO/1"
        component.execution_gate = ""
        with self.assertRaises(ValueError):
            component.build_url()
        component.execution_gate = _Message(text="success")
        result = component.build_request_data().data
        self.assertTrue(result["url"].endswith("/work-orders/WO%2F1/auto-assign"))
        self.assertEqual(result["json_body"], {"client_request_id": "DEMO-001-auto-assign"})

    def test_send_email_uses_current_django_endpoint(self):
        component = self._component()
        component.operation = component.SEND_EMAIL
        component.demo_run_id = "DEMO-001"
        component.work_order_id = "WO-1"
        component.execution_gate = _Message(text="success")
        result = component.build_request_data().data
        self.assertTrue(result["url"].endswith("/work-orders/WO-1/send-email"))
        self.assertEqual(result["json_body"], {"client_request_id": "DEMO-001-send-email"})

    def test_review_context_and_callback_requests(self):
        component = self._component()
        component.operation = component.REPORT_REVIEW_CONTEXT
        component.source_data = _Data(data={"submission_id": "RPT/1"})
        context = component.build_request_data().data
        self.assertEqual(context["method"], "GET")
        self.assertTrue(context["url"].endswith("/report-submissions/RPT%2F1/review-context"))

        component.operation = component.REPORT_REVIEW
        component.execution_gate = _Message(text="success")
        component.submission_id = "RPT/1"
        component.source_data = _Message(
            text=json.dumps(
                {
                    "client_request_id": "review-1",
                    "decision": "NEEDS_MORE_INFO",
                    "assessment_summary": "图片不清晰",
                    "confidence": 0.4,
                    "knowledge_package_hash": "a" * 64,
                },
                ensure_ascii=False,
            )
        )
        callback = component.build_request_data().data
        self.assertTrue(callback["url"].endswith("/report-submissions/RPT%2F1/review"))
        self.assertEqual(callback["json_body"]["decision"], "NEEDS_MORE_INFO")

        component.source_data = _Message(
            text=json.dumps(
                {
                    "client_request_id": "review-2",
                    "decision": "COMPLETE",
                    "assessment_summary": "声称完成",
                    "confidence": 0.95,
                    "knowledge_package_hash": "a" * 64,
                    "inspection_results": [{"knowledge_id": "KB-1", "result": "PASS"}],
                },
                ensure_ascii=False,
            )
        )
        with self.assertRaisesRegex(ValueError, "只允许回写 NEEDS_MORE_INFO"):
            component.build_request_data()

    def test_heartbeat_uses_selected_field(self):
        component = self._component()
        component.operation = component.SCHEDULER_HEARTBEAT
        component.work_order_id = "PRB-1"
        component.trigger_data = _Data(data={"timestamp": "2026-08-14T10:00:00+08:00"})
        component.evidence_field = "timestamp"
        component.client_request_id = ""
        result = component.build_request_data().data
        self.assertEqual(result["json_body"]["evidence"], "2026-08-14T10:00:00+08:00")
        self.assertTrue(result["json_body"]["client_request_id"].startswith("PRB-1-scheduler-"))


class ResponseAdapterTests(unittest.TestCase):
    def test_email_success_requires_message_id(self):
        component = RESPONSE.MoldGuardResponseAdapter()
        component.response_type = component.SEND_EMAIL
        component.response = _Data(
            data={
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "new_email_status": "SENT",
                        "email_message_id": "MSG-1",
                        "email_sent_at": "now",
                    },
                },
            }
        )
        result = component.build_result().data
        self.assertTrue(result["success"])
        self.assertEqual(result["primary_value"], "SENT")
        self.assertEqual(result["secondary_value"], "MSG-1")

        component.response.data["body"]["data"]["email_message_id"] = ""
        self.assertFalse(component.build_result().data["success"])

    def test_scan_routes_not_due_to_failure(self):
        component = RESPONSE.MoldGuardResponseAdapter()
        component.response_type = component.SCAN
        component.response = _Data(
            data={
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "results": [
                            {
                                "status": "NOT_DUE",
                                "code": "MAINTENANCE_NOT_DUE",
                                "message": "尚未到期",
                            }
                        ]
                    },
                },
            }
        )
        self.assertFalse(component.build_result().data["success"])
        self.assertIn("NOT_DUE", component.route_failure().text)

    def test_scan_success_returns_created_work_order_id(self):
        component = RESPONSE.MoldGuardResponseAdapter()
        component.response_type = component.SCAN
        component.response = _Data(
            data={
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "results": [
                            {
                                "status": "TRIGGERED",
                                "code": "MAINTENANCE_TRIGGERED",
                                "alert_id": "ALT-1",
                                "work_order_id": "WO-1",
                                "work_order_created": True,
                            }
                        ]
                    },
                },
            }
        )
        result = component.build_result().data
        self.assertTrue(result["success"])
        self.assertEqual(result["primary_value"], "WO-1")
        self.assertEqual(result["secondary_value"], "ALT-1")

    def test_review_response_accepts_django_finalized_status(self):
        component = RESPONSE.MoldGuardResponseAdapter()
        component.response_type = component.REPORT_REVIEW
        component.response = _Data(
            data={
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "submission_id": "RPT-1",
                        "submission_status": "FINALIZED",
                        "work_order_status": "COMPLETED",
                        "review_decision": "COMPLETE",
                    },
                },
            }
        )
        result = component.build_result().data
        self.assertTrue(result["success"])
        self.assertEqual(result["primary_value"], "COMPLETED")

    def test_auto_assign_reads_flat_assignee_id(self):
        component = RESPONSE.MoldGuardResponseAdapter()
        component.response_type = component.AUTO_ASSIGN
        component.response = _Data(
            data={
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {"work_order_id": "WO-1", "assignee_id": "EMP-1"},
                },
            }
        )
        result = component.build_result().data
        self.assertTrue(result["success"])
        self.assertEqual(result["primary_value"], "EMP-1")


class KnowledgeSnapshotTests(unittest.TestCase):
    VALID_ITEM = {
        "knowledge_id": "KB-1",
        "title": "标题",
        "item": "检查项",
        "knowledge_type": "INSPECTION_STANDARD",
        "content": "检查内容",
        "source": "MOLDGUARD-KB-1.2",
        "required": True,
    }

    def _component(self):
        component = SNAPSHOT.MoldGuardKnowledgeSnapshotBuilder()
        component.execution_gate = "success"
        component.work_order_id = "WO-1"
        component.demo_run_id = "DEMO-1"
        component.catalog_version = "MOLDGUARD-KB-1.2"
        component.base_url = "https://moldguard.oracle.19970219.xyz"
        component.fallback_items_json = ""
        return component

    def test_uses_valid_retrieved_metadata(self):
        component = self._component()
        component.knowledge_results = [_Data(data=dict(self.VALID_ITEM))]
        result = json.loads(component.build_json_body().text)
        self.assertEqual(set(result), {"catalog_version", "items", "client_request_id"})
        self.assertEqual(result["catalog_version"], "MOLDGUARD-KB-1.2")
        self.assertEqual(result["items"][0]["knowledge_id"], "KB-1")
        self.assertEqual(result["client_request_id"], "DEMO-1-knowledge-snapshot")
        self.assertTrue(component.build_url().text.endswith("/work-orders/WO-1/knowledge"))

    def test_uses_explicit_fallback_only_when_retrieved_items_are_invalid(self):
        component = self._component()
        component.knowledge_results = [_Data(data={"title": "不完整"})]
        component.fallback_items_json = json.dumps([self.VALID_ITEM], ensure_ascii=False)
        result = component.build_items_data().data
        self.assertEqual(result["source"], "controlled_fallback")
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["rejected_count"], 1)


class RequestEnvelopeV2Tests(unittest.TestCase):
    def _component(self):
        component = REQUEST_V2.MoldGuardRequestEnvelopeV2()
        component.base_url = "https://moldguard.oracle.19970219.xyz/"
        return component

    def test_scan_builds_all_molds_request_without_mold_ids(self):
        component = self._component()
        component.operation = component.SCAN
        component.demo_run_id = _Message(text="FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45")

        request = component.build_request().data

        self.assertEqual(request["schema_version"], "moldguard.request.v2")
        self.assertEqual(request["method"], "POST")
        self.assertTrue(request["url"].endswith("/api/v1/alerts/scan"))
        self.assertEqual(
            request["json_body"],
            {"client_request_id": ("FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45-scan")},
        )
        self.assertNotIn("mold_ids", {field.name for field in component.inputs})
        self.assertEqual(
            request["context"]["demo_run_id"],
            "FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45",
        )
        self.assertEqual(request["context"]["scan_scope"], "ALL_NON_DISABLED_MOLDS")

        start_field = next(field for field in component.inputs if field.name == "demo_run_id")
        self.assertEqual(start_field.display_name, "演示批次")

    def test_scan_requires_nonempty_demo_run_id(self):
        component = self._component()
        component.operation = component.SCAN
        component.demo_run_id = _Message(text=" ")

        with self.assertRaisesRegex(ValueError, "演示批次"):
            component.build_request()

    def test_auto_assign_reads_work_order_from_success_envelope(self):
        component = self._component()
        component.operation = component.AUTO_ASSIGN
        component.upstream = _Message(
            text="[MOLDGUARD_OK]",
            data={
                "success": True,
                "context": {
                    "demo_run_id": "DEMO-001",
                    "work_order_id": "WO/1",
                },
            },
        )

        request = component.build_request().data

        self.assertTrue(request["url"].endswith("/work-orders/WO%2F1/auto-assign"))
        self.assertEqual(
            request["json_body"],
            {"client_request_id": "DEMO-001-auto-assign"},
        )

        component.upstream.data["success"] = False
        with self.assertRaisesRegex(ValueError, "真"):
            component.build_request()

    def test_send_email_uses_propagated_context(self):
        component = self._component()
        component.operation = component.SEND_EMAIL
        component.upstream = _Message(
            data={
                "success": True,
                "context": {
                    "demo_run_id": "DEMO-001",
                    "work_order_id": "WO-1",
                    "employee_id": "EMP-1",
                    "knowledge_text": "[]",
                },
            }
        )

        request = component.build_request().data

        self.assertTrue(request["url"].endswith("/work-orders/WO-1/send-email"))
        self.assertEqual(
            request["json_body"],
            {"client_request_id": "DEMO-001-send-email"},
        )
        self.assertEqual(request["context"]["employee_id"], "EMP-1")

    def test_review_callback_defaults_to_safe_needs_more_info(self):
        component = self._component()
        component.operation = component.REPORT_REVIEW
        component.upstream = _Message(
            data={
                "success": True,
                "context": {
                    "submission_id": "RPT-1",
                    "work_order_id": "WO-1",
                    "knowledge_package_hash": "a" * 64,
                },
            }
        )

        request = component.build_request().data

        self.assertTrue(request["url"].endswith("/report-submissions/RPT-1/review"))
        self.assertEqual(request["json_body"]["decision"], "NEEDS_MORE_INFO")
        self.assertEqual(request["json_body"]["confidence"], 0.0)
        self.assertEqual(request["json_body"]["knowledge_package_hash"], "a" * 64)

        component.source_data = _Message(
            data={
                "client_request_id": "review-unsafe",
                "decision": "COMPLETE",
                "assessment_summary": "声称完成",
                "confidence": 0.95,
                "knowledge_package_hash": "a" * 64,
            }
        )
        with self.assertRaisesRegex(ValueError, "只允许回写 NEEDS_MORE_INFO"):
            component.build_request()


class _FakeHttpResponse:
    status_code = 200
    text = ""

    def json(self):
        return {"code": "SUCCESS", "data": {"ok": True}}


class _FakeAsyncClient:
    def __init__(self):
        self.request_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def request(self, **kwargs):
        self.request_kwargs = kwargs
        return _FakeHttpResponse()


class SingleInputHttpV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_request_and_preserves_context(self):
        component = HTTP_V2.MoldGuardSingleInputHttpV2()
        component.timeout = 30
        component.follow_redirects = True
        component.request = _Data(
            data={
                "schema_version": "moldguard.request.v2",
                "operation": "扫描预警",
                "method": "POST",
                "url": "https://moldguard.oracle.19970219.xyz/api/v1/alerts/scan",
                "json_body": {
                    "client_request_id": ("FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45-scan")
                },
                "context": {
                    "demo_run_id": "FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45",
                },
            }
        )
        fake_client = _FakeAsyncClient()

        with patch.object(HTTP_V2.httpx, "AsyncClient", return_value=fake_client):
            response = await component.execute_request()

        self.assertEqual(response.data["schema_version"], "moldguard.http-response.v2")
        self.assertEqual(response.data["status_code"], 200)
        self.assertEqual(
            response.data["context"]["demo_run_id"],
            "FLOW01-开始检查-当前时间是: 2026-08-14 15:30:45",
        )
        self.assertEqual(fake_client.request_kwargs["json"], component.request.data["json_body"])
        self.assertNotIn("mold_ids", fake_client.request_kwargs["json"])


class _FakeMultimodalModel:
    def __init__(self, content="", error=None):
        self.content = content
        self.error = error
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return types.SimpleNamespace(content=self.content)


class DoubaoMultimodalV1Tests(unittest.IsolatedAsyncioTestCase):
    AUDIT_RESULT = {
        "decision": "NEEDS_MORE_INFO",
        "decision_label": "需要补充材料",
        "assessment_summary": "第二张图片过暗，需要补拍。",
        "confidence": 0.63,
        "inspection_results": [],
        "abnormal_items": [],
        "abnormal_next_action": None,
        "reason_codes": ["IMAGE_TOO_DARK"],
        "knowledge_sources": ["MOLDGUARD-KB-1.2"],
        "review_model": "doubao-test",
        "image_observations": ["第一张图片清晰", "第二张图片过暗"],
    }

    def _component(self):
        component = MULTIMODAL.MoldGuardDoubaoMultimodalV1()
        component.prompt = _Message(text="只使用这段外部提示词，不得添加内置审核规则。")
        component.image_source = _Data(
            data={
                "body": {
                    "data": {
                        "submission": {
                            "evidence": [
                                {
                                    "url": "https://example.test/one.jpg",
                                    "content_type": "image/jpeg",
                                },
                                {
                                    "url": "https://example.test/two.png",
                                    "content_type": "image/png",
                                },
                            ]
                        }
                    }
                }
            }
        )
        component.image_path = "body.data.submission.evidence"
        component.response_mode = component.STRICT_JSON
        component.image_detail = "high"
        component.max_images = 10
        component.allowed_url_hosts = ""
        component.model_name = "doubao-test"
        component.api_key = ""
        return component

    async def test_passes_external_prompt_and_multiple_urls_in_order(self):
        component = self._component()
        model = _FakeMultimodalModel(json.dumps(self.AUDIT_RESULT, ensure_ascii=False))

        with patch.object(component, "_build_model", return_value=model):
            result = await component.generate_response()

        self.assertIn(component.OK_TOKEN, result.text)
        self.assertIn("[DOUBAO_DECISION=NEEDS_MORE_INFO]", result.text)
        self.assertIn("需要补充材料", result.text)
        self.assertEqual(result.data["decision"], "NEEDS_MORE_INFO")
        self.assertEqual(len(model.messages), 1)
        blocks = model.messages[0].content
        self.assertEqual(blocks[0], {"type": "text", "text": component.prompt.text})
        self.assertEqual(
            [block["image_url"]["url"] for block in blocks[1:]],
            ["https://example.test/one.jpg", "https://example.test/two.png"],
        )
        self.assertTrue(all(block["image_url"]["detail"] == "high" for block in blocks[1:]))

    async def test_accepts_stringified_json_message_from_native_parser(self):
        component = self._component()
        component.image_source = _Message(
            text=json.dumps(component.image_source.data, ensure_ascii=False)
        )
        model = _FakeMultimodalModel(json.dumps(self.AUDIT_RESULT, ensure_ascii=False))

        with patch.object(component, "_build_model", return_value=model):
            result = await component.generate_response()

        self.assertIn(component.OK_TOKEN, result.text)
        self.assertEqual(len(model.messages[0].content), 3)

    async def test_builds_native_provider_and_uses_global_bytedance_key(self):
        component = self._component()
        model = _FakeMultimodalModel(json.dumps(self.AUDIT_RESULT, ensure_ascii=False))
        key_module = sys.modules["langflow.helpers.global_api_key"]
        original_key_loader = key_module.get_global_api_key_sync
        _ProviderComponent.model = model
        _ProviderComponent.last_kwargs = None
        key_module.get_global_api_key_sync = lambda name: (
            "configured-key" if name == "bytedance" else ""
        )

        try:
            result = await component.generate_response()
        finally:
            key_module.get_global_api_key_sync = original_key_loader
            _ProviderComponent.model = None

        self.assertIn(component.OK_TOKEN, result.text)
        self.assertEqual(_ProviderComponent.last_kwargs["model_name"], "doubao-test")
        self.assertEqual(_ProviderComponent.last_kwargs["api_key"], "configured-key")

    async def test_accepts_fenced_json(self):
        component = self._component()
        content = f"```json\n{json.dumps(self.AUDIT_RESULT, ensure_ascii=False)}\n```"
        model = _FakeMultimodalModel(content)

        with patch.object(component, "_build_model", return_value=model):
            result = await component.generate_response()

        self.assertIn(component.OK_TOKEN, result.text)
        self.assertEqual(result.data["assessment_summary"], self.AUDIT_RESULT["assessment_summary"])

    async def test_converts_local_jpeg_png_webp_and_data_url(self):
        component = self._component()
        png = b"\x89PNG\r\n\x1a\n" + b"png-pixels"
        jpeg = b"\xff\xd8\xff" + b"jpeg-pixels"
        webp = b"RIFF\x08\x00\x00\x00WEBP" + b"webp-pixels"
        inline_png_content = b"\x89PNG\r\n\x1a\n" + b"different-inline-pixels"
        inline_png = "data:image/png;base64," + base64.b64encode(inline_png_content).decode()
        model = _FakeMultimodalModel(json.dumps(self.AUDIT_RESULT, ensure_ascii=False))

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = []
            for filename, content in (("one.jpg", jpeg), ("two.png", png), ("three.webp", webp)):
                path = Path(temp_dir) / filename
                path.write_bytes(content)
                paths.append(str(path))
            component.image_source = _Message(files=[*paths, inline_png])
            component.image_path = ""
            with patch.object(component, "_build_model", return_value=model):
                result = await component.generate_response()

        self.assertIn(component.OK_TOKEN, result.text)
        image_urls = [block["image_url"]["url"] for block in model.messages[0].content[1:]]
        self.assertEqual(len(image_urls), 4)
        self.assertTrue(image_urls[0].startswith("data:image/jpeg;base64,"))
        self.assertTrue(image_urls[1].startswith("data:image/png;base64,"))
        self.assertTrue(image_urls[2].startswith("data:image/webp;base64,"))
        self.assertEqual(image_urls[3], inline_png)

    async def test_invalid_json_and_model_error_return_failure_message(self):
        for model in (
            _FakeMultimodalModel("不是 JSON"),
            _FakeMultimodalModel(
                error=RuntimeError("https://secret.example/image.jpg?token=do-not-leak")
            ),
        ):
            with self.subTest(model=model):
                component = self._component()
                with patch.object(component, "_build_model", return_value=model):
                    result = await component.generate_response()
                self.assertIn(component.FAIL_TOKEN, result.text)
                self.assertEqual(result.data, {})
                self.assertNotIn("do-not-leak", result.text)
                self.assertNotIn("\n", result.text)
                self.assertNotIn('"', result.text)

    async def test_rejects_wrong_explicit_path_even_when_message_has_files(self):
        component = self._component()
        component.image_source = _Message(
            data={"images": ["https://example.test/one.jpg"]},
            files=["https://example.test/two.jpg"],
        )
        component.image_path = "missing.evidence"

        result = await component.generate_response()

        self.assertIn(component.FAIL_TOKEN, result.text)
        self.assertIn("不存在指定的字段路径", result.text)

    async def test_rejects_remote_url_outside_configured_hosts(self):
        component = self._component()
        component.allowed_url_hosts = "moldguard.oracle.19970219.xyz"

        result = await component.generate_response()

        self.assertIn(component.FAIL_TOKEN, result.text)
        self.assertIn("不在允许的图片域名", result.text)

    async def test_zero_and_over_limit_images_return_failure_message(self):
        component = self._component()
        component.image_source = _Data(data={"images": []})
        component.image_path = ""
        result = await component.generate_response()
        self.assertIn(component.FAIL_TOKEN, result.text)

        component = self._component()
        component.image_source = _Data(
            data={"images": [f"https://example.test/{index}.jpg" for index in range(11)]}
        )
        component.image_path = "images"
        result = await component.generate_response()
        self.assertIn(component.FAIL_TOKEN, result.text)
        self.assertIn("超过当前上限", result.text)


class ResponseEnvelopeV2Tests(unittest.TestCase):
    def test_scan_success_selects_triggered_work_order_from_all_results(self):
        component = RESPONSE_V2.MoldGuardResponseEnvelopeV2()
        component.response_type = component.SCAN
        component.response = _Data(
            data={
                "schema_version": "moldguard.http-response.v2",
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "scanned_count": 2,
                        "triggered_count": 1,
                        "results": [
                            {
                                "mold_id": "MOLD-1",
                                "status": "NOT_DUE",
                                "code": "MAINTENANCE_NOT_DUE",
                            },
                            {
                                "mold_id": "MOLD-2",
                                "status": "TRIGGERED",
                                "code": "MAINTENANCE_TRIGGERED",
                                "alert_id": "ALT-1",
                                "work_order_id": "WO-1",
                                "work_order_created": True,
                            },
                        ],
                    },
                },
                "context": {
                    "demo_run_id": "DEMO-001",
                    "scan_scope": "ALL_NON_DISABLED_MOLDS",
                },
            }
        )

        result = component.build_result()

        self.assertIn(component.OK_TOKEN, result.text)
        self.assertTrue(result.data["success"])
        self.assertEqual(result.data["context"]["work_order_id"], "WO-1")
        self.assertEqual(result.data["context"]["alert_id"], "ALT-1")
        self.assertEqual(result.data["context"]["selected_mold_id"], "MOLD-2")
        self.assertEqual(result.data["context"]["scanned_count"], 2)
        self.assertEqual(result.data["context"]["triggered_count"], 1)
        self.assertEqual(result.data["context"]["triggered_work_order_ids"], ["WO-1"])

    def test_scan_not_due_emits_failure_token(self):
        component = RESPONSE_V2.MoldGuardResponseEnvelopeV2()
        component.response_type = component.SCAN
        component.response = _Data(
            data={
                "schema_version": "moldguard.http-response.v2",
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "results": [
                            {
                                "status": "NOT_DUE",
                                "code": "MAINTENANCE_NOT_DUE",
                            }
                        ]
                    },
                },
                "context": {"demo_run_id": "DEMO-001"},
            }
        )

        result = component.build_result()

        self.assertIn(component.FAIL_TOKEN, result.text)
        self.assertFalse(result.data["success"])

    def test_knowledge_context_outputs_search_query_for_platform_kb(self):
        component = RESPONSE_V2.MoldGuardResponseEnvelopeV2()
        component.response_type = component.KNOWLEDGE_CONTEXT
        component.response = _Data(
            data={
                "schema_version": "moldguard.http-response.v2",
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "mold_type": "INJECTION",
                        "knowledge_profile_code": "INJECTION_MOLD",
                        "query_keywords": ["型腔", "冷却水路"],
                        "required_knowledge_types": ["INSPECTION_STANDARD"],
                    },
                },
                "context": {
                    "demo_run_id": "DEMO-001",
                    "work_order_id": "WO-1",
                    "employee_id": "EMP-1",
                },
            }
        )

        result = component.build_result()

        self.assertTrue(result.text.startswith("INJECTION INJECTION_MOLD"))
        self.assertIn(component.OK_TOKEN, result.text)
        self.assertIn("型腔", result.data["context"]["search_query"])

    def test_review_context_propagates_hash_and_submission(self):
        component = RESPONSE_V2.MoldGuardResponseEnvelopeV2()
        component.response_type = component.REPORT_REVIEW_CONTEXT
        component.response = _Data(
            data={
                "schema_version": "moldguard.http-response.v2",
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "submission": {
                            "submission_id": "RPT-1",
                            "evidence": [{"url": "https://example.test/evidence.jpg"}],
                        },
                        "work_order": {"work_order_id": "WO-1"},
                        "knowledge_package_hash": "a" * 64,
                        "review_callback_url": "https://example.test/review",
                    },
                },
                "context": {"submission_id": "RPT-1"},
            }
        )

        result = component.build_result()

        self.assertTrue(result.data["success"])
        self.assertIn(component.OK_TOKEN, result.text)
        self.assertEqual(result.data["context"]["work_order_id"], "WO-1")
        self.assertEqual(result.data["context"]["knowledge_package_hash"], "a" * 64)

    def test_review_callback_accepts_needs_more_info_decision(self):
        component = RESPONSE_V2.MoldGuardResponseEnvelopeV2()
        component.response_type = component.REPORT_REVIEW
        component.response = _Data(
            data={
                "schema_version": "moldguard.http-response.v2",
                "status_code": 200,
                "body": {
                    "code": "SUCCESS",
                    "data": {
                        "submission_id": "RPT-1",
                        "submission_status": "NEEDS_MORE_INFO",
                        "work_order_status": "ASSIGNED",
                        "review_decision": "NEEDS_MORE_INFO",
                    },
                },
                "context": {"submission_id": "RPT-1", "work_order_id": "WO-1"},
            }
        )

        result = component.build_result()

        self.assertTrue(result.data["success"])
        self.assertEqual(result.data["context"]["submission_status"], "NEEDS_MORE_INFO")


class KnowledgeSnapshotEnvelopeV2Tests(unittest.TestCase):
    VALID_ITEM = KnowledgeSnapshotTests.VALID_ITEM

    def _component(self):
        component = SNAPSHOT_V2.MoldGuardKnowledgeSnapshotEnvelopeV2()
        component.upstream = _Message(
            data={
                "success": True,
                "context": {
                    "demo_run_id": "DEMO-001",
                    "work_order_id": "WO-1",
                    "employee_id": "EMP-1",
                    "search_query": "INJECTION 型腔",
                },
            }
        )
        component.catalog_version = "MOLDGUARD-KB-1.2"
        component.base_url = "https://moldguard.oracle.19970219.xyz"
        component.fallback_items_json = ""
        return component

    def test_preserves_original_full_metadata_contract(self):
        component = self._component()
        component.knowledge_results = [_Data(data=dict(self.VALID_ITEM))]

        request = component.build_request().data

        self.assertEqual(request["json_body"]["items"][0]["knowledge_id"], "KB-1")
        self.assertIn("KB-1", request["context"]["knowledge_text"])


class KnowledgeSnapshotEnvelopeV3Tests(unittest.TestCase):
    EXTRACTED_ITEM = {
        "title": "分型面清洁与润滑",
        "content": "清除分型面异物，检查磨损并补充指定润滑脂。",
        "source": "模具保养知识库",
    }

    def _component(self):
        component = SNAPSHOT_V3.MoldGuardKnowledgeSnapshotEnvelopeV3()
        component.upstream = _Message(
            data={
                "success": True,
                "context": {
                    "demo_run_id": "DEMO-001",
                    "work_order_id": "WO-1",
                    "employee_id": "EMP-1",
                    "search_query": "INJECTION 型腔",
                },
            }
        )
        component.catalog_version = "MOLDGUARD-KB-1.2"
        component.base_url = "https://moldguard.oracle.19970219.xyz"
        component.fallback_items_json = ""
        return component

    def test_builds_single_request_and_propagates_knowledge_context(self):
        component = self._component()
        component.knowledge_results = _Data(data={"results": [dict(self.EXTRACTED_ITEM)]})

        request = component.build_request().data
        item = request["json_body"]["items"][0]

        self.assertEqual(request["schema_version"], "moldguard.request.v2")
        self.assertEqual(request["method"], "POST")
        self.assertTrue(request["url"].endswith("/work-orders/WO-1/knowledge"))
        self.assertTrue(item["knowledge_id"].startswith("KB-SHA256-"))
        self.assertEqual(item["item"], self.EXTRACTED_ITEM["title"])
        self.assertEqual(item["knowledge_type"], "MAINTENANCE_GUIDANCE")
        self.assertTrue(item["required"])
        self.assertIn(self.EXTRACTED_ITEM["content"], request["context"]["knowledge_text"])
        self.assertNotIn("KB-SHA256-", request["context"]["knowledge_text"])
        self.assertEqual(request["context"]["employee_id"], "EMP-1")

    def test_generated_id_is_stable_and_duplicate_results_are_collapsed(self):
        component = self._component()
        component.knowledge_results = _Data(
            data={"results": [dict(self.EXTRACTED_ITEM), dict(self.EXTRACTED_ITEM)]}
        )
        first_request = component.build_request().data

        second_component = self._component()
        second_component.knowledge_results = _Data(data=dict(self.EXTRACTED_ITEM))
        second_request = second_component.build_request().data

        first_items = first_request["json_body"]["items"]
        second_items = second_request["json_body"]["items"]
        self.assertEqual(len(first_items), 1)
        self.assertEqual(first_items[0]["knowledge_id"], second_items[0]["knowledge_id"])

    def test_accepts_json_message_from_modular_extraction(self):
        component = self._component()
        component.knowledge_results = _Message(
            text=json.dumps({"results": [self.EXTRACTED_ITEM]}, ensure_ascii=False)
        )

        request = component.build_request().data

        self.assertEqual(
            request["json_body"]["items"][0]["source"],
            "模具保养知识库",
        )

    def test_rejects_extracted_result_without_human_readable_source(self):
        component = self._component()
        component.knowledge_results = _Data(data={"title": "标题", "content": "保养说明"})

        with self.assertRaisesRegex(ValueError, "缺少字段：source"):
            component.build_request()


if __name__ == "__main__":
    unittest.main()
