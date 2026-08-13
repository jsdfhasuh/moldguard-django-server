#!/usr/bin/env python3
"""Run the platform-probe demo through real HTTP calls.

Without PROBE_BASE_URL this script resets the local demo database, starts a
temporary Django development server on port 18080, exercises three normal
workflows and one abnormal workflow, then stops the server. Set PROBE_BASE_URL
to exercise an already-running deployment without modifying its process.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "http://127.0.0.1:18080"
TIMEZONE = ZoneInfo("Asia/Shanghai")


class SmokeFailure(RuntimeError):
    pass


class ProbeClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.sequence = 0

    def request_id(self, label):
        self.sequence += 1
        return f"smoke-{label}-{self.sequence}-{uuid.uuid4().hex[:8]}"

    def request(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status = response.status
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            status = exc.code
            result = json.loads(exc.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if status >= 400 or result.get("code") != "SUCCESS":
            raise SmokeFailure(f"{method} {path} returned {status}: {result}")
        if not str(result.get("request_id", "")).startswith("req-"):
            raise SmokeFailure(f"{method} {path} did not return a request_id")
        return result["data"]

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, payload):
        return self.request("POST", path, payload)


def wait_until_ready(client, process=None, timeout=20):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise SmokeFailure(f"Django server exited with status {process.returncode}")
        try:
            client.get("/api/v1/health")
            return
        except SmokeFailure as exc:
            last_error = exc
            time.sleep(0.25)
    raise SmokeFailure(f"Server did not become ready: {last_error}")


def start_local_server():
    with socket.socket() as probe_socket:
        try:
            probe_socket.bind(("127.0.0.1", 18080))
        except OSError as exc:
            raise SmokeFailure(
                "Port 18080 is already in use. Stop that process or set PROBE_BASE_URL."
            ) from exc
    subprocess.run(
        [sys.executable, str(ROOT / "manage.py"), "reset_probe_data"],
        cwd=ROOT,
        check=True,
    )
    return subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "manage.py"),
            "runserver",
            "127.0.0.1:18080",
            "--noreload",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def knowledge_items(mold_type):
    if mold_type == "INJECTION":
        return [
            {
                "knowledge_id": "KB-INJECTION-001",
                "item": "检查模具表面及型腔",
                "knowledge_type": "INSPECTION_STANDARD",
                "required": True,
            },
            {
                "knowledge_id": "KB-INJECTION-002",
                "item": "检查冷却水路",
                "knowledge_type": "INSPECTION_STANDARD",
                "required": True,
            },
        ]
    return [
        {
            "knowledge_id": "KB-SHEET-001",
            "item": "检查刃口和导向部件",
            "knowledge_type": "INSPECTION_STANDARD",
            "required": True,
        },
        {
            "knowledge_id": "KB-SHEET-002",
            "item": "检查润滑与紧固状态",
            "knowledge_type": "INSPECTION_STANDARD",
            "required": True,
        },
    ]


def alert_for_mold(client, mold_id):
    alerts = client.get(f"/api/v1/alerts?mold_id={mold_id}&alert_type=MAINTENANCE_DUE")["alerts"]
    if len(alerts) != 1:
        raise SmokeFailure(f"Expected one maintenance alert for {mold_id}, got {alerts}")
    return alerts[0]


def prepare_work_order(client, mold_id):
    alert = alert_for_mold(client, mold_id)
    work_order = client.post(
        f"/api/v1/alerts/{alert['alert_id']}/create-work-order",
        {"client_request_id": client.request_id(f"create-{mold_id}")},
    )
    candidates = client.get(f"/api/v1/work-orders/{work_order['work_order_id']}/candidates")[
        "candidates"
    ]
    if not candidates:
        raise SmokeFailure(f"No assignment candidate for {mold_id}")
    assigned = client.post(
        f"/api/v1/work-orders/{work_order['work_order_id']}/auto-assign",
        {"client_request_id": client.request_id(f"assign-{mold_id}")},
    )
    context = client.get(f"/api/v1/work-orders/{work_order['work_order_id']}/knowledge-context")
    items = knowledge_items(context["mold_type"])
    client.post(
        f"/api/v1/work-orders/{work_order['work_order_id']}/knowledge-snapshot",
        {
            "catalog_version": "SMOKE-KB-V1",
            "items": items,
            "client_request_id": client.request_id(f"snapshot-{mold_id}"),
        },
    )
    email_context = client.get(f"/api/v1/work-orders/{work_order['work_order_id']}/email-context")
    expected_email = assigned["assigned_employee"]["email"]
    if email_context["to"] != [expected_email] or "cc" in email_context:
        raise SmokeFailure(f"Unsafe email context: {email_context}")
    client.post(
        f"/api/v1/work-orders/{work_order['work_order_id']}/notifications",
        {
            "status": "SENT",
            "message_id": f"smoke-message-{work_order['work_order_id']}",
            "sent_at": datetime.now(TIMEZONE).isoformat(),
            "client_request_id": client.request_id(f"notify-{mold_id}"),
        },
    )
    return work_order["work_order_id"], assigned["assigned_employee"], items


def run_normal_flow(client, mold_id):
    work_order_id, employee, items = prepare_work_order(client, mold_id)
    completed_at = datetime.now(TIMEZONE)
    started_at = completed_at - timedelta(hours=2)
    report = client.post(
        f"/api/v1/work-orders/{work_order_id}/report-complete",
        {
            "employee_id": employee["employee_id"],
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "work_summary": "真实HTTP冒烟测试已完成清洁、润滑和全部点检。",
            "inspection_results": [
                {
                    "knowledge_id": item["knowledge_id"],
                    "item": item["item"],
                    "result": "PASS",
                    "note": "冒烟测试通过",
                }
                for item in items
            ],
            "attachments": [],
            "client_request_id": client.request_id(f"complete-{mold_id}"),
        },
    )
    detail = client.get(f"/api/v1/work-orders/{work_order_id}")
    history = client.get(f"/api/v1/work-orders/{work_order_id}/history")
    status = client.get(f"/api/v1/molds/{mold_id}/maintenance-status")
    if detail["status"] != "COMPLETED" or not report["cycle_reset"]["performed"]:
        raise SmokeFailure(f"Normal flow did not complete for {mold_id}")
    if history["maintenance_history"] is None or status["cycle_count"] != 0:
        raise SmokeFailure(f"Cycle reset evidence missing for {mold_id}")
    return {
        "mold_id": mold_id,
        "work_order_id": work_order_id,
        "report_id": report["report_id"],
        "cycle_version": report["cycle_reset"]["cycle_version"],
    }


def run_abnormal_flow(client):
    subprocess.run(
        [sys.executable, str(ROOT / "manage.py"), "reset_probe_data"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": client.request_id("abnormal-scan")},
    )
    before = client.get("/api/v1/molds/MOLD-TEST-001")
    work_order_id, employee, _items = prepare_work_order(client, "MOLD-TEST-001")
    result = client.post(
        f"/api/v1/work-orders/{work_order_id}/report-abnormal",
        {
            "employee_id": employee["employee_id"],
            "abnormal_type": "COOLING_CHANNEL_BLOCKED",
            "description": "冒烟测试：冷却水路堵塞，常规保养无法处理。",
            "inspection_results": [
                {
                    "knowledge_id": "KB-INJECTION-002",
                    "item": "检查冷却水路",
                    "result": "FAIL",
                    "note": "发现堵塞",
                }
            ],
            "client_request_id": client.request_id("abnormal-report"),
        },
    )
    after = client.get("/api/v1/molds/MOLD-TEST-001")
    history = client.get(f"/api/v1/work-orders/{work_order_id}/history")
    before_cycle = (
        before["cycle_baseline_count"],
        before["cycle_baseline_time"],
        before["cycle_version"],
    )
    after_cycle = (
        after["cycle_baseline_count"],
        after["cycle_baseline_time"],
        after["cycle_version"],
    )
    if result["status"] != "ABNORMAL_REPORTED" or result["cycle_reset"]["performed"]:
        raise SmokeFailure("Abnormal flow did not preserve the cycle")
    if before_cycle != after_cycle or history["maintenance_history"] is not None:
        raise SmokeFailure("Abnormal reporting changed cycle state or created maintenance history")
    return {
        "mold_id": "MOLD-TEST-001",
        "work_order_id": work_order_id,
        "abnormal_report_id": result["abnormal_report_id"],
        "cycle_reset": False,
    }


def run_probe_flow(client):
    run = client.post(
        "/api/v1/probe/runs",
        {
            "platform_name": "local-http-smoke-client",
            "tester": "scripts/smoke_test.py",
            "mode": "STRICT",
            "client_request_id": client.request_id("probe-run"),
        },
    )
    run_id = run["run_id"]
    challenge = client.get(f"/api/v1/probe/runs/{run_id}/context")["challenge"]
    client.post(
        f"/api/v1/probe/runs/{run_id}/variable-test",
        {
            **challenge,
            "client_request_id": client.request_id("variable-test"),
        },
    )
    client.post(
        "/api/v1/probe/scheduler-heartbeat",
        {
            "run_id": run_id,
            "platform_name": "local-http-smoke-client",
            "evidence": "本地HTTP客户端触发；比赛平台定时能力仍需平台实测",
            "client_request_id": client.request_id("heartbeat"),
        },
    )
    return run_id


def main():
    external_url = os.getenv("PROBE_BASE_URL")
    base_url = external_url or DEFAULT_URL
    process = None
    try:
        if external_url is None:
            process = start_local_server()
        client = ProbeClient(base_url)
        wait_until_ready(client, process)
        meta = client.get("/api/v1/meta")
        if meta["authentication"] != "NONE":
            raise SmokeFailure("Probe server unexpectedly requires authentication")

        run_id = run_probe_flow(client)
        if external_url is not None:
            report = client.get(f"/api/v1/probe/runs/{run_id}/report")
            print(
                json.dumps(
                    {
                        "status": "PLATFORM_ENDPOINT_REACHABLE",
                        "base_url": base_url,
                        "probe_report": {
                            "run_id": run_id,
                            "tested": report["summary"]["tested"],
                            "total": report["summary"]["total"],
                        },
                        "business_workflows": "SKIPPED_TO_AVOID_REMOTE_DATA_RESET",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        client.post(
            "/api/v1/alerts/scan",
            {"client_request_id": client.request_id("normal-scan")},
        )
        normal_results = [
            run_normal_flow(client, mold_id)
            for mold_id in ["MOLD-TEST-001", "MOLD-TEST-002", "MOLD-TEST-007"]
        ]
        report = client.get(f"/api/v1/probe/runs/{run_id}/report")
        probe_report_summary = {
            "run_id": run_id,
            "tested": report["summary"]["tested"],
            "total": report["summary"]["total"],
        }
        abnormal_result = run_abnormal_flow(client)
        summary = {
            "status": "READY_FOR_PLATFORM_TEST",
            "base_url": base_url,
            "normal_workflows": normal_results,
            "abnormal_workflow": abnormal_result,
            "probe_report": probe_report_summary,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (SmokeFailure, subprocess.CalledProcessError) as exc:
        print(f"SMOKE_TEST_FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
