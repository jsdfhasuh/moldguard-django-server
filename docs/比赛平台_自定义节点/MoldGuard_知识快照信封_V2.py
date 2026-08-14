import json
from typing import Any
from urllib.parse import quote

from langflow.custom import Component
from langflow.io import DataInput, HandleInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardKnowledgeSnapshotEnvelopeV2(Component):
    display_name = "MoldGuard 知识快照信封 V2（单输出）"
    description = "校验平台知识库结果，输出单个 Django 知识快照请求 Data 信封。"
    icon = "database"
    name = "MoldGuardKnowledgeSnapshotEnvelopeV2"

    REQUIRED_FIELDS = (
        "knowledge_id",
        "title",
        "item",
        "knowledge_type",
        "content",
        "source",
        "required",
    )

    inputs = [
        HandleInput(
            name="upstream",
            display_name="知识上下文成功信封",
            input_types=["Data", "Message"],
            info="连接知识上下文条件路由器的“真”输出。",
            required=True,
        ),
        DataInput(
            name="knowledge_results",
            display_name="知识库检索结果",
            info="连接“模具保养知识库”的 search_results。",
            is_list=True,
            required=False,
        ),
        MessageTextInput(
            name="catalog_version",
            display_name="知识目录版本",
            value="MOLDGUARD-KB-1.2",
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="后端基础地址",
            value="https://moldguard.oracle.19970219.xyz",
            required=True,
        ),
        MultilineInput(
            name="fallback_items_json",
            display_name="受控备用知识项 JSON（可选）",
            info="仅当平台检索结果没有有效条目时使用。",
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="知识快照请求信封", name="request", method="build_request"),
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
        return raw

    @classmethod
    def _upstream_context(cls, value: Any) -> dict[str, Any]:
        envelope = cls._data_dict(value, "知识上下文成功信封")
        if envelope.get("success") is not True:
            raise ValueError("知识快照只能连接原生条件路由器的“真”分支。")
        context = envelope.get("context", {})
        if not isinstance(context, dict):
            raise ValueError("上游信封的 context 必须是对象。")
        return dict(context)

    @staticmethod
    def _candidate_from_data(item: Data) -> dict[str, Any]:
        raw = item.data if isinstance(item.data, dict) else {}
        candidate: dict[str, Any] = {}
        metadata = raw.get("metadata")
        if isinstance(metadata, dict):
            candidate.update(metadata)
        candidate.update({key: value for key, value in raw.items() if key != "metadata"})

        for text_key in ("text", "page_content"):
            value = candidate.get(text_key)
            if isinstance(value, str) and value.strip().startswith("{"):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    candidate.update(parsed)

        if not candidate.get("content"):
            text = item.get_text() if hasattr(item, "get_text") else getattr(item, "text", "")
            if isinstance(text, str) and text.strip() and not text.strip().startswith("{"):
                candidate["content"] = text.strip()
        return candidate

    @classmethod
    def _validate_item(
        cls,
        candidate: dict[str, Any],
        source_label: str,
    ) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in cls.REQUIRED_FIELDS if field not in candidate]
        if missing:
            return None, f"{source_label} 缺少字段：{', '.join(missing)}"

        normalized: dict[str, Any] = {}
        for field in cls.REQUIRED_FIELDS:
            value = candidate[field]
            if field == "required":
                if not isinstance(value, bool):
                    return None, f"{source_label} 的 required 必须是布尔值。"
                normalized[field] = value
            else:
                text = str(value).strip() if value is not None else ""
                if not text:
                    return None, f"{source_label} 的 {field} 不能为空。"
                normalized[field] = text
        return normalized, ""

    def _retrieved_items(self) -> tuple[list[dict[str, Any]], list[str]]:
        values = getattr(self, "knowledge_results", None)
        if values is None:
            values = []
        if not isinstance(values, list):
            values = [values]

        items: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, value in enumerate(values, start=1):
            if not isinstance(value, Data):
                errors.append(f"检索结果第 {index} 项不是 Data。")
                continue
            normalized, error = self._validate_item(
                self._candidate_from_data(value),
                f"检索结果第 {index} 项",
            )
            if normalized is not None:
                items.append(normalized)
            else:
                errors.append(error)
        return items, errors

    def _fallback_items(self) -> list[dict[str, Any]]:
        raw = self._text(getattr(self, "fallback_items_json", ""))
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("受控备用知识项不是合法 JSON。") from exc
        if not isinstance(parsed, list):
            raise ValueError("受控备用知识项必须是 JSON 数组。")

        result: list[dict[str, Any]] = []
        for index, candidate in enumerate(parsed, start=1):
            if not isinstance(candidate, dict):
                raise ValueError(f"受控备用知识项第 {index} 项必须是对象。")
            normalized, error = self._validate_item(
                candidate,
                f"受控备用知识项第 {index} 项",
            )
            if normalized is None:
                raise ValueError(error)
            result.append(normalized)
        return result

    @staticmethod
    def _deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for item in items:
            knowledge_id = item["knowledge_id"]
            if knowledge_id not in seen:
                seen.add(knowledge_id)
                result.append(item)
        return result

    def _api_url(self, work_order_id: str) -> str:
        base = self._required_text(self.base_url, "后端基础地址").rstrip("/")
        prefix = "" if base.endswith("/api/v1") else "/api/v1"
        return f"{base}{prefix}/work-orders/{quote(work_order_id, safe='')}/knowledge"

    def _build(self) -> dict[str, Any]:
        context = self._upstream_context(self.upstream)
        work_order_id = self._required_text(context.get("work_order_id"), "工单 ID")
        demo_run_id = self._required_text(context.get("demo_run_id"), "演示批次")
        catalog_version = self._required_text(self.catalog_version, "知识目录版本")

        items, rejected = self._retrieved_items()
        source = "knowledge_base"
        if not items:
            items = self._fallback_items()
            source = "controlled_fallback"
        items = self._deduplicate(items)
        if not items:
            detail = "; ".join(rejected) if rejected else "知识库没有返回任何条目"
            raise ValueError(f"无法生成知识快照：{detail}，且未配置有效的受控备用知识项。")

        knowledge_text = json.dumps(items, ensure_ascii=False, indent=2)
        snapshot_context = dict(context)
        snapshot_context.update(
            {
                "knowledge_text": knowledge_text,
                "knowledge_items": items,
                "knowledge_source": source,
                "catalog_version": catalog_version,
            }
        )
        body = {
            "catalog_version": catalog_version,
            "items": items,
            "client_request_id": f"{demo_run_id}-knowledge-snapshot",
        }
        result = {
            "schema_version": "moldguard.request.v2",
            "operation": "知识快照回写",
            "method": "POST",
            "url": self._api_url(work_order_id),
            "json_body": body,
            "context": snapshot_context,
        }
        self.status = {
            "source": source,
            "accepted_count": len(items),
            "rejected_count": len(rejected),
        }
        return result

    def build_request(self) -> Data:
        return Data(data=self._build())
