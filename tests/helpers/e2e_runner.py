from __future__ import annotations

from pathlib import Path
import shlex

from pico_hid_bridge.e2e.cases import ALL_CASES, CASES
from pico_hid_bridge.e2e.model import E2ETestCase

from .artifacts import TestResult
from .environment import TestEnvironment, is_call_only, run_hardware_preflight
from .remote import run_ssh


INFRASTRUCTURE_DOMAINS = {
    "pi_ssh",
    "pi_dependency",
    "pi_process",
    "pico_uart",
    "capture_board",
    "target_pc_state",
    "openai_api",
}

EXPECTED_FAILURE_MARKER = "result expected failure"


def list_e2e_cases(
    *,
    stage: str | None = None,
    category: str | None = None,
    include_expected_failure: bool = True,
) -> list[E2ETestCase]:
    cases = list(ALL_CASES)
    if stage is not None:
        cases = [case for case in cases if case.stage == stage]
    if category == "expected_failure":
        cases = [case for case in cases if "expected_failure" in case.name]
    elif category is not None:
        cases = [case for case in cases if category in case.name or category in case.stage]
    if not include_expected_failure:
        cases = [case for case in cases if "expected_failure" not in case.name]
    return cases


def _is_expected_failure(case: E2ETestCase, expected_failure: bool | None) -> bool:
    return bool(expected_failure) if expected_failure is not None else "expected_failure" in case.name


def _build_e2e_command(
    env: TestEnvironment,
    case_name: str,
    *,
    api_key_file: str | None,
    output_root: str | None,
    pre_test_close_attempts: int,
    pre_test_close_delay: float,
    max_action_turns: int,
    max_verify_turns: int,
    api_timeout: float,
) -> str:
    parts = [
        "cd",
        shlex.quote(env.remote_pi_dir),
        "&&",
        "python3",
        "run_e2e_case.py",
        shlex.quote(case_name),
        "--api-key-file",
        shlex.quote(api_key_file or env.openai_api_key_file),
        "--output-root",
        shlex.quote(output_root or env.artifacts_dir),
        "--pre-test-close-attempts",
        str(pre_test_close_attempts),
        "--pre-test-close-delay",
        str(pre_test_close_delay),
        "--max-action-turns",
        str(max_action_turns),
        "--max-verify-turns",
        str(max_verify_turns),
        "--api-timeout",
        str(api_timeout),
    ]
    return " ".join(parts)


def run_e2e_case_by_name(
    env: TestEnvironment,
    case_name: str,
    *,
    api_key_file: str | None = None,
    output_root: str | None = None,
    pre_test_close_attempts: int = 8,
    pre_test_close_delay: float = 0.5,
    max_action_turns: int = 5,
    max_verify_turns: int = 5,
    api_timeout: float = 60.0,
    expected_failure: bool | None = None,
    require_preflight: bool = True,
) -> TestResult:
    if case_name not in CASES:
        return TestResult(case_name, "", "error", "known_case", "test_spec", 2, "", "", "unknown E2E case")

    case = CASES[case_name]
    expects_failure = _is_expected_failure(case, expected_failure)
    command = _build_e2e_command(
        env,
        case_name,
        api_key_file=api_key_file,
        output_root=output_root,
        pre_test_close_attempts=pre_test_close_attempts,
        pre_test_close_delay=pre_test_close_delay,
        max_action_turns=max_action_turns,
        max_verify_turns=max_verify_turns,
        api_timeout=api_timeout,
    )

    if is_call_only():
        return TestResult(
            case_name=case.name,
            stage=case.stage,
            status="expected_failure_detected" if expects_failure else "pass",
            expected_result="expected_failure" if expects_failure else "pass",
            failure_domain=None,
            exit_code=0,
            artifacts_dir=output_root or env.artifacts_dir,
            result_json="",
            message=f"call-only: {command}",
        )

    if require_preflight:
        preflight = run_hardware_preflight(env)
        if not preflight.ok:
            failed = next((check for check in preflight.checks if not check.ok), None)
            return TestResult(
                case.name,
                case.stage,
                "infrastructure_failure",
                "expected_failure" if expects_failure else "pass",
                failed.failure_domain if failed else "unknown",
                2,
                output_root or env.artifacts_dir,
                "",
                failed.message if failed else "preflight failed",
            )

    result = run_ssh(env, command, timeout_sec=max(120, int(api_timeout) * 10))
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    domain = classify_e2e_output(result.exit_code, combined)

    if result.exit_code == 0:
        if expects_failure and EXPECTED_FAILURE_MARKER in combined.lower():
            status = "expected_failure_detected"
            message = "expected failure detected"
        else:
            status = "fail" if expects_failure else "pass"
            message = "expected failure scenario succeeded unexpectedly" if expects_failure else "E2E passed"
    elif expects_failure and domain not in INFRASTRUCTURE_DOMAINS:
        status = "expected_failure_detected"
        message = "expected failure detected"
    elif domain in INFRASTRUCTURE_DOMAINS:
        status = "infrastructure_failure"
        message = "infrastructure failure"
    else:
        status = "fail"
        message = "E2E failed"

    return TestResult(
        case.name,
        case.stage,
        status,
        "expected_failure" if expects_failure else "pass",
        None if status in {"pass", "expected_failure_detected"} else domain,
        result.exit_code,
        output_root or env.artifacts_dir,
        "",
        f"{message}\n{combined}".strip(),
    )


def assert_e2e_passed(result: TestResult) -> None:
    if result.expected_result == "expected_failure":
        assert result.status == "expected_failure_detected", result.message
    else:
        assert result.status == "pass", result.message


def classify_e2e_output(exit_code: int, output: str) -> str:
    text = output.lower()
    if "permission denied" in text or "could not resolve hostname" in text or "connection timed out" in text:
        return "pi_ssh"
    if "no module named" in text or "pip" in text:
        return "pi_dependency"
    if "failed to open capture device" in text or "failed to read frame" in text or "mean_brightness" in text:
        return "capture_board"
    if "serial" in text or "uart" in text or "send failed" in text:
        return "pico_uart"
    if "missing api key" in text or "401" in text or "403" in text or "429" in text:
        return "openai_api"
    if "smtp" in text:
        return "smtp"
    if "discord" in text:
        return "discord"
    if "unknown e2e case" in text or "invalid choice" in text:
        return "test_spec"
    if exit_code != 0 and ("unsupported" in text or "result fail" in text or "result error" in text):
        return "implementation"
    return "unknown"


def classify_e2e_failure(result: TestResult) -> str:
    if result.failure_domain:
        return result.failure_domain
    return classify_e2e_output(result.exit_code, result.message)
