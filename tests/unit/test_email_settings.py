import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def run_check(**overrides):
    environment = {
        **os.environ,
        "DJANGO_DB_ENGINE": "sqlite",
        "DJANGO_DB_PATH": ":memory:",
        "DJANGO_SECRET_KEY": "isolated-email-settings-test",
        "DJANGO_ALLOWED_HOSTS": "*",
        "EMAIL_USE_TLS": "false",
        "EMAIL_USE_SSL": "false",
        "MOLDGUARD_REQUIRE_SMTP": "false",
        **overrides,
    }
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_tls_and_ssl_cannot_both_be_enabled():
    result = run_check(EMAIL_USE_TLS="true", EMAIL_USE_SSL="true")
    assert result.returncode != 0
    assert "EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true" in result.stderr


def test_development_default_uses_locmem_backend():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config import settings; print(settings.EMAIL_BACKEND)",
        ],
        cwd=BASE_DIR,
        env={
            key: value
            for key, value in {
                **os.environ,
                "DJANGO_DB_ENGINE": "sqlite",
                "DJANGO_DB_PATH": ":memory:",
                "DJANGO_SECRET_KEY": "isolated-email-settings-test",
                "MOLDGUARD_REQUIRE_SMTP": "false",
            }.items()
            if key
            not in {
                "EMAIL_BACKEND",
                "EMAIL_HOST",
                "EMAIL_PORT",
                "EMAIL_HOST_USER",
                "EMAIL_HOST_PASSWORD",
                "EMAIL_USE_TLS",
                "EMAIL_USE_SSL",
                "EMAIL_TIMEOUT",
                "DEFAULT_FROM_EMAIL",
                "EMAIL_MESSAGE_ID_DOMAIN",
            }
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "django.core.mail.backends.locmem.EmailBackend"


def test_competition_requires_real_smtp_settings():
    result = run_check(
        MOLDGUARD_REQUIRE_SMTP="true",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    assert result.returncode != 0
    assert "Competition deployment requires Django's SMTP email backend" in result.stderr


def test_valid_smtp_settings_pass_django_check():
    result = run_check(
        MOLDGUARD_REQUIRE_SMTP="true",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.test.invalid",
        EMAIL_PORT="587",
        EMAIL_USE_TLS="true",
        DEFAULT_FROM_EMAIL="MoldGuard <moldguard@test.invalid>",
        EMAIL_MESSAGE_ID_DOMAIN="moldguard.test.invalid",
    )
    assert result.returncode == 0, result.stderr
