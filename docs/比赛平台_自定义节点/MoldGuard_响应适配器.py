import json
from typing import Any

from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardResponseAdapter(Component):
    display_name = "MoldGuard 响应适配器"
    description = "按响应类型提取业务变量、执行严格成功判定，并提供成功/失败路由。"
    icon = "split"
    name = "MoldGuardResponseAdapter"

    SCAN = "扫描预警响应"
    AUTO_ASSIGN = "自动派工响应"
    KNOWLEDGE_CONTEXT = "知识上下文响应"
    KNOWLEDGE_SNAPSHOT = "知识快照响应"
    SEND_EMAIL = "派工邮件响应"
    REPORT_REVIEW_CONTEXT = "报工审核上下文响应"
    REPORT_REVIEW = "报工审核回写响应"
    SCHEDULER_HEARTBEAT = "定时心跳响应"

    inputs = [
        DropdownInput(
            name="response_type",
            display_name="响应类型",
            options=[
                SCAN,
                AUTO_ASSIGN,
                KNOWLEDGE_CONTEXT,
                KNOWLEDGE_SNAPSHOT,
                SEND_EMAIL,
                REPORT_REVIEW_CONTEXT,
                REPORT_REVIEW,
                SCHEDULER_HEARTBEAT,
            ],
            value=SCAN,
        ),
        HandleInput(
            name="response",
            display_name="HTTP 响应",
            input_types=["Data", "Message"],
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="结构化结果",
            name="result",
            method="build_result",
            group_outputs=True,
        ),
        Output(
            display_name="成功标量",
            name="success",
            method="build_success",
            group_outputs=True,
        ),
        Output(
            display_name="主变量",
            name="primary_value",
            method="build_primary_value",
            group_outputs=True,
        ),
        Output(
            display_name="次变量",
            name="secondary_value",
            method="build_secondary_value",
            group_outputs=True,
        ),
        Output(
            display_name="响应摘要",
            name="summary",
            method="build_summary",
            group_outputs=True,
        ),
        Output(
            display_name="成功分支",
            name="success_result",
            method="route_success",
            group_outputs=True,
        ),
        Output(
            display_name="失败分支",
            name="failure_result",
            method="route_failure",
            group_outputs=True,
        ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._route_updated = False

    def _pre_run_setup(self):
        self._route_updated = False

    @staticmethod
    def _response_dict(value: Any) -> dict[str, Any]:
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
                raise ValueError("HTTP 响应不是合法 JSON 对象。") from exc
        if not isinstance(raw, dict):
            raise ValueError("HTTP 响应必须是 Data 或 JSON 对象。")
        return raw

    @staticmethod
    def _body_dict(payload: dict[str, Any]) -> dict[str, Any]:
        body: Any = payload.get("body", {})
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return {"raw_text": body}
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _status_code(payload: dict[str, Any]) -> int:
        try:
            return int(payload.get("status_code", 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _nested(payload: Any, *keys: str, default: Any = "") -> Any:
        current = payload
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    @staticmethod
    def _nonempty_text(value: Any) -> str:
        return str(value).strip() if value is not None else ""

    def _analyze(self) -> dict[str, Any]:
        raw = self._response_dict(self.response)
        status_code = self._status_code(raw)
        body = self._body_dict(raw)
        code = self._nonempty_text(body.get("code"))
        common_ok = status_code == 200 and code == "SUCCESS"
        primary = ""
        secondary = ""
        primary_name = ""
        secondary_name = ""
        details: dict[str, Any] = {}
        success = False
        reason = ""

        if self.response_type == self.SCAN:
            results = self._nested(body, "data", "results", default=[])
            first = (
                results[0]
                if isinstance(results, list) and results and isinstance(results[0], dict)
                else {}
            )
            scan_status = self._nonempty_text(first.get("status"))
            scan_code = self._nonempty_text(first.get("code"))
            work_order_id = self._nonempty_text(first.get("work_order_id"))
            alert_id = self._nonempty_text(first.get("alert_id"))
            primary_name, primary = "work_order_id", work_order_id
            secondary_name, secondary = "alert_id", alert_id
            details = {
                "status": scan_status,
                "scan_code": scan_code,
                "work_order_id": work_order_id,
                "alert_id": alert_id,
                "work_order_created": first.get("work_order_created"),
                "message": first.get("message", ""),
            }
            success = (
                common_ok
                and scan_status == "TRIGGERED"
                and scan_code == "MAINTENANCE_TRIGGERED"
                and bool(work_order_id)
                and bool(alert_id)
            )
            if common_ok and scan_status and scan_status != "TRIGGERED":
                reason = f"扫描完成，当前状态为 {scan_status}（{scan_code or '无业务码'}）。"
            elif common_ok and scan_status == "TRIGGERED" and not work_order_id:
                reason = "扫描已触发保养，但响应缺少 work_order_id。"
            else:
                reason = (
                    "扫描已触发并返回工单。"
                    if success
                    else "扫描响应未满足 HTTP 200、SUCCESS、TRIGGERED 和工单字段要求。"
                )
        elif self.response_type == self.AUTO_ASSIGN:
            employee_id = self._nonempty_text(self._nested(body, "data", "assignee_id"))
            work_order_id = self._nonempty_text(self._nested(body, "data", "work_order_id"))
            primary_name, primary = "employee_id", employee_id
            secondary_name, secondary = "work_order_id", work_order_id
            details = {"employee_id": employee_id, "work_order_id": work_order_id}
            success = common_ok and bool(employee_id)
            reason = "自动派工成功。" if success else "自动派工响应缺少有效 employee_id。"
        elif self.response_type == self.KNOWLEDGE_CONTEXT:
            mold_type = self._nonempty_text(self._nested(body, "data", "mold_type"))
            profile_code = self._nonempty_text(self._nested(body, "data", "knowledge_profile_code"))
            query_keywords = self._nested(body, "data", "query_keywords", default=[])
            required_types = self._nested(body, "data", "required_knowledge_types", default=[])
            query_keywords = query_keywords if isinstance(query_keywords, list) else []
            required_types = required_types if isinstance(required_types, list) else []
            query_parts = []
            for value in [mold_type, profile_code, *query_keywords, *required_types]:
                text = self._nonempty_text(value)
                if text and text not in query_parts:
                    query_parts.append(text)
            search_query = " ".join(query_parts)
            primary_name, primary = "search_query", search_query
            secondary_name, secondary = "knowledge_profile_code", profile_code
            details = {
                "mold_type": mold_type,
                "knowledge_profile_code": profile_code,
                "search_query": search_query,
                "query_keywords": query_keywords,
                "required_knowledge_types": required_types,
            }
            success = common_ok and bool(mold_type) and bool(profile_code)
            reason = (
                "知识检索条件生成成功。"
                if success
                else "知识上下文缺少 mold_type 或 knowledge_profile_code。"
            )
        elif self.response_type == self.KNOWLEDGE_SNAPSHOT:
            primary_name, primary = "code", code
            details = {"code": code, "data": body.get("data", {})}
            success = common_ok
            reason = "知识快照回写成功。" if success else "知识快照未返回 HTTP 200 + SUCCESS。"
        elif self.response_type == self.SEND_EMAIL:
            email_status = self._nonempty_text(self._nested(body, "data", "new_email_status"))
            message_id = self._nonempty_text(self._nested(body, "data", "email_message_id"))
            primary_name, primary = "email_status", email_status
            secondary_name, secondary = "message_id", message_id
            details = {
                "email_status": email_status,
                "message_id": message_id,
                "sent_at": self._nested(body, "data", "email_sent_at"),
                "replayed": self._nested(body, "data", "replayed"),
            }
            success = common_ok and email_status == "SENT" and bool(message_id)
            reason = (
                "Django 已发送派工邮件并返回真实 email_message_id。"
                if success
                else ("发信失败：必须同时满足 HTTP 200、SUCCESS、SENT 和非空 email_message_id。")
            )
        elif self.response_type == self.REPORT_REVIEW_CONTEXT:
            submission_id = self._nonempty_text(
                self._nested(body, "data", "submission", "submission_id")
            )
            evidence = self._nested(body, "data", "submission", "evidence", default=[])
            evidence = evidence if isinstance(evidence, list) else []
            primary_evidence_url = self._nonempty_text(
                evidence[0].get("url") if evidence and isinstance(evidence[0], dict) else ""
            )
            primary_name, primary = "submission_id", submission_id
            secondary_name, secondary = "primary_evidence_url", primary_evidence_url
            details = {
                "submission_id": submission_id,
                "work_order_id": self._nested(body, "data", "work_order", "work_order_id"),
                "evidence_count": len(evidence),
                "primary_evidence_url": primary_evidence_url,
                "review_callback_url": self._nested(body, "data", "review_callback_url"),
            }
            success = common_ok and bool(submission_id) and bool(evidence)
            reason = (
                "报工审核上下文与图片证据已就绪。"
                if success
                else "审核上下文必须包含submission_id和至少一张图片证据。"
            )
        elif self.response_type == self.REPORT_REVIEW:
            submission_id = self._nonempty_text(self._nested(body, "data", "submission_id"))
            submission_status = self._nonempty_text(self._nested(body, "data", "submission_status"))
            work_order_status = self._nonempty_text(self._nested(body, "data", "work_order_status"))
            primary_name, primary = "work_order_status", work_order_status
            secondary_name, secondary = "submission_status", submission_status
            details = {
                "submission_id": submission_id,
                "submission_status": submission_status,
                "work_order_status": work_order_status,
                "review_decision": self._nested(body, "data", "review_decision"),
                "assessment_summary": self._nested(body, "data", "assessment_summary"),
            }
            finalized = submission_status == "FINALIZED" and work_order_status in {
                "COMPLETED",
                "ABNORMAL_REPORTED",
            }
            needs_more_info = submission_status == "NEEDS_MORE_INFO"
            success = common_ok and bool(submission_id) and (finalized or needs_more_info)
            reason = (
                "AI建议已由Django完成最终裁决。"
                if success
                else "审核回写未形成FINALIZED或NEEDS_MORE_INFO裁决。"
            )
        elif self.response_type == self.SCHEDULER_HEARTBEAT:
            primary_name, primary = "code", code
            secondary_name, secondary = "request_id", self._nonempty_text(body.get("request_id"))
            details = {"code": code, "data": body.get("data", {}), "request_id": secondary}
            success = common_ok
            reason = "定时心跳提交成功。" if success else "定时心跳未返回 HTTP 200 + SUCCESS。"
        else:
            raise ValueError(f"不支持的响应类型：{self.response_type}")

        summary = (
            f"[{self.response_type}] {'成功' if success else '未通过'}：{reason} "
            f"(HTTP {status_code or '未知'}, code={code or '空'})"
        )
        result = {
            "response_type": self.response_type,
            "success": success,
            "status_code": status_code,
            "code": code,
            "primary_name": primary_name,
            "primary_value": primary,
            "secondary_name": secondary_name,
            "secondary_value": secondary,
            "summary": summary,
            "details": details,
            "raw_response": raw,
        }
        self.status = result
        return result

    def build_result(self) -> Data:
        return Data(data=self._analyze())

    def build_success(self) -> Message:
        return Message(text=str(self._analyze()["success"]).lower())

    def build_primary_value(self) -> Message:
        return Message(text=str(self._analyze()["primary_value"]))

    def build_secondary_value(self) -> Message:
        return Message(text=str(self._analyze()["secondary_value"]))

    def build_summary(self) -> Message:
        return Message(text=self._analyze()["summary"])

    def _stop_once(self, route_to_stop: str) -> None:
        if not self._route_updated:
            self.stop(route_to_stop)
            self._route_updated = True

    def route_success(self) -> Message:
        result = self._analyze()
        if result["success"]:
            self._stop_once("failure_result")
            return Message(text=result["summary"])
        self._stop_once("success_result")
        return Message(text="")

    def route_failure(self) -> Message:
        result = self._analyze()
        if not result["success"]:
            self._stop_once("success_result")
            return Message(text=result["summary"])
        self._stop_once("failure_result")
        return Message(text="")
