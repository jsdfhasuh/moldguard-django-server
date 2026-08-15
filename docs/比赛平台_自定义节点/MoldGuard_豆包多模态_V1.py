import asyncio
import base64
import inspect
import ipaddress
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from langchain_core.messages import HumanMessage
from langflow.base.models.model_input_constants import MODEL_PROVIDERS_DICT
from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, IntInput, MessageTextInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardMultimodalError(ValueError):
    pass


class MoldGuardDoubaoMultimodalV1(Component):
    display_name = "MoldGuard 豆包多模态 V1（批量图片）"
    description = "使用外部提示词和 1 至 10 张图片调用平台原生豆包模型。"
    icon = "images"
    name = "MoldGuardDoubaoMultimodalV1"

    STRICT_JSON = "严格 JSON"
    TEXT = "自然语言"
    OK_TOKEN = "[DOUBAO_OK]"
    FAIL_TOKEN = "[DOUBAO_FAIL]"

    _PROVIDER_NAME = "豆包AI"
    _PROVIDER = MODEL_PROVIDERS_DICT.get(_PROVIDER_NAME, {"inputs": []})
    _ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
    _MAX_IMAGE_BYTES = 20 * 1024 * 1024
    _COMMON_IMAGE_PATHS = (
        "body.data.submission.evidence",
        "data.submission.evidence",
        "context.review_context.submission.evidence",
        "review_context.submission.evidence",
        "submission.evidence",
        "evidence",
        "images",
        "files",
    )
    _FENCED_JSON = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.IGNORECASE | re.DOTALL)

    inputs = [
        HandleInput(
            name="prompt",
            display_name="外部提示词",
            input_types=["Message", "Data"],
            required=True,
            info="连接平台原生“提示词”节点；本节点不内置业务审核规则。",
        ),
        HandleInput(
            name="image_source",
            display_name="图片来源",
            input_types=["Data", "Message"],
            required=True,
            info="支持 Django 响应 Data、平台文件、聊天临时文件、URL 和 Data URL。",
        ),
        MessageTextInput(
            name="image_path",
            display_name="图片字段路径（可选）",
            value="",
            info=("留空时自动识别常见路径；流程 02 填 body.data.submission.evidence。"),
        ),
        MessageTextInput(
            name="allowed_url_hosts",
            display_name="允许的图片域名（可选）",
            value="",
            info="逗号分隔；流程 02 填 moldguard.oracle.19970219.xyz。留空允许公网域名。",
            advanced=True,
        ),
        DropdownInput(
            name="response_mode",
            display_name="输出模式",
            options=[STRICT_JSON, TEXT],
            value=STRICT_JSON,
        ),
        DropdownInput(
            name="image_detail",
            display_name="图片细节",
            options=["high", "auto", "low"],
            value="high",
            advanced=True,
        ),
        IntInput(
            name="max_images",
            display_name="最大图片数",
            value=10,
            advanced=True,
        ),
        *_PROVIDER.get("inputs", []),
    ]

    outputs = [
        Output(display_name="豆包结果", name="result", method="generate_response"),
    ]

    @staticmethod
    def _message_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Message):
            text = value.text
        elif isinstance(value, Data):
            text = value.get_text() if hasattr(value, "get_text") else ""
            if not text and isinstance(value.data, dict):
                text = json.dumps(value.data, ensure_ascii=False, default=str)
        else:
            text = value
        if isinstance(text, str):
            return text.strip()
        if isinstance(text, (dict, list)):
            return json.dumps(text, ensure_ascii=False, default=str)
        return str(text).strip()

    @staticmethod
    def _source_payload(value: Any) -> Any:
        if isinstance(value, Data):
            return value.data
        if isinstance(value, Message):
            if isinstance(value.data, (dict, list)) and value.data:
                return value.data
            value = value.text
        if isinstance(value, str):
            candidate = value.strip()
            if candidate:
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, (dict, list)):
                        return parsed
        return value

    @staticmethod
    def _message_files(value: Any) -> list[Any]:
        files = getattr(value, "files", None)
        if files in (None, ""):
            return []
        if isinstance(files, (list, tuple, set)):
            return list(files)
        return [files]

    @staticmethod
    def _path_parts(path: str) -> list[str]:
        normalized = re.sub(r"\[\s*['\"]?([^\]'\"]+)['\"]?\s*\]", r".\1", path)
        return [part.strip() for part in normalized.split(".") if part.strip()]

    @classmethod
    def _extract_path(cls, payload: Any, path: str) -> Any:
        current = payload
        for part in cls._path_parts(path):
            if isinstance(current, dict) and part in current:
                current = current[part]
                continue
            if isinstance(current, (list, tuple)) and part.isdigit():
                index = int(part)
                if index < len(current):
                    current = current[index]
                    continue
            raise KeyError(path)
        return current

    def _candidate_roots(self) -> list[Any]:
        roots = self._message_files(self.image_source)
        payload = self._source_payload(self.image_source)
        image_path = self._message_text(getattr(self, "image_path", ""))

        if image_path:
            try:
                roots.append(self._extract_path(payload, image_path))
            except KeyError as exc:
                raise MoldGuardMultimodalError("图片来源中不存在指定的字段路径。") from exc
            return roots

        for path in self._COMMON_IMAGE_PATHS:
            try:
                roots.append(self._extract_path(payload, path))
                break
            except KeyError:
                continue
        if not roots and payload not in (None, "", {}, []):
            roots.append(payload)
        return roots

    @classmethod
    def _iter_candidates(cls, value: Any, mime_hint: str = "") -> Iterable[tuple[Any, str]]:
        if value in (None, ""):
            return
        if isinstance(value, (str, bytes, bytearray, Path)) or hasattr(value, "__fspath__"):
            yield value, mime_hint
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                yield from cls._iter_candidates(item, mime_hint)
            return
        if isinstance(value, dict):
            hint = str(value.get("content_type") or value.get("mime_type") or mime_hint)
            for key in ("url", "image_url", "data_url", "file_path", "path", "file"):
                if value.get(key) not in (None, ""):
                    yield from cls._iter_candidates(value[key], hint)
                    return
            for key in ("result", "content", "value", "data"):
                candidate = value.get(key)
                if isinstance(candidate, (str, bytes, bytearray, Path)):
                    yield from cls._iter_candidates(candidate, hint)
                    return
            for key in ("images", "evidence", "files", "attachments", "items"):
                if value.get(key) not in (None, "", [], {}):
                    yield from cls._iter_candidates(value[key], hint)
            return
        for attr in ("url", "image_url", "data_url", "file_path", "path", "file"):
            candidate = getattr(value, attr, None)
            if candidate not in (None, ""):
                hint = str(
                    getattr(value, "content_type", "")
                    or getattr(value, "mime_type", "")
                    or mime_hint
                )
                yield from cls._iter_candidates(candidate, hint)
                return
        raise MoldGuardMultimodalError(f"不支持的图片输入类型：{type(value).__name__}")

    @classmethod
    def _sniff_mime_type(cls, content: bytes) -> str:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp"
        raise MoldGuardMultimodalError("本地图片内容不是受支持的 JPEG、PNG 或 WebP。")

    @classmethod
    def _data_url(cls, content: bytes, declared_mime: str = "") -> str:
        if not content:
            raise MoldGuardMultimodalError("图片内容不能为空。")
        if len(content) > cls._MAX_IMAGE_BYTES:
            raise MoldGuardMultimodalError("单张本地图片不能超过 20 MiB。")
        detected_mime = cls._sniff_mime_type(content)
        if declared_mime and declared_mime not in cls._ALLOWED_MIME_TYPES:
            raise MoldGuardMultimodalError(f"不支持的图片类型：{declared_mime}")
        if declared_mime and declared_mime != detected_mime:
            raise MoldGuardMultimodalError("图片声明类型与文件内容不一致。")
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{detected_mime};base64,{encoded}"

    @classmethod
    def _normalize_data_url(cls, value: str) -> str:
        header, separator, payload = value.partition(",")
        match = re.fullmatch(r"data:(image/[A-Za-z0-9.+-]+);base64", header, re.IGNORECASE)
        if not separator or not match:
            raise MoldGuardMultimodalError("图片 Data URL 必须使用 image/*;base64 格式。")
        declared_mime = match.group(1).lower()
        try:
            content = base64.b64decode(re.sub(r"\s+", "", payload), validate=True)
        except (ValueError, TypeError) as exc:
            raise MoldGuardMultimodalError("图片 Data URL 的 Base64 内容无效。") from exc
        return cls._data_url(content, declared_mime)

    def _allowed_hosts(self) -> set[str]:
        value = self._message_text(getattr(self, "allowed_url_hosts", ""))
        return {
            host.strip().lower().rstrip(".") for host in re.split(r"[,;\n]+", value) if host.strip()
        }

    def _validate_remote_url(self, parsed, mime_hint: str) -> None:
        hostname = str(parsed.hostname or "").lower().rstrip(".")
        if not hostname or parsed.username or parsed.password:
            raise MoldGuardMultimodalError("远程图片 URL 格式无效或包含凭据。")
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise MoldGuardMultimodalError("远程图片 URL 不允许使用非公网 IP 地址。")

        allowed_hosts = self._allowed_hosts()
        if allowed_hosts and not any(
            hostname == allowed or hostname.endswith(f".{allowed}") for allowed in allowed_hosts
        ):
            raise MoldGuardMultimodalError("远程图片 URL 不在允许的图片域名中。")

        declared_mime = mime_hint.partition(";")[0].strip().lower()
        if declared_mime and declared_mime not in self._ALLOWED_MIME_TYPES:
            raise MoldGuardMultimodalError(f"不支持的远程图片类型：{declared_mime}")

    def _normalize_candidate(self, value: Any, mime_hint: str = "") -> str:
        if isinstance(value, (bytes, bytearray)):
            return self._data_url(bytes(value), mime_hint)

        if hasattr(value, "__fspath__"):
            value = str(Path(value))
        if not isinstance(value, str):
            raise MoldGuardMultimodalError(f"不支持的图片值类型：{type(value).__name__}")

        source = value.strip()
        if source.lower().startswith("data:"):
            return self._normalize_data_url(source)

        parsed = urlparse(source)
        if parsed.scheme.lower() in {"http", "https"}:
            self._validate_remote_url(parsed, mime_hint)
            return source
        if parsed.scheme.lower() == "file":
            source = unquote(parsed.path)
            if re.match(r"^/[A-Za-z]:/", source):
                source = source[1:]

        path = Path(source).expanduser()
        if not path.is_file():
            raise MoldGuardMultimodalError("图片输入不是可访问的 HTTP URL、Data URL 或本地文件。")
        return self._data_url(path.read_bytes(), mime_hint)

    def _image_urls(self) -> list[str]:
        try:
            max_images = int(getattr(self, "max_images", 10) or 10)
        except (TypeError, ValueError) as exc:
            raise MoldGuardMultimodalError("最大图片数必须是 1 至 10 的整数。") from exc
        if not 1 <= max_images <= 10:
            raise MoldGuardMultimodalError("最大图片数必须在 1 至 10 之间。")

        candidates: list[tuple[Any, str]] = []
        for root in self._candidate_roots():
            candidates.extend(self._iter_candidates(root))
        if not candidates:
            raise MoldGuardMultimodalError("至少需要一张图片。")
        if len(candidates) > max_images:
            raise MoldGuardMultimodalError(
                f"图片数量为 {len(candidates)}，超过当前上限 {max_images}。"
            )

        image_urls: list[str] = []
        seen: set[str] = set()
        for candidate, mime_hint in candidates:
            normalized = self._normalize_candidate(candidate, mime_hint)
            if normalized not in seen:
                seen.add(normalized)
                image_urls.append(normalized)
        if not image_urls:
            raise MoldGuardMultimodalError("至少需要一张有效图片。")
        return image_urls

    def _build_model(self):
        provider = self._PROVIDER
        if not provider or "component_class" not in provider:
            raise MoldGuardMultimodalError("当前平台没有可用的豆包AI模型提供者。")
        component = provider["component_class"]
        prefix = provider.get("prefix", "")
        model_kwargs: dict[str, Any] = {}
        for input_ in provider.get("inputs", []):
            attr_name = f"{prefix}{input_.name}"
            value = getattr(self, attr_name, getattr(input_, "value", None))
            if value is not None:
                model_kwargs[input_.name] = value

        if "api_key" in model_kwargs and not model_kwargs["api_key"]:
            from langflow.helpers.global_api_key import get_global_api_key_sync

            global_api_key = get_global_api_key_sync("bytedance")
            if global_api_key:
                model_kwargs["api_key"] = global_api_key

        try:
            return component.set(**model_kwargs).build_model()
        except TypeError:
            signature = inspect.signature(component.__init__)
            accepts_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            valid_kwargs = (
                model_kwargs
                if accepts_kwargs
                else {
                    key: value for key, value in model_kwargs.items() if key in signature.parameters
                }
            )
            return component.set(**valid_kwargs).build_model()

    @staticmethod
    async def _invoke_model(model: Any, messages: list[HumanMessage]) -> Any:
        if hasattr(model, "ainvoke"):
            return await model.ainvoke(messages)
        if hasattr(model, "invoke"):
            return await asyncio.to_thread(model.invoke, messages)
        raise MoldGuardMultimodalError("当前豆包模型对象不支持 invoke 或 ainvoke。")

    @classmethod
    def _response_text(cls, response: Any) -> str:
        if isinstance(response, Message):
            return cls._message_text(response)
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            for key in ("content", "text", "output_text", "output"):
                if key in response:
                    return cls._response_text(response[key])
            messages = response.get("messages")
            if isinstance(messages, list) and messages:
                return cls._response_text(messages[-1])
        content = getattr(response, "content", None)
        if content is None:
            content = getattr(response, "text", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    text = block.get("text") or block.get("content")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
        return ""

    @classmethod
    def _parse_json(cls, text: str) -> dict[str, Any]:
        candidate = text.strip()
        fenced = cls._FENCED_JSON.fullmatch(candidate)
        if fenced:
            candidate = fenced.group(1).strip()
        try:
            result = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise MoldGuardMultimodalError("豆包没有返回合法的严格 JSON 对象。") from exc
        if not isinstance(result, dict):
            raise MoldGuardMultimodalError("豆包严格 JSON 输出必须是对象。")
        return result

    @staticmethod
    def _localized_decision(value: Any) -> str:
        return {
            "COMPLETE": "审核完成",
            "ABNORMAL": "发现异常",
            "NEEDS_MORE_INFO": "需要补充材料",
        }.get(str(value or "").upper(), str(value or "未提供"))

    @staticmethod
    def _localized_result(value: Any) -> str:
        return {
            "PASS": "通过",
            "FAIL": "不通过",
            "NOT_APPLICABLE": "不适用",
        }.get(str(value or "").upper(), str(value or "未提供"))

    @classmethod
    def _json_display(cls, payload: dict[str, Any], image_count: int) -> str:
        lines = [cls.OK_TOKEN, "豆包多模态审核建议", f"已读取图片：{image_count} 张"]
        decision = payload.get("decision")
        if decision not in (None, ""):
            normalized_decision = str(decision).upper()
            if normalized_decision in {"COMPLETE", "ABNORMAL", "NEEDS_MORE_INFO"}:
                lines.insert(1, f"[DOUBAO_DECISION={normalized_decision}]")
            label = payload.get("decision_label") or cls._localized_decision(normalized_decision)
            lines.append(f"审核结论：{label}（{normalized_decision}）")
        if payload.get("confidence") not in (None, ""):
            try:
                confidence = f"{float(payload['confidence']) * 100:.1f}%"
            except (TypeError, ValueError):
                confidence = str(payload["confidence"])
            lines.append(f"置信度：{confidence}")
        if payload.get("assessment_summary"):
            lines.append(f"审核说明：{payload['assessment_summary']}")

        observations = payload.get("image_observations")
        if isinstance(observations, list) and observations:
            lines.append("图片观察：")
            lines.extend(f"- {item}" for item in observations if str(item).strip())

        inspection_results = payload.get("inspection_results")
        if isinstance(inspection_results, list) and inspection_results:
            lines.append("点检结果：")
            for item in inspection_results:
                if not isinstance(item, dict):
                    continue
                knowledge_id = item.get("knowledge_id") or item.get("item") or "未命名检查项"
                lines.append(f"- {knowledge_id}：{cls._localized_result(item.get('result'))}")

        abnormal_items = payload.get("abnormal_items")
        if isinstance(abnormal_items, list) and abnormal_items:
            lines.append("异常项目：")
            for item in abnormal_items:
                if isinstance(item, dict):
                    name = item.get("item") or "未命名异常"
                    description = item.get("description") or ""
                    lines.append(f"- {name}：{description}")
                elif str(item).strip():
                    lines.append(f"- {item}")

        missing = payload.get("missing_information")
        if isinstance(missing, list) and missing:
            lines.append("需要补充：")
            lines.extend(f"- {item}" for item in missing if str(item).strip())
        lines.append("机器审核结果已准备，可连接 Django 回写节点。")
        return "\n".join(lines)

    @classmethod
    def _failure_message(cls, error: Exception) -> Message:
        if isinstance(error, MoldGuardMultimodalError):
            public_error = str(error)
        elif isinstance(error, TimeoutError):
            public_error = "豆包模型调用超时，请稍后重试。"
        else:
            public_error = "豆包模型调用失败，请检查模型配置或稍后重试。"
        public_error = re.sub(r"https?://\S+", "[已隐藏地址]", public_error)
        public_error = re.sub(r"[\r\n\t]+", " ", public_error)
        public_error = public_error.replace("\\", "/").replace('"', "")[:180].strip()
        text = f"{cls.FAIL_TOKEN} 豆包多模态处理失败：{public_error} 系统将按需要补充材料安全处理。"
        return Message(text=text, data={})

    async def generate_response(self) -> Message:
        try:
            prompt_text = self._message_text(self.prompt)
            if not prompt_text:
                raise MoldGuardMultimodalError("外部提示词不能为空。")
            image_urls = self._image_urls()
            detail = self._message_text(getattr(self, "image_detail", "high")) or "high"
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
            content.extend(
                {
                    "type": "image_url",
                    "image_url": {"url": image_url, "detail": detail},
                }
                for image_url in image_urls
            )
            model = self._build_model()
            response = await self._invoke_model(model, [HumanMessage(content=content)])
            response_text = self._response_text(response)
            if not response_text:
                raise MoldGuardMultimodalError("豆包返回内容为空。")

            if self.response_mode == self.STRICT_JSON:
                data = self._parse_json(response_text)
                text = self._json_display(data, len(image_urls))
            elif self.response_mode == self.TEXT:
                data = {}
                text = (
                    f"{self.OK_TOKEN}\n豆包多模态处理完成\n"
                    f"已读取图片：{len(image_urls)} 张\n{response_text}"
                )
            else:
                raise MoldGuardMultimodalError(f"不支持的输出模式：{self.response_mode}")

            self.status = {
                "success": True,
                "image_count": len(image_urls),
                "response_mode": self.response_mode,
            }
            return Message(text=text, data=data)
        except Exception as exc:
            public_message = self._failure_message(exc)
            self.status = {
                "success": False,
                "error_type": type(exc).__name__,
                "message": public_message.text,
            }
            return public_message
