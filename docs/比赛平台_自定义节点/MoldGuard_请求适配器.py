import json
import re
from typing import Any
from urllib.parse import quote

from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardRequestAdapter(Component):
    display_name = "MoldGuard 请求适配器"
    description = (
        "按业务动作生成 MoldGuard API 的完整 URL 和严格 JSON 请求体；本节点不发送 HTTP 请求。"
    )
    icon = "braces"
    name = "MoldGuardRequestAdapter"

    SCAN = "扫描预警"
    AUTO_ASSIGN = "自动派工"
    KNOWLEDGE_CONTEXT = "知识上下文"
    SEND_EMAIL = "发送派工邮件"
    REPORT_REVIEW_CONTEXT = "报工审核上下文"
    REPORT_REVIEW = "报工审核回写"
    SCHEDULER_HEARTBEAT = "定时心跳"
    MULTIMODAL_REVIEW_VERIFIED = False

    _DYNAMIC_FIELDS = {
        "execution_gate",
        "demo_run_id",
        "mold_ids",
        "work_order_id",
        "submission_id",
        "source_data",
        "trigger_data",
        "evidence_field",
        "client_request_id",
    }

    _VISIBLE_FIELDS = {
        SCAN: {"demo_run_id", "mold_ids"},
        AUTO_ASSIGN: {"execution_gate", "demo_run_id", "work_order_id"},
        KNOWLEDGE_CONTEXT: {"execution_gate", "work_order_id"},
        SEND_EMAIL: {"execution_gate", "demo_run_id", "work_order_id"},
        REPORT_REVIEW_CONTEXT: {"source_data"},
        REPORT_REVIEW: {"execution_gate", "submission_id", "source_data"},
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
            info="可填写站点根地址或以 /api/v1 结尾的 API 地址。",
            required=True,
        ),
        MessageTextInput(
            name="execution_gate",
            display_name="执行门",
            info="连接上一个响应适配器的“成功分支”，用于阻止失败分支继续调用后端。",
            show=False,
        ),
        MessageTextInput(
            name="demo_run_id",
            display_name="演示批次",
            info="可手动填写，也可连接聊天输入或其他 Message/Text 变量。",
            show=True,
        ),
        MessageTextInput(
            name="mold_ids",
            display_name="模具 ID",
            value="MOLD-TEST-001",
            info="一个模具 ID、逗号分隔的多个 ID，或 JSON 字符串数组。",
            show=True,
        ),
        MessageTextInput(
            name="work_order_id",
            display_name="工单 ID / 探测 run_id",
            info="普通业务使用工单 ID；定时心跳模式下填写流程 00 返回的 run_id。",
            show=False,
        ),
        MessageTextInput(name="submission_id", display_name="报工提交 ID", show=False),
        HandleInput(
            name="source_data",
            display_name="业务数据",
            input_types=["Data", "Message"],
            info="连接Webhook事件或AI严格JSON输出。",
            show=False,
        ),
        HandleInput(
            name="trigger_data",
            display_name="定时器数据",
            input_types=["Data", "Message"],
            info="定时心跳时连接定时触发器的真实 Data 输出。",
            show=False,
        ),
        MessageTextInput(
            name="evidence_field",
            display_name="证据字段路径",
            value="timestamp",
            info="从定时器 Data 中选择一个稳定字段，例如 timestamp；嵌套字段使用点号。",
            show=False,
        ),
        MessageTextInput(
            name="client_request_id",
            display_name="客户端请求 ID（可选）",
            info="留空时，定时心跳会根据 run_id 和证据值生成唯一 ID。",
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="URL", name="url", method="build_url", group_outputs=True),
        Output(
            display_name="JSON 请求体",
            name="json_body",
            method="build_json_body",
            group_outputs=True,
        ),
        Output(
            display_name="请求预览",
            name="request_data",
            method="build_request_data",
            group_outputs=True,
        ),
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
    def _data_dict(value: Any, label: str) -> dict[str, Any]:
        raw: Any
        if isinstance(value, Data):
            raw = value.data
        elif isinstance(value, Message):
            if isinstance(value.data, dict) and value.data:
                raw = value.data
            else:
                raw = value.text
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

    @classmethod
    def _parse_mold_ids(cls, value: Any) -> list[str]:
        raw = cls._required_text(value, "模具 ID")
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("模具 ID 的 JSON 数组格式无效。") from exc
            if not isinstance(parsed, list):
                raise ValueError("模具 ID 必须是字符串或 JSON 数组。")
            values = [str(item).strip() for item in parsed if str(item).strip()]
        else:
            values = [part.strip() for part in re.split(r"[,\n]", raw) if part.strip()]
        if not values:
            raise ValueError("至少需要一个模具 ID。")
        return values

    def _api_url(self, path: str) -> str:
        base = self._required_text(self.base_url, "后端基础地址").rstrip("/")
        prefix = "" if base.endswith("/api/v1") else "/api/v1"
        return f"{base}{prefix}{path}"

    def _require_gate(self) -> None:
        if not self._text(getattr(self, "execution_gate", "")):
            raise ValueError("当前请求必须连接上一个响应适配器的成功分支。")

    def _build_review_context_request(self) -> dict[str, Any]:
        payload = self._data_dict(getattr(self, "source_data", None), "Django Webhook 数据")
        submission_id = self._required_text(payload.get("submission_id"), "Webhook submission_id")
        return {
            "operation": self.REPORT_REVIEW_CONTEXT,
            "method": "GET",
            "url": self._api_url(
                f"/report-submissions/{quote(submission_id, safe='')}/review-context"
            ),
            "json_body": None,
        }

    def _build_review_callback_request(self) -> dict[str, Any]:
        self._require_gate()
        submission_id = self._required_text(self.submission_id, "报工提交 ID")
        body = self._data_dict(getattr(self, "source_data", None), "AI审核严格JSON")
        required = {
            "client_request_id",
            "decision",
            "assessment_summary",
            "confidence",
            "knowledge_package_hash",
        }
        missing = sorted(field for field in required if field not in body)
        if missing:
            raise ValueError(f"AI审核JSON缺少字段：{', '.join(missing)}")
        if not self.MULTIMODAL_REVIEW_VERIFIED and body["decision"] != "NEEDS_MORE_INFO":
            raise ValueError("当前平台尚未验证图片可进入多模态模型，只允许回写 NEEDS_MORE_INFO。")
        return {
            "operation": self.REPORT_REVIEW,
            "method": "POST",
            "url": self._api_url(f"/report-submissions/{quote(submission_id, safe='')}/review"),
            "json_body": body,
        }

    def _build(self) -> dict[str, Any]:
        operation = self.operation

        if operation == self.SCAN:
            demo_run_id = self._required_text(self.demo_run_id, "演示批次")
            result = {
                "operation": operation,
                "method": "POST",
                "url": self._api_url("/alerts/scan"),
                "json_body": {
                    "mold_ids": self._parse_mold_ids(self.mold_ids),
                    "client_request_id": f"{demo_run_id}-scan",
                },
            }
        elif operation == self.AUTO_ASSIGN:
            self._require_gate()
            demo_run_id = self._required_text(self.demo_run_id, "演示批次")
            work_order_id = self._required_text(self.work_order_id, "工单 ID")
            result = {
                "operation": operation,
                "method": "POST",
                "url": self._api_url(f"/work-orders/{quote(work_order_id, safe='')}/auto-assign"),
                "json_body": {"client_request_id": f"{demo_run_id}-auto-assign"},
            }
        elif operation == self.KNOWLEDGE_CONTEXT:
            self._require_gate()
            work_order_id = self._required_text(self.work_order_id, "工单 ID")
            result = {
                "operation": operation,
                "method": "GET",
                "url": self._api_url(
                    f"/work-orders/{quote(work_order_id, safe='')}/knowledge-context"
                ),
                "json_body": None,
            }
        elif operation == self.SEND_EMAIL:
            self._require_gate()
            demo_run_id = self._required_text(self.demo_run_id, "演示批次")
            work_order_id = self._required_text(self.work_order_id, "工单 ID")
            result = {
                "operation": operation,
                "method": "POST",
                "url": self._api_url(f"/work-orders/{quote(work_order_id, safe='')}/send-email"),
                "json_body": {"client_request_id": f"{demo_run_id}-send-email"},
            }
        elif operation == self.REPORT_REVIEW_CONTEXT:
            result = self._build_review_context_request()
        elif operation == self.REPORT_REVIEW:
            result = self._build_review_callback_request()
        elif operation == self.SCHEDULER_HEARTBEAT:
            run_id = self._required_text(self.work_order_id, "探测 run_id")
            trigger_data = self._data_dict(getattr(self, "trigger_data", None), "定时器数据")
            evidence_field = self._required_text(self.evidence_field, "证据字段路径")
            evidence_value = self._extract_path(trigger_data, evidence_field)
            evidence = (
                json.dumps(evidence_value, ensure_ascii=False, separators=(",", ":"), default=str)
                if isinstance(evidence_value, (dict, list))
                else str(evidence_value)
            )
            request_id = self._text(getattr(self, "client_request_id", ""))
            if not request_id:
                token = re.sub(r"[^A-Za-z0-9._-]+", "-", evidence).strip("-")[:64] or "tick"
                request_id = f"{run_id}-scheduler-{token}"
            result = {
                "operation": operation,
                "method": "POST",
                "url": self._api_url("/probe/scheduler-heartbeat"),
                "json_body": {
                    "run_id": run_id,
                    "platform_name": "competition-agent-platform",
                    "evidence": evidence,
                    "client_request_id": request_id,
                },
            }
        else:
            raise ValueError(f"不支持的请求类型：{operation}")

        self.status = result
        return result

    def build_url(self) -> Message:
        return Message(text=self._build()["url"])

    def build_json_body(self) -> Message:
        body = self._build()["json_body"]
        text = (
            ""
            if body is None
            else json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str)
        )
        return Message(text=text)

    def build_request_data(self) -> Data:
        return Data(data=self._build())

    def update_build_config(
        self, build_config: dict, field_value: str, field_name: str | None = None
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
