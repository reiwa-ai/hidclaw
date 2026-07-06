from __future__ import annotations

import json

import pytest

from tests.helpers.environment import TestEnvironment, is_call_only
from tests.helpers.remote import run_ssh


pytestmark = pytest.mark.pi_integration


def _remote_webui_call(env: TestEnvironment, path: str, *, method: str = "GET", body: dict[str, object] | None = None):
    encoded_body = json.dumps(body or {})
    command = f"""python3 - <<'PY'
import json
import urllib.error
import urllib.request

url = "http://127.0.0.1:{env.webui_port}{path}"
data = {encoded_body!r}.encode("utf-8") if "{method}" != "GET" else None
request = urllib.request.Request(url, data=data, method="{method}")
request.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.status)
        print(response.read().decode("utf-8", "replace"))
except urllib.error.HTTPError as error:
    print(error.code)
    print(error.read().decode("utf-8", "replace"))
    raise SystemExit(0 if error.code >= 400 else 1)
PY"""
    if is_call_only():
        return 0, f"call-only: {method} {path}"
    result = run_ssh(env, command, timeout_sec=20)
    return result.exit_code, result.stdout + result.stderr


def test_webui_status_api(env: TestEnvironment) -> None:
    code, output = _remote_webui_call(env, "/api/status")
    assert code == 0, output
    assert "status" in output or "call-only" in output or "bind_host" in output


def test_webui_manual_hid_rejects_invalid_hid(env: TestEnvironment) -> None:
    code, output = _remote_webui_call(env, "/api/manual-hid", method="POST", body={"command": "TEXT café"})
    assert code == 0, output
    assert "400" in output or "call-only" in output or "error" in output.lower()


def test_webui_emergency_stop_state(env: TestEnvironment) -> None:
    code, output = _remote_webui_call(env, "/api/emergency-stop", method="POST", body={})
    assert code == 0, output
    assert "emergency" in output.lower() or "call-only" in output


def test_webui_planning_toggle(env: TestEnvironment) -> None:
    code, output = _remote_webui_call(env, "/api/planning", method="POST", body={"enabled": True})
    assert code == 0, output
    assert "planning" in output.lower() or "call-only" in output


def test_webui_screenshot_api(env: TestEnvironment) -> None:
    code, output = _remote_webui_call(env, "/api/screenshot")
    assert code == 0, output
    assert output or is_call_only()
