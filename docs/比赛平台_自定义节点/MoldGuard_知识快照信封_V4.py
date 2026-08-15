import hashlib
import json
from typing import Any
from urllib.parse import quote

from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, MultilineInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardKnowledgeSnapshotEnvelopeV4(Component):
    display_name = "MoldGuard 知识快照信封 V4（单输出）"
    description = "兼容大模型 Message 包装，补齐内部字段并输出 Django 知识快照请求。"
    icon = "database"
    name = "MoldGuardKnowledgeSnapshotEnvelopeV4"

    EXTRACTED_FIELDS = ("title", "content", "source")
    FIELD_LIMITS = {"title": 240, "content": 4000, "source": 500}
    DEFAULT_KNOWLEDGE_TYPE = "MAINTENANCE_GUIDANCE"
    PAYLOAD_WRAPPER_KEYS = (
        "text",
        "page_content",
        "data",
        "message",
        "output",
        "result",
        "response",
    )
    DIAGNOSTIC_KEY_LIMIT = 20
    DIAGNOSTIC_SAFE_KEYS = frozenset(
        {
            *PAYLOAD_WRAPPER_KEYS,
            *EXTRACTED_FIELDS,
            "results",
            "metadata",
            "sender",
            "sender_name",
            "session_id",
            "trace_id",
            "run_id",
            "flow_id",
            "timestamp",
            "files",
            "properties",
            "content_blocks",
            "id",
            "type",
            "authorization",
            "cookie",
            "email",
            "token",
            "password",
        }
    )

    inputs = [
        HandleInput(
            name="upstream",
            display_name="知识上下文成功信封",
            input_types=["Data", "Message"],
            info="连接知识上下文条件路由器的“真”输出。",
            required=True,
        ),
        HandleInput(
            name="knowledge_results",
            display_name="模块化提取结果",
            input_types=["Data", "Message"],
            info=(
                "连接大模型或模块化提取的 Data/Message；每项只需 title、content、source，"
                '兼容 JSON Message、运行元数据包装和 {"results": [...]} 包装。'
            ),
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
            info="仅当模块化提取没有有效条目时使用；每项只需 title、content、source。",
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
    def _strip_json_fence(value: str) -> str:
        text = value.strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        return text

    @classmethod
    def _try_parse_json(cls, value: Any) -> tuple[bool, Any]:
        if not isinstance(value, str):
            return False, None
        text = cls._strip_json_fence(value)
        if not text:
            return False, None
        try:
            return True, json.loads(text)
        except json.JSONDecodeError:
            return False, None

    @classmethod
    def _is_structured_payload(cls, value: Any) -> bool:
        if isinstance(value, list):
            return bool(value)
        if not isinstance(value, dict):
            return False
        if "results" in value:
            return True
        return all(field in value for field in cls.EXTRACTED_FIELDS)

    @classmethod
    def _find_wrapped_payload(cls, value: Any, depth: int = 0) -> Any | None:
        if depth > 4:
            return None
        if cls._is_structured_payload(value):
            return value
        if isinstance(value, str):
            parsed_ok, parsed = cls._try_parse_json(value)
            if not parsed_ok:
                return None
            return cls._find_wrapped_payload(parsed, depth + 1)
        if isinstance(value, dict):
            for key in cls.PAYLOAD_WRAPPER_KEYS:
                if key not in value:
                    continue
                payload = cls._find_wrapped_payload(value[key], depth + 1)
                if payload is not None:
                    return payload
        return None

    @classmethod
    def _json_shape(cls, value: Any) -> str:
        parsed_ok, parsed = cls._try_parse_json(value)
        if not parsed_ok:
            return "false"
        if isinstance(parsed, dict) and "results" in parsed:
            return "results"
        if isinstance(parsed, dict) and all(field in parsed for field in cls.EXTRACTED_FIELDS):
            return "item"
        return type(parsed).__name__

    @classmethod
    def _diagnostic_key(cls, value: Any) -> str:
        key = str(value)
        if key in cls.DIAGNOSTIC_SAFE_KEYS:
            return key
        digest = hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"<redacted-key:{digest}>"

    @classmethod
    def _input_diagnostic(cls, value: Any) -> str:
        parts = [f"type={type(value).__name__}"]
        if isinstance(value, Message):
            message_text = str(value.text or "")
            parts.extend(
                [
                    f"text_len={len(message_text)}",
                    f"text_json={cls._json_shape(message_text)}",
                ]
            )
            data = value.data
        elif isinstance(value, Data):
            data = value.data
        else:
            data = value

        parts.append(f"data_type={type(data).__name__}")
        if isinstance(data, dict):
            keys = [cls._diagnostic_key(key) for key in data.keys()][: cls.DIAGNOSTIC_KEY_LIMIT]
            parts.append(f"data_keys={json.dumps(keys, ensure_ascii=False)}")
            parts.append(f"data_has_results={'results' in data}")
            results = data.get("results")
            if isinstance(results, list):
                parts.append(f"data_results_len={len(results)}")
            present_fields = [field for field in cls.EXTRACTED_FIELDS if field in data]
            parts.append(f"data_fields={json.dumps(present_fields, ensure_ascii=False)}")
            for key in ("text", "page_content"):
                nested_text = data.get(key)
                if isinstance(nested_text, str):
                    parts.extend(
                        [
                            f"data_{key}_len={len(nested_text)}",
                            f"data_{key}_json={cls._json_shape(nested_text)}",
                        ]
                    )
        elif isinstance(data, list):
            parts.append(f"data_len={len(data)}")
            if data:
                parts.append(f"data_item_type={type(data[0]).__name__}")
        elif isinstance(data, str):
            parts.extend(
                [
                    f"data_len={len(data)}",
                    f"data_json={cls._json_shape(data)}",
                ]
            )
        return f"输入诊断[{'; '.join(parts)}]"

    @classmethod
    def _decode_payload(cls, value: Any, source_label: str) -> Any:
        payload: Any | None = None
        if isinstance(value, Data):
            raw: Any = value.data
            payload = cls._find_wrapped_payload(raw)
        elif isinstance(value, Message):
            data = value.data if isinstance(value.data, (dict, list)) else None
            if cls._is_structured_payload(data):
                return data
            payload = cls._find_wrapped_payload(value.text)
            if payload is None:
                payload = cls._find_wrapped_payload(data)
            raw = data if data else value.text
        else:
            raw = value
            payload = cls._find_wrapped_payload(raw)

        if payload is not None:
            return payload
        if isinstance(raw, str):
            parsed_ok, parsed = cls._try_parse_json(raw)
            if parsed_ok:
                return parsed
            message = f"{source_label}必须是结构化 JSON，不能直接使用大模型自由文本。"
            raise ValueError(message)
        return raw

    @classmethod
    def _candidate_records(cls, value: Any, source_label: str) -> list[dict[str, Any]]:
        payload = cls._decode_payload(value, source_label)
        if isinstance(payload, dict) and "results" in payload:
            payload = payload["results"]
        elif isinstance(payload, dict):
            payload = [payload]

        if not isinstance(payload, list):
            raise ValueError(f"{source_label}必须是对象、对象数组或包含 results 数组的对象。")
        if not payload:
            raise ValueError(f"{source_label}的 results 不能为空。")

        records: list[dict[str, Any]] = []
        for index, candidate in enumerate(payload, start=1):
            if not isinstance(candidate, dict):
                raise ValueError(f"{source_label}第 {index} 项必须是对象。")
            records.append(candidate)
        return records

    @staticmethod
    def _candidate_from_mapping(raw: dict[str, Any]) -> dict[str, Any]:
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
            for text_key in ("text", "page_content"):
                value = candidate.get(text_key)
                if isinstance(value, str) and value.strip() and not value.strip().startswith("{"):
                    candidate["content"] = value.strip()
                    break
        return candidate

    @classmethod
    def _normalize_item(
        cls,
        candidate: dict[str, Any],
        source_label: str,
    ) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in cls.EXTRACTED_FIELDS if not cls._text(candidate.get(field))]
        if missing:
            return None, f"{source_label} 缺少字段：{', '.join(missing)}"

        extracted = {field: cls._text(candidate[field]) for field in cls.EXTRACTED_FIELDS}
        for field, limit in cls.FIELD_LIMITS.items():
            if len(extracted[field]) > limit:
                return None, f"{source_label} 的 {field} 超过 {limit} 个字符。"

        canonical = json.dumps(
            extracted,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        normalized = {
            "knowledge_id": f"KB-SHA256-{digest}",
            "title": extracted["title"],
            "item": extracted["title"],
            "knowledge_type": cls.DEFAULT_KNOWLEDGE_TYPE,
            "content": extracted["content"],
            "source": extracted["source"],
            "required": True,
        }
        return normalized, ""

    def _retrieved_items(self) -> tuple[list[dict[str, Any]], list[str]]:
        values = getattr(self, "knowledge_results", None)
        if values is None:
            values = []
        if not isinstance(values, list):
            values = [values]

        items: list[dict[str, Any]] = []
        errors: list[str] = []
        for input_index, value in enumerate(values, start=1):
            source_label = f"模块化提取结果第 {input_index} 组"
            diagnostic = self._input_diagnostic(value)
            try:
                candidates = self._candidate_records(value, source_label)
            except ValueError as exc:
                errors.append(f"{exc}；{diagnostic}")
                continue
            for item_index, candidate in enumerate(candidates, start=1):
                normalized, error = self._normalize_item(
                    self._candidate_from_mapping(candidate),
                    f"{source_label}第 {item_index} 项",
                )
                if normalized is not None:
                    items.append(normalized)
                else:
                    errors.append(f"{error}；{diagnostic}")
        return items, errors

    def _fallback_items(self) -> list[dict[str, Any]]:
        raw = self._text(getattr(self, "fallback_items_json", ""))
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("受控备用知识项不是合法 JSON。") from exc
        result: list[dict[str, Any]] = []
        for index, candidate in enumerate(
            self._candidate_records(parsed, "受控备用知识项"),
            start=1,
        ):
            normalized, error = self._normalize_item(
                self._candidate_from_mapping(candidate),
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
        source = "platform_normalized_knowledge"
        if not items:
            items = self._fallback_items()
            source = "controlled_fallback"
        items = self._deduplicate(items)
        if not items:
            detail = "; ".join(rejected) if rejected else "知识库没有返回任何条目"
            raise ValueError(f"无法生成知识快照：{detail}，且未配置有效的受控备用知识项。")

        knowledge_text = "\n\n".join(
            f"{index}. {item['title']}\n{item['content']}\n来源：{item['source']}"
            for index, item in enumerate(items, start=1)
        )
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
