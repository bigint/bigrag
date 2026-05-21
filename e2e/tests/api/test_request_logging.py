from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

from tests._helpers import assert_envelope

E2E_ROOT = Path(__file__).resolve().parents[2]


def _api_logs() -> str:
    command = [
        "docker",
        "compose",
        "-p",
        os.environ.get("E2E_PROJECT", "bigrag-e2e"),
        "-f",
        "../docker-compose.yml",
        "-f",
        "docker-compose.e2e.yml",
        "logs",
        "--no-color",
        "--since",
        "5m",
        "bigrag-api",
    ]
    result = subprocess.run(
        command,
        cwd=E2E_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return f"{result.stdout}\n{result.stderr}"


async def _api_logs_containing(marker: str) -> str:
    logs = ""
    for _ in range(20):
        logs = _api_logs()
        if marker in logs:
            return logs
        await asyncio.sleep(0.25)
    return logs


async def test_request_logs_redact_secret_like_query_params_and_url_userinfo(
    unauth_client: httpx.AsyncClient,
    api_base_url: str,
) -> None:
    if not api_base_url.startswith(("http://localhost:", "http://127.0.0.1:")):
        pytest.skip("log assertion requires the local e2e Docker Compose stack")

    marker = uuid.uuid4().hex
    safe_marker = f"REQUEST_LOG_SAFE_{marker}"
    secret_values = {
        "api_secret_key": f"REQUEST_LOG_API_SECRET_KEY_{marker}",
        "secret_key": f"REQUEST_LOG_SECRET_KEY_{marker}",
        "apikey": f"REQUEST_LOG_APIKEY_{marker}",
        "signature": f"REQUEST_LOG_SIGNATURE_{marker}",
        "credential": f"REQUEST_LOG_CREDENTIAL_{marker}",
        "accessToken": f"REQUEST_LOG_ACCESS_TOKEN_{marker}",
        "idToken": f"REQUEST_LOG_ID_TOKEN_{marker}",
        "clientSecret": f"REQUEST_LOG_CLIENT_SECRET_{marker}",
        "x_api_key": f"REQUEST_LOG_X_API_KEY_{marker}",
    }
    referer_user = f"REQUEST_LOG_USERINFO_USER_{marker}"
    referer_password = f"REQUEST_LOG_USERINFO_PASSWORD_{marker}"
    referer_secret = f"REQUEST_LOG_REFERER_SECRET_{marker}"
    referer = (
        f"https://{referer_user}:{referer_password}@example.test/callback"
        f"?api_secret_key={referer_secret}&probe={safe_marker}#fragment"
    )

    response = await unauth_client.get(
        "/health",
        params={**secret_values, "probe": safe_marker},
        headers={"Referer": referer},
    )
    assert_envelope(response, 200)

    logs = await _api_logs_containing(safe_marker)
    assert safe_marker in logs
    for value in [*secret_values.values(), referer_user, referer_password, referer_secret]:
        assert value not in logs
    assert "[REDACTED]" in logs
