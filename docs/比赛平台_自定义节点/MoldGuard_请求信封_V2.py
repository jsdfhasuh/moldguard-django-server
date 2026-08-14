import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.message import Message

REQUEST_ID_TIMEZONE = timezone(timedelta(hours=8))


class MoldGuardRequestEnvelopeV2(Component):
    display_name = "MoldGuard 请求信封 V3（单输出）"
    description = "根据业务动作生成单个请求 Data 信封；本节点不发送 HTTP 请求。"
    icon = "package"
    name = "MoldGuardRequestEnvelopeV2"

    SCAN = "扫描预警"
    AUTO_ASSIGN = "自动派工"
    KNOWLEDGE_CONTEXT = "知识上下文"
    SEND_EMAIL = "发送派工邮件"
    REPORT_REVIEW_CONTEXT = "报工审核上下文"
    REPORT_REVIEW = "报工审核回写"
    SCHEDULER_HEARTBEAT = "定时心跳"
    MULTIMODAL_REVIEW_VERIFIED = False

    _DYNAMIC_FIELDS = {
        "upstream",
        "demo_run_id",
        "source_data",
        "trigger_data",
        "work_order_id",
        "evidence_field",
        "client_request_id",
    }

    _VISIBLE_FIELDS = {
        SCAN: {"demo_run_id"},
        AUTO_ASSIGN: {"upstream"},
        KNOWLEDGE_CONTEXT: {"upstream"},
        SEND_EMAIL: {"upstream"},
        REPORT_REVIEW_CONTEXT: {"source_data"},
        REPORT_REVIEW: {"upstream", "source_data"},
        SCHEDULER_HEARTBEAT: {
            "trigger_data",
            "work_order_id",
            "evidence_field",
            "client_request_id",
        },
    }

    inputs = [
        DropdownInput(
            name="operation",
            display_name="请求类型",
            options=[
                SCAN,
                AUTO_ASSIGN,
                KNOWLEDGE_CONTEXT,
                SEND_EMAIL,
                REPORT_REVIEW_CONTEXT,
                REPORT_REVIEW,
                SCHEDULER_HEARTBEAT,
            ],
            value=SCAN,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="后端基础地址",
            value="https://moldguard.oracle.19970219.xyz",
            required=True,
        ),
        HandleInput(
            name="upstream",
            display_name="上游成功信封",
            input_types=["Data", "Message"],
            info="连接上一个原生条件路由器的“真”输出。",
            show=False,
        ),
        MessageTextInput(
            name="demo_run_id",
            display_name="启动指令",
            info="连接聊天输入；用户输入“开始检查”等指令，系统自动生成带北京时间的运行批次。",
            show=True,
        ),
        HandleInput(
            name="source_data",
            display_name="AI 审核 JSON（可选）",
            input_types=["Data", "Message"],
            info=(
                "报工审核上下文时连接 Webhook；审核回写留空时生成 NEEDS_MORE_INFO 安全门禁载荷。"
            ),
            show=False,
        ),
        HandleInput(
            name="trigger_data",
            display_name="定时器数据",
            input_types=["Data", "Message"],
            show=False,
        ),
        MessageTextInput(
            name="work_order_id",
            display_name="探测 run_id",
            info="仅定时心跳使用。",
            show=False,
        ),
        MessageTextInput(
            name="evidence_field",
            display_name="证据字段路径",
            value="timestamp",
            show=False,
        ),
        MessageTextInput(
            name="client_request_id",
            display_name="客户端请求 ID（可选）",
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="请求信封", name="request", method="build_request"),
    ]

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Message):
            return str(value.text or "").strip()
        return str(value).strip()

    @classmethod
    def _required_text(cls, value: Any, label: str) -> str:
        result = cls._text(value)
        if not result:
            raise ValueError(f"{label}不能为空。")
        return result

    @staticmethod
    def _new_flow_run_id() -> str:
        timestamp = datetime.now(REQUEST_ID_TIMEZONE).strftime("%Y%m%d-%H%M%S-%f")
        return f"FLOW01-{timestamp}"

    @staticmethod
    def _data_dict(value: Any, label: str) -> dict[str, Any]:
        raw: Any
        if isinstance(value, Data):
            raw = value.data
        elif isinstance(value, Message):
            raw = value.data if isinstance(value.data, dict) and value.data else value.text
        else:
            raw = value

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{label}不是合法 JSON 对象。") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{label}必须是 JSON 对象。")
        if set(raw) == {"payload"} and isinstance(raw["payload"], dict):
            raw = raw["payload"]
        return raw

    @staticmethod
    def _extract_path(payload: dict[str, Any], path: str) -> Any:
        current: Any = payload
        for key in [part.strip() for part in path.split(".") if part.strip()]:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"定时器数据中不存在字段路径：{path}")
            current = current[key]
        return current

    def _api_url(self, path: str) -> str:
        base = self._required_text(self.base_url, "后端基础地址").rstrip("/")
        prefix = "" if base.endswith("/api/v1") else "/api/v1"
        return f"{base}{prefix}{path}"

    def _upstream_context(self) -> tuple[dict[str, Any], dict[str, Any]]:
        envelope = self._data_dict(getattr(self, "upstream", None), "上游业务信封")
        if envelope.get("success") is not True:
            raise ValueError("当前请求只能连接原生条件路由器的“真”分支。")
        context = envelope.get("context", {})
        if not isinstance(context, dict):
            raise ValueError("上游业务信封的 context 必须是对象。")
        return envelope, dict(context)

    @staticmethod
    def _envelope(
        operation: str,
        method: str,
        url: str,
        json_body: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": "moldguard.request.v2",
            "operation": operation,
            "method": method,
            "url": url,
            "json_body": json_body,
            "context": context,
        }

    def _build_review_context(self) -> dict[str, Any]:
        payload = self._data_dict(getattr(self, "source_data", None), "Django Webhook 数据")
        submission_id = self._required_text(payload.get("submission_id"), "Webhook submission_id")
        context = {
            key: payload[key]
            for key in ("submission_id", "work_order_id", "review_context_url")
            if payload.get(key) not in (None, "")
        }
        return self._envelope(
            self.REPORT_REVIEW_CONTEXT,
            "GET",
            self._api_url(f"/report-submissions/{quote(submission_id, safe='')}/review-context"),
            None,
            context,
        )

    def _build_review_callback(self) -> dict[str, Any]:
        _, context = self._upstream_context()
        submission_id = self._required_text(context.get("submission_id"), "报工提交 ID")
        source_data = getattr(self, "source_data", None)
        if source_data in (None, ""):
            knowledge_package_hash = self._required_text(
                context.get("knowledge_package_hash"),
                "知识包哈希",
            )
            body = {
                "client_request_id": f"review-{submission_id}-safe-001",
                "decision": "NEEDS_MORE_INFO",
                "assessment_summary": (
                    "当前平台尚未验证图片可进入多模态模型，无法形成完成或异常建议。"
                ),
                "confidence": 0.0,
                "knowledge_package_hash": knowledge_package_hash,
                "inspection_results": [],
                "abnormal_items": [],
                "abnormal_next_action": None,
                "reason_codes": ["MULTIMODAL_INPUT_NOT_VERIFIED"],
                "knowledge_sources": ["MOLDGUARD-KB-1.2"],
                "review_model": "SAFE_GATE_NO_VISION",
            }
        else:
            body = self._data_dict(source_data, "AI 审核严格 JSON")
        required = {
            "client_request_id",
            "decision",
            "assessment_summary",
            "confidence",
            "knowledge_package_hash",
        }
        missing = sorted(field for field in required if field not in body)
        if missing:
            raise ValueError(f"AI 审核 JSON 缺少字段：{', '.join(missing)}")
        if not self.MULTIMODAL_REVIEW_VERIFIED and body["decision"] != "NEEDS_MORE_INFO":
            raise ValueError("当前平台尚未验证图片可进入多模态模型，只允许回写 NEEDS_MORE_INFO。")
        return self._envelope(
            self.REPORT_REVIEW,
            "POST",
            self._api_url(f"/report-submissions/{quote(submission_id, safe='')}/review"),
            body,
            context,
        )

    def _build(self) -> dict[str, Any]:
        operation = self.operation

        if operation == self.SCAN:
            start_command = self._required_text(self.demo_run_id, "启动指令")
            demo_run_id = self._new_flow_run_id()
            result = self._envelope(
                operation,
                "POST",
                self._api_url("/alerts/scan"),
                {"client_request_id": f"{demo_run_id}-scan"},
                {
                    "demo_run_id": demo_run_id,
                    "start_command": start_command,
                    "scan_scope": "ALL_NON_DISABLED_MOLDS",
                },
            )
        elif operation == self.AUTO_ASSIGN:
            _, context = self._upstream_context()
            demo_run_id = self._required_text(context.get("demo_run_id"), "系统运行批次")
            work_order_id = self._required_text(context.get("work_order_id"), "工单 ID")
            result = self._envelope(
                operation,
                "POST",
                self._api_url(f"/work-orders/{quote(work_order_id, safe='')}/auto-assign"),
                {"client_request_id": f"{demo_run_id}-auto-assign"},
                context,
            )
        elif operation == self.KNOWLEDGE_CONTEXT:
            _, context = self._upstream_context()
            work_order_id = self._required_text(context.get("work_order_id"), "工单 ID")
            result = self._envelope(
                operation,
                "GET",
                self._api_url(f"/work-orders/{quote(work_order_id, safe='')}/knowledge-context"),
                None,
                context,
            )
        elif operation == self.SEND_EMAIL:
            _, context = self._upstream_context()
            demo_run_id = self._required_text(context.get("demo_run_id"), "系统运行批次")
            work_order_id = self._required_text(context.get("work_order_id"), "工单 ID")
            result = self._envelope(
                operation,
                "POST",
                self._api_url(f"/work-orders/{quote(work_order_id, safe='')}/send-email"),
                {"client_request_id": f"{demo_run_id}-send-email"},
                context,
            )
        elif operation == self.REPORT_REVIEW_CONTEXT:
            result = self._build_review_context()
        elif operation == self.REPORT_REVIEW:
            result = self._build_review_callback()
        elif operation == self.SCHEDULER_HEARTBEAT:
            run_id = self._required_text(self.work_order_id, "探测 run_id")
            trigger_data = self._data_dict(getattr(self, "trigger_data", None), "定时器数据")
            evidence_field = self._required_text(self.evidence_field, "证据字段路径")
            evidence_value = self._extract_path(trigger_data, evidence_field)
            evidence = (
                json.dumps(
                    evidence_value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                )
                if isinstance(evidence_value, (dict, list))
                else str(evidence_value)
            )
            request_id = self._text(getattr(self, "client_request_id", ""))
            if not request_id:
                token = re.sub(r"[^A-Za-z0-9._-]+", "-", evidence).strip("-")[:64]
                request_id = f"{run_id}-scheduler-{token or 'tick'}"
            result = self._envelope(
                operation,
                "POST",
                self._api_url("/probe/scheduler-heartbeat"),
                {
                    "run_id": run_id,
                    "platform_name": "competition-agent-platform",
                    "evidence": evidence,
                    "client_request_id": request_id,
                },
                {"run_id": run_id},
            )
        else:
            raise ValueError(f"不支持的请求类型：{operation}")

        self.status = {
            "operation": result["operation"],
            "method": result["method"],
            "url": result["url"],
        }
        return result

    def build_request(self) -> Data:
        return Data(data=self._build())

    def update_build_config(
        self,
        build_config: dict,
        field_value: str,
        field_name: str | None = None,
    ) -> dict:
        if field_name != "operation":
            return build_config
        visible = self._VISIBLE_FIELDS.get(field_value, set())
        for field in self._DYNAMIC_FIELDS:
            if field in build_config:
                build_config[field]["show"] = field in visible
        if "operation" in build_config:
            build_config["operation"]["value"] = field_value
        return build_config
