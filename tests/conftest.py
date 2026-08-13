import pytest
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_demo(db):
    call_command("seed_demo_data", verbosity=0)


@pytest.fixture
def knowledge_payload():
    return {
        "knowledge_snapshot_version": "MOLDGUARD-KB-1.2",
        "title": "DEMO注塑模具周期保养点检",
        "items": [
            {
                "knowledge_id": "CHK-INJ-001",
                "item": "模具外观",
                "criteria": "配件齐全完好无异常",
                "method": "目视",
                "required": True,
            },
            {
                "knowledge_id": "CHK-INJ-010",
                "item": "冷却水路",
                "criteria": "表面干净清洁无水质残留",
                "method": "目视",
                "required": True,
            },
        ],
        "safety_notes": ["设备停止、断电并防止误启动"],
        "source_documents": ["MOLDGUARD-KB-1.2"],
    }
