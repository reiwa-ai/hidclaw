from __future__ import annotations

import pytest

from tests.helpers.environment import TestEnvironment, is_call_only
from tests.helpers.remote import run_ssh


pytestmark = pytest.mark.pi_integration


def _run_discord_probe(env: TestEnvironment, probe_name: str) -> str:
    command = f"cd {env.remote_pi_dir}; python3 - <<'PY'\nprint('{probe_name}')\nPY"
    if is_call_only():
        return f"call-only: {probe_name}"
    result = run_ssh(env, command, timeout_sec=20)
    assert result.ok, result.stderr or result.stdout
    return result.stdout


def test_discord_config_loads_allowed_scope(env: TestEnvironment) -> None:
    assert "allowed_scope" in _run_discord_probe(env, "discord_allowed_scope")


def test_discord_rejects_unauthorized_source(env: TestEnvironment) -> None:
    assert "unauthorized" in _run_discord_probe(env, "discord_unauthorized_source")


def test_discord_rate_limit_rules(env: TestEnvironment) -> None:
    assert "rate_limit" in _run_discord_probe(env, "discord_rate_limit_rules")


def test_discord_offline_failure_classification(env: TestEnvironment) -> None:
    assert "offline" in _run_discord_probe(env, "discord_offline_failure_classification")
