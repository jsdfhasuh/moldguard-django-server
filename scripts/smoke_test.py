#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid


class SmokeFailure(RuntimeError):
    pass


def request_json(base_url, method, path, payload=None):
    body = None
    headers = {"Accept": "application/json", "X-Request-ID": f"smoke-{uuid.uuid4().hex}"}
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise SmokeFailure(
            f"{method} {path} returned {exc.code}: {exc.read().decode(errors='replace')}"
        ) from exc
    if result.get("code") != "SUCCESS" or not result.get("request_id"):
        raise SmokeFailure(f"{method} {path} returned an invalid envelope: {result}")
    return result["data"]


def run_health(base_url):
    health = request_json(base_url, "GET", "/api/v1/health")
    meta = request_json(base_url, "GET", "/api/v1/meta")
    if health.get("status") != "ok":
        raise SmokeFailure("health status is not ok")
    if meta.get("knowledge_snapshot_version") != "MOLDGUARD-KB-1.2":
        raise SmokeFailure("unexpected knowledge version")


def run_workflow(base_url):
    run_id = uuid.uuid4().hex
    scan = request_json(
        base_url,
        "POST",
        "/api/v1/alerts/scan",
        {
            "client_request_id": f"smoke-scan-{run_id}",
            "mold_ids": ["DEMO-INJ-COUNT-TIME"],
        },
    )
    if scan["triggered_count"] != 1:
        raise SmokeFailure(f"workflow mold did not trigger: {scan}")
    work_order_id = scan["results"][0]["work_order_id"]
    candidates = request_json(base_url, "GET", f"/api/v1/work-orders/{work_order_id}/candidates")
    if not candidates["candidates"]:
        raise SmokeFailure("no assignment candidates")
    assignee_id = candidates["candidates"][0]["employee_id"]
    assigned = request_json(
        base_url,
        "POST",
        f"/api/v1/work-orders/{work_order_id}/assign",
        {
            "client_request_id": f"smoke-assign-{run_id}",
            "employee_id": assignee_id,
        },
    )
    if assigned["new_status"] != "ASSIGNED":
        raise SmokeFailure("assignment did not reach ASSIGNED")
    knowledge = request_json(
        base_url,
        "POST",
        f"/api/v1/work-orders/{work_order_id}/knowledge",
        {
            "client_request_id": f"smoke-knowledge-{run_id}",
            "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
            "title": "HTTP smoke DEMO点检包",
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
    email = request_json(base_url, "GET", f"/api/v1/work-orders/{work_order_id}/email-context")
    if email["knowledge_package_hash"] != knowledge["knowledge_package_hash"]:
        raise SmokeFailure("email and knowledge hashes differ")
    report = request_json(
        base_url,
        "POST",
        f"/api/v1/work-orders/{work_order_id}/report",
        {
            "client_request_id": f"smoke-report-{run_id}",
            "report_type": "NORMAL",
            "report_summary": "HTTP smoke已完成保养并逐项检查",
            "inspection_results": [
                {
                    "knowledge_id": "CHK-INJ-001",
                    "result": "PASS",
                    "not_applicable_reason": "",
                    "abnormal_note": "",
                }
            ],
            "abnormal_items": [],
            "photos": [],
            "parts_replaced": [],
            "source_fault_id": None,
            "actual_work_hours": "1.00",
            "abnormal_next_action": None,
            "knowledge_package_hash": knowledge["knowledge_package_hash"],
        },
    )
    if report["new_status"] != "COMPLETED":
        raise SmokeFailure("normal report did not complete work order")
    records = request_json(base_url, "GET", "/api/v1/molds/DEMO-INJ-COUNT-TIME/records")
    if not any(item["work_order_id"] == work_order_id for item in records["records"]):
        raise SmokeFailure("maintenance record was not created")


def main():
    parser = argparse.ArgumentParser(description="MoldGuard HTTP smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument(
        "--workflow",
        action="store_true",
        help="Run the state-changing scan-to-report DEMO workflow on a freshly reset dataset.",
    )
    args = parser.parse_args()
    try:
        run_health(args.base_url)
        if args.workflow:
            run_workflow(args.base_url)
    except (SmokeFailure, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    print("MoldGuard HTTP smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
