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
