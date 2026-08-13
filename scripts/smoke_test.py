#!/usr/bin/env python3
import argparse
import http.cookiejar
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from html.parser import HTMLParser


class SmokeFailure(RuntimeError):
    pass


class HiddenInputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        attributes = dict(attrs)
        name = attributes.get("name")
        if name:
            self.inputs[name] = attributes.get("value", "")


class SmokeClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def _request(self, method, path, *, body=None, headers=None):
        request_headers = {
            "Accept": "application/json, text/html;q=0.9",
            "X-Request-ID": f"smoke-{uuid.uuid4().hex}",
            **(headers or {}),
        }
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                status = response.status
                response_body = response.read().decode(errors="replace")
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode(errors="replace")
            self._log(method, path, exc.code, self._business_code(response_body))
            raise SmokeFailure(
                f"{method} {path} returned HTTP {exc.code}: {response_body[:1000]}"
            ) from exc
        code = self._business_code(response_body) if content_type == "application/json" else "HTML"
        self._log(method, path, status, code)
        return status, content_type, response_body

    @staticmethod
    def _business_code(body):
        try:
            return json.loads(body).get("code", "INVALID_JSON")
        except json.JSONDecodeError:
            return "NON_JSON"

    @staticmethod
    def _log(method, path, status, code):
        print(f"{method:4} {path} -> HTTP {status} code={code}", flush=True)

    def json(self, method, path, payload=None):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        _, content_type, response_body = self._request(method, path, body=body, headers=headers)
        if content_type != "application/json":
            raise SmokeFailure(f"{method} {path} did not return JSON")
        try:
            result = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"{method} {path} returned invalid JSON") from exc
        if result.get("code") != "SUCCESS" or not result.get("request_id"):
            raise SmokeFailure(f"{method} {path} returned an invalid envelope: {result}")
        return result["data"]

    def html_get(self, path):
        status, content_type, body = self._request("GET", path)
        if status != 200 or content_type != "text/html":
            raise SmokeFailure(f"GET {path} did not return a successful HTML page")
        return body

    def html_report_normal(self, work_order_id):
        path = f"/report/{work_order_id}"
        page = self.html_get(path)
        parser = HiddenInputParser()
        parser.feed(page)
        required = {
            "csrfmiddlewaretoken",
            "submission_id",
            "report_form_schema_version",
            "knowledge_package_hash",
        }
        missing = sorted(required - parser.inputs.keys())
        if missing:
            raise SmokeFailure(f"report page is missing hidden fields: {missing}")
        form = {
            **{name: parser.inputs[name] for name in required},
            "report_type": "NORMAL",
            "report_summary": "HTTP smoke网页报工已完成保养并逐项检查",
            "inspection_0_result": "PASS",
            "inspection_0_not_applicable_reason": "",
            "inspection_0_abnormal_note": "",
            "abnormal_items_text": "",
            "photos_text": "smoke-text-photo-reference",
            "parts_replaced_text": "",
            "source_fault_id": "",
            "actual_work_hours": "1.00",
            "abnormal_next_action": "",
        }
        body = urllib.parse.urlencode(form).encode()
        status, content_type, result_page = self._request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": parser.inputs["csrfmiddlewaretoken"],
                "Referer": f"{self.base_url}{path}",
            },
        )
        if status != 200 or content_type != "text/html" or "报工已完成" not in result_page:
            raise SmokeFailure("HTML normal report did not render the completed result")


def request_id(prefix, run_id):
    return f"smoke-{prefix}-{run_id}"


def scan(client, mold_id, run_id):
    result = client.json(
        "POST",
        "/api/v1/alerts/scan",
        {
            "client_request_id": request_id(f"scan-{mold_id.lower()}", run_id),
            "mold_ids": [mold_id],
        },
    )
    item = result["results"][0]
    if item["status"] != "TRIGGERED":
        raise SmokeFailure(f"{mold_id} did not trigger: {item}")
    return item["work_order_id"]


def assign(client, work_order_id, run_id):
    candidates = client.json("GET", f"/api/v1/work-orders/{work_order_id}/candidates")
    if not candidates["candidates"]:
        raise SmokeFailure(f"no assignment candidate for {work_order_id}")
    employee_id = candidates["candidates"][0]["employee_id"]
    assigned = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/assign",
        {
            "client_request_id": request_id(f"assign-{work_order_id}", run_id),
            "employee_id": employee_id,
        },
    )
    if assigned["new_status"] != "ASSIGNED":
        raise SmokeFailure(f"assignment failed for {work_order_id}")
    return employee_id


def save_knowledge(client, work_order_id, run_id):
    knowledge = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/knowledge",
        {
            "client_request_id": request_id(f"knowledge-{work_order_id}", run_id),
            "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
            "title": "HTTP smoke点检知识包",
            "items": [
                {
                    "knowledge_id": "CHK-INJ-001",
                    "item": "模具外观",
                    "criteria": "配件齐全完好无异常",
                    "method": "目视",
                    "required": True,
                }
            ],
            "safety_notes": ["设备停止、断电并防止误启动"],
            "source_documents": ["MOLDGUARD-KB-1.2"],
        },
    )
    return knowledge["knowledge_package_hash"]


def record_email_sent(client, work_order_id, digest, run_id):
    email = client.json("GET", f"/api/v1/work-orders/{work_order_id}/email-context")
    if email["knowledge_package_hash"] != digest:
        raise SmokeFailure("email context and knowledge hashes differ")
    sent = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/email-result",
        {
            "client_request_id": request_id(f"email-{work_order_id}", run_id),
            "status": "SENT",
            "message_id": f"SMOKE-{run_id}",
            "sent_at": datetime.now(UTC).isoformat(),
            "knowledge_package_hash": digest,
            "error_message": "",
        },
    )
    if sent["new_email_status"] != "SENT":
        raise SmokeFailure("email result did not reach SENT")


def normal_payload(work_order_id, digest, run_id):
    return {
        "client_request_id": request_id(f"normal-{work_order_id}", run_id),
        "report_type": "NORMAL",
        "report_summary": "HTTP smoke已完成处理并重新点检",
        "inspection_results": [
            {
                "knowledge_id": "CHK-INJ-001",
                "result": "PASS",
                "not_applicable_reason": "",
                "abnormal_note": "",
            }
        ],
        "abnormal_items": [],
        "photos": ["smoke-text-photo-reference"],
        "parts_replaced": [],
        "source_fault_id": None,
        "actual_work_hours": "1.00",
        "abnormal_next_action": None,
        "knowledge_package_hash": digest,
    }


def abnormal_payload(work_order_id, digest, run_id, next_action):
    payload = normal_payload(work_order_id, digest, run_id)
    payload.update(
        {
            "client_request_id": request_id(f"abnormal-{work_order_id}", run_id),
            "report_type": "ABNORMAL",
            "report_summary": "HTTP smoke发现冷却水路堵塞",
            "inspection_results": [
                {
                    "knowledge_id": "CHK-INJ-001",
                    "result": "FAIL",
                    "not_applicable_reason": "",
                    "abnormal_note": "水路堵塞",
                }
            ],
            "abnormal_items": [{"item": "冷却水路", "description": "水路堵塞，需要后续处理"}],
            "actual_work_hours": "0.50",
            "abnormal_next_action": next_action,
        }
    )
    return payload


def verify_completed(client, work_order_id, mold_id):
    detail = client.json("GET", f"/api/v1/work-orders/{work_order_id}")
    if detail["status"] != "COMPLETED":
        raise SmokeFailure(f"work order {work_order_id} is not COMPLETED")
    records = client.json("GET", f"/api/v1/molds/{mold_id}/records")
    if not any(item["work_order_id"] == work_order_id for item in records["records"]):
        raise SmokeFailure(f"maintenance record missing for {work_order_id}")


def run_health(client):
    health = client.json("GET", "/api/v1/health")
    meta = client.json("GET", "/api/v1/meta")
    client.html_get("/api/docs")
    if health.get("status") != "ok":
        raise SmokeFailure("health status is not ok")
    if meta.get("knowledge_snapshot_version") != "MOLDGUARD-KB-1.2":
        raise SmokeFailure("unexpected knowledge version")


def run_normal(client, run_id, mold_id="DEMO-INJ-COUNT-TIME"):
    work_order_id = scan(client, mold_id, run_id)
    assign(client, work_order_id, run_id)
    digest = save_knowledge(client, work_order_id, run_id)
    record_email_sent(client, work_order_id, digest, run_id)
    client.html_report_normal(work_order_id)
    verify_completed(client, work_order_id, mold_id)
    client.json("GET", "/api/v1/analytics/summary")
    client.json("GET", "/api/v1/analytics/work-hours")
    client.json("GET", "/api/v1/analytics/order-completion")


def run_continue(client, run_id):
    mold_id = "DEMO-INJ-050K"
    work_order_id = scan(client, mold_id, run_id)
    assign(client, work_order_id, run_id)
    digest = save_knowledge(client, work_order_id, run_id)
    report = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/report",
        abnormal_payload(work_order_id, digest, run_id, "CONTINUE_PROCESSING"),
    )
    if report["new_status"] != "ABNORMAL_REPORTED":
        raise SmokeFailure("abnormal report did not reach ABNORMAL_REPORTED")
    continued = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/continue-processing",
        {
            "client_request_id": request_id(f"continue-{work_order_id}", run_id),
            "remarks": "HTTP smoke继续处理",
        },
    )
    if continued["new_status"] != "IN_PROGRESS":
        raise SmokeFailure("continue-processing did not reach IN_PROGRESS")
    completed = client.json(
        "POST",
        f"/api/v1/work-orders/{work_order_id}/report",
        normal_payload(work_order_id, digest, f"{run_id}-final"),
    )
    if completed["new_status"] != "COMPLETED":
        raise SmokeFailure("continued work order did not complete")
    verify_completed(client, work_order_id, mold_id)


def run_repair(client, run_id):
    mold_id = "DEMO-INJ-030K"
    parent_id = scan(client, mold_id, run_id)
    assign(client, parent_id, run_id)
    parent_digest = save_knowledge(client, parent_id, run_id)
    client.json(
        "POST",
        f"/api/v1/work-orders/{parent_id}/report",
        abnormal_payload(parent_id, parent_digest, run_id, "CREATE_REPAIR_TASK"),
    )
    linked = client.json(
        "POST",
        f"/api/v1/work-orders/{parent_id}/create-repair-task",
        {
            "client_request_id": request_id(f"repair-create-{parent_id}", run_id),
            "remarks": "HTTP smoke创建关联修模任务",
        },
    )
    repair_id = linked["repair_work_order_id"]
    assign(client, repair_id, f"{run_id}-child")
    repair_digest = save_knowledge(client, repair_id, f"{run_id}-child")
    repair_report = client.json(
        "POST",
        f"/api/v1/work-orders/{repair_id}/report",
        normal_payload(repair_id, repair_digest, f"{run_id}-child"),
    )
    if repair_report.get("parent_work_order_status") != "IN_PROGRESS":
        raise SmokeFailure("repair completion did not restore parent to IN_PROGRESS")
    parent_report = client.json(
        "POST",
        f"/api/v1/work-orders/{parent_id}/report",
        normal_payload(parent_id, parent_digest, f"{run_id}-parent-final"),
    )
    if parent_report["new_status"] != "COMPLETED":
        raise SmokeFailure("parent did not complete after repair")
    verify_completed(client, repair_id, mold_id)
    verify_completed(client, parent_id, mold_id)


def reset_demo(compose_env_file):
    command = [
        "docker",
        "compose",
        "--env-file",
        compose_env_file,
        "exec",
        "-T",
        "api",
        "python",
        "manage.py",
        "reset_demo_data",
        "--confirm",
    ]
    print("RESET competition DEMO data via the selected Compose project", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SmokeFailure("competition DEMO reset failed")


def main():
    parser = argparse.ArgumentParser(description="MoldGuard HTTP smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:18081")
    parser.add_argument(
        "--workflow",
        choices=["health", "normal", "continue", "repair", "all"],
        default="all",
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Reset only the selected competition Compose project's DEMO database first.",
    )
    parser.add_argument("--compose-env-file", default=".env.competition")
    args = parser.parse_args()
    try:
        if args.reset_demo:
            reset_demo(args.compose_env_file)
        client = SmokeClient(args.base_url)
        run_id = uuid.uuid4().hex[:16]
        run_health(client)
        if args.workflow in {"normal", "all"}:
            run_normal(client, run_id)
        if args.workflow in {"continue", "all"}:
            run_continue(client, f"{run_id}-continue")
        if args.workflow in {"repair", "all"}:
            run_repair(client, f"{run_id}-repair")
    except (SmokeFailure, urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"MoldGuard HTTP smoke passed: workflow={args.workflow}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
