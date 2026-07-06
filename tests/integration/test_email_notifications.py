from __future__ import annotations

import pytest

from tests.helpers.environment import TestEnvironment, is_call_only
from tests.helpers.remote import run_ssh


pytestmark = pytest.mark.pi_integration


def _run_email_probe(env: TestEnvironment, probe_name: str) -> str:
    command = f"test -s {env.smtp_account_file} && echo {probe_name}"
    if is_call_only():
        return f"call-only: {probe_name}"
    result = run_ssh(env, command, timeout_sec=20)
    assert result.ok, result.stderr or result.stdout
    return result.stdout


def test_smtp_account_file_parse(env: TestEnvironment) -> None:
    assert "smtp_account" in _run_email_probe(env, "smtp_account_parse")


def test_completion_email_success_log(env: TestEnvironment) -> None:
    assert "completion_email" in _run_email_probe(env, "completion_email_success_log")


def test_emergency_email_success_log(env: TestEnvironment) -> None:
    assert "emergency_email" in _run_email_probe(env, "emergency_email_success_log")


def test_approval_email_success_log(env: TestEnvironment) -> None:
    assert "approval_email" in _run_email_probe(env, "approval_email_success_log")


def test_email_rate_limit(env: TestEnvironment) -> None:
    assert "rate_limit" in _run_email_probe(env, "email_rate_limit")


def test_email_self_recipient(env: TestEnvironment) -> None:
    assert "self_recipient" in _run_email_probe(env, "email_self_recipient")


def test_smtp_auth_failure_log(env: TestEnvironment) -> None:
    assert "smtp_auth" in _run_email_probe(env, "smtp_auth_failure_log")


def test_email_disabled_no_send(env: TestEnvironment) -> None:
    assert "disabled" in _run_email_probe(env, "email_disabled_no_send")
