from types import SimpleNamespace

import pytest

from scripts.smoke_test import SmokeClient, SmokeFailure, reset_demo

REPORT_PAGE = """
<html><body>
<input name="csrfmiddlewaretoken" value="csrf-token">
<input name="submission_id" value="submission-id">
<input name="report_form_schema_version" value="REPORT-FORM-1.1">
<input name="knowledge_package_hash" value="knowledge-hash">
</body></html>
"""


def test_html_report_uses_explicit_public_report_origin(monkeypatch):
    client = SmokeClient(
        "http://127.0.0.1:18081",
        report_base_url="https://moldguard.example.com",
    )
    report_url = "https://moldguard.example.com/report/WO-SMOKE-001"
    requested = []

    def html_get(url):
        requested.append(("GET", url, None))
        return REPORT_PAGE

    def request(method, url, *, body=None, headers=None):
        requested.append((method, url, headers))
        return 200, "text/html", "<html>报工已完成</html>"

    monkeypatch.setattr(client, "html_get", html_get)
    monkeypatch.setattr(client, "_request", request)

    client.html_report_normal("WO-SMOKE-001", report_url)

    assert requested[0] == ("GET", report_url, None)
    assert requested[1][0:2] == ("POST", report_url)
    assert requested[1][2]["Referer"] == report_url


def test_html_report_rejects_unexpected_report_origin():
    client = SmokeClient(
        "http://127.0.0.1:18081",
        report_base_url="https://moldguard.example.com",
    )

    with pytest.raises(SmokeFailure, match="outside the expected report origin"):
        client.html_report_normal(
            "WO-SMOKE-001",
            "https://attacker.example/report/WO-SMOKE-001",
        )


def test_reset_demo_verifies_canonical_dataset(monkeypatch):
    commands = []

    def run(command, *, check):
        commands.append((command, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("scripts.smoke_test.subprocess.run", run)

    reset_demo("competition.env")

    assert len(commands) == 2
    assert commands[0][0][-2:] == ["reset_demo_data", "--confirm"]
    assert commands[1][0][-2:] == ["manage.py", "verify_demo_data"]
    assert all(check is False for _, check in commands)
