from django.core.files.uploadedfile import SimpleUploadedFile


def scan_work_order(api_client, mold_id, suffix):
    response = api_client.post(
        "/api/v1/alerts/scan",
        {"client_request_id": f"scan-{suffix}", "mold_ids": [mold_id]},
        format="json",
    )
    assert response.status_code == 200, response.data
    result = response.data["data"]["results"][0]
    assert result["status"] == "TRIGGERED"
    return result["work_order_id"], result["alert_id"]


def assign_work_order(api_client, work_order_id, employee_id, suffix):
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/assign",
        {"client_request_id": f"assign-{suffix}", "employee_id": employee_id},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["data"]["new_status"] == "ASSIGNED"
    return response.data["data"]


def save_knowledge(api_client, work_order_id, knowledge_payload, suffix):
    payload = {
        "client_request_id": f"knowledge-{suffix}",
        **knowledge_payload,
    }
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/knowledge", payload, format="json"
    )
    assert response.status_code == 200, response.data
    assert len(response.data["data"]["knowledge_package_hash"]) == 64
    return response.data["data"]


def send_assignment_email(api_client, work_order_id, suffix):
    response = api_client.post(
        f"/api/v1/work-orders/{work_order_id}/send-email",
        {"client_request_id": f"send-email-{suffix}"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["data"]["new_email_status"] == "SENT"
    return response.data["data"]


def assigned_with_knowledge(api_client, knowledge_payload, *, mold_id, employee_id, suffix):
    work_order_id, alert_id = scan_work_order(api_client, mold_id, suffix)
    assign_work_order(api_client, work_order_id, employee_id, suffix)
    knowledge = save_knowledge(api_client, work_order_id, knowledge_payload, suffix)
    return work_order_id, alert_id, knowledge["knowledge_package_hash"]


def normal_report_payload(suffix, knowledge_hash):
    return {
        "client_request_id": f"report-{suffix}",
        "report_type": "NORMAL",
        "report_summary": "已完成保养并逐项检查",
        "inspection_results": [
            {
                "knowledge_id": "CHK-INJ-001",
                "result": "PASS",
                "not_applicable_reason": "",
                "abnormal_note": "",
            },
            {
                "knowledge_id": "CHK-INJ-010",
                "result": "PASS",
                "not_applicable_reason": "",
                "abnormal_note": "",
            },
        ],
        "abnormal_items": [],
        "photos": [],
        "parts_replaced": [],
        "source_fault_id": None,
        "actual_work_hours": "2.50",
        "abnormal_next_action": None,
        "knowledge_package_hash": knowledge_hash,
    }


def abnormal_report_payload(suffix, knowledge_hash, *, next_action="CONTINUE_PROCESSING"):
    payload = normal_report_payload(suffix, knowledge_hash)
    payload.update(
        {
            "report_type": "ABNORMAL",
            "report_summary": "发现冷却水路堵塞，常规保养无法处理",
            "abnormal_items": [{"item": "冷却水路", "description": "水路堵塞，需要后续处理"}],
            "actual_work_hours": "1.50",
            "abnormal_next_action": next_action,
        }
    )
    payload["inspection_results"][1].update({"result": "FAIL", "abnormal_note": "水路不通"})
    return payload


def report_image(name="report-evidence.png"):
    return SimpleUploadedFile(
        name,
        b"\x89PNG\r\n\x1a\n" + b"moldguard-report-evidence",
        content_type="image/png",
    )


def complete_review_payload(suffix, knowledge_hash, *, confidence="0.9500"):
    normal = normal_report_payload(suffix, knowledge_hash)
    return {
        "client_request_id": f"review-{suffix}",
        "decision": "COMPLETE",
        "assessment_summary": "图片与文字能够证明必检项目已完成",
        "confidence": confidence,
        "knowledge_package_hash": knowledge_hash,
        "inspection_results": normal["inspection_results"],
        "abnormal_items": [],
        "abnormal_next_action": None,
        "reason_codes": ["ALL_REQUIRED_ITEMS_CONFIRMED"],
        "knowledge_sources": ["MOLDGUARD-KB-1.2"],
        "review_model": "competition-agent",
    }
