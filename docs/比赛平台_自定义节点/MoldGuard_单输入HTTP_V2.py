import json
from typing import Any
from urllib.parse import urlparse

import httpx
from langflow.custom import Component
from langflow.io import BoolInput, HandleInput, IntInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class MoldGuardSingleInputHttpV2(Component):
    display_name = "MoldGuard 单输入 HTTP V2"
    description = "接收单个 MoldGuard 请求 Data 信封，执行 HTTP 并原样传递业务上下文。"
    icon = "globe"
    name = "MoldGuardSingleInputHttpV2"

    inputs = [
        HandleInput(
            name="request",
            display_name="请求信封",
            input_types=["Data", "Message"],
            required=True,
        ),
        IntInput(
            name="timeout",
            display_name="超时（秒）",
            value=30,
            advanced=True,
        ),
        BoolInput(
            name="follow_redirects",
            display_name="跟随重定向",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="HTTP 响应信封", name="response", method="execute_request"),
    ]

    @staticmethod
    def _request_dict(value: Any) -> dict[str, Any]:
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
                raise ValueError("请求信封不是合法 JSON 对象。") from exc
        if not isinstance(raw, dict):
            raise ValueError("请求信封必须是 Data 或 JSON 对象。")
        return raw

    @staticmethod
    def _validate_url(value: Any) -> str:
        url = str(value or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"无效的 HTTP URL：{url or '空'}")
        return url

    @staticmethod
    def _json_body(value: Any) -> dict[str, Any] | list[Any] | None:
        if value in (None, ""):
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("请求信封的 json_body 不是合法 JSON。") from exc
            if isinstance(parsed, (dict, list)):
                return parsed
        raise ValueError("请求信封的 json_body 必须是对象、数组或空值。")

    async def execute_request(self) -> Data:
        request = self._request_dict(self.request)
        if request.get("schema_version") != "moldguard.request.v2":
            raise ValueError("请求信封必须使用 moldguard.request.v2 契约。")

        method = str(request.get("method") or "").strip().upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError(f"不支持的 HTTP 方法：{method or '空'}")
        url = self._validate_url(request.get("url"))
        json_body = self._json_body(request.get("json_body"))
        context = request.get("context", {})
        if not isinstance(context, dict):
            raise ValueError("请求信封的 context 必须是对象。")

        kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "timeout": self.timeout,
            "follow_redirects": self.follow_redirects,
        }
        if method in {"POST", "PUT", "PATCH"} and json_body is not None:
            kwargs["json"] = json_body

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(**kwargs)
        except httpx.ConnectError as exc:
            raise ValueError(f"无法连接到服务器：{url}") from exc
        except httpx.TimeoutException as exc:
            raise ValueError(f"请求超时（{self.timeout}秒）") from exc
        except httpx.RequestError as exc:
            raise ValueError(f"HTTP 请求失败：{exc}") from exc

        try:
            body: Any = response.json()
        except ValueError:
            body = response.text

        result = {
            "schema_version": "moldguard.http-response.v2",
            "operation": request.get("operation", ""),
            "request_url": url,
            "request_method": method,
            "status_code": response.status_code,
            "body": body,
            "context": dict(context),
        }
        self.status = {
            "operation": result["operation"],
            "status_code": result["status_code"],
        }
        return Data(data=result)
