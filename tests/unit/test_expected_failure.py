from __future__ import annotations

import pytest

from tests.helpers.artifacts import TestResult
from tests.helpers.environment import load_test_environment
from tests.helpers.e2e_runner import assert_e2e_passed, classify_e2e_failure
from tests.helpers.remote import CommandResult


def result(status: str, expected_result: str, failure_domain: str | None = None) -> TestResult:
    return TestResult(
        case_name="case",
        stage="stage",
        status=status,
        expected_result=expected_result,
        failure_domain=failure_domain,
        exit_code=1,
        artifacts_dir="",
        result_json="",
        message="message",
    )


def test_expected_failure_passes_when_failure_detected() -> None:
    assert_e2e_passed(result("expected_failure_detected", "expected_failure"))


def test_expected_failure_fails_when_operation_succeeds() -> None:
    with pytest.raises(AssertionError):
        assert_e2e_passed(result("pass", "expected_failure"))


def test_normal_case_fails_when_verification_false() -> None:
    with pytest.raises(AssertionError):
        assert_e2e_passed(result("fail", "pass", "implementation"))


def test_infrastructure_failure_is_not_counted_as_expected_failure() -> None:
    failed = result("infrastructure_failure", "expected_failure", "capture_board")
    with pytest.raises(AssertionError):
        assert_e2e_passed(failed)
    assert classify_e2e_failure(failed) == "capture_board"


def test_expected_failure_marker_from_runner_counts_as_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.helpers import e2e_runner

    def fake_run_ssh(env: object, command: str, *, timeout_sec: int) -> CommandResult:
        return CommandResult(
            args=["ssh"],
            exit_code=0,
            stdout="RESULT EXPECTED FAILURE: unsupported drag was reported as expected",
            stderr="",
            elapsed_sec=0.1,
        )

    monkeypatch.setattr(e2e_runner, "run_ssh", fake_run_ssh)

    detected = e2e_runner.run_e2e_case_by_name(
        load_test_environment(),
        "stage01_scenario06_expected_failure_unsupported_drag",
        require_preflight=False,
    )

    assert detected.status == "expected_failure_detected"
    assert_e2e_passed(detected)
