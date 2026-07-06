from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .remote import CommandResult, copy_pi_sources, run_local, run_ssh


@dataclass(frozen=True)
class TestEnvironment:
    __test__ = False

    pi_host: str
    pi_user: str
    ssh_key: Path
    remote_pi_dir: str
    openai_api_key_file: str
    smtp_account_file: str
    capture_device: str
    uart_port: str
    webui_host: str
    webui_port: int
    runtime_dir: str
    artifacts_dir: str
    target_pc_os: str


@dataclass(frozen=True)
class CheckResult:
    __test__ = False

    name: str
    ok: bool
    message: str
    command: str = ""
    failure_domain: str | None = None
    command_result: CommandResult | None = None


@dataclass(frozen=True)
class PreflightResult:
    __test__ = False

    ok: bool
    checks: tuple[CheckResult, ...]


def is_call_only() -> bool:
    return os.environ.get("PICO_HID_TEST_CALL_ONLY") == "1"


def load_test_environment(
    *,
    pi_host: str = "192.168.11.6",
    pi_user: str = "nama",
    ssh_key: Path = Path("id_rsa"),
    remote_pi_dir: str = "/home/nama/pi",
    webui_port: int = 18080,
) -> TestEnvironment:
    return TestEnvironment(
        pi_host=pi_host,
        pi_user=pi_user,
        ssh_key=ssh_key,
        remote_pi_dir=remote_pi_dir,
        openai_api_key_file="/home/nama/openai-api-key.txt",
        smtp_account_file="/home/nama/mail-send-vert.txt",
        capture_device="/dev/video0",
        uart_port="/dev/serial0",
        webui_host=pi_host,
        webui_port=webui_port,
        runtime_dir=f"{remote_pi_dir}/runtime/test",
        artifacts_dir=f"{remote_pi_dir}/captures",
        target_pc_os="windows",
    )


def _planned(name: str, command: str) -> CheckResult:
    return CheckResult(name=name, ok=True, message="call-only: command construction verified", command=command)


def _check_result(name: str, command: str, result: CommandResult, failure_domain: str) -> CheckResult:
    output = (result.stdout or result.stderr).strip()
    return CheckResult(
        name=name,
        ok=result.ok,
        message=output or ("ok" if result.ok else "failed"),
        command=command,
        failure_domain=None if result.ok else failure_domain,
        command_result=result,
    )


def _running_on_remote_pi(env: TestEnvironment) -> bool:
    return Path.cwd().as_posix() == env.remote_pi_dir


def _run_pi_command(env: TestEnvironment, command: str, *, timeout_sec: int) -> CommandResult:
    if _running_on_remote_pi(env):
        return run_local(["bash", "-lc", command], cwd=Path.cwd(), timeout_sec=timeout_sec)
    return run_ssh(env, command, timeout_sec=timeout_sec)


def assert_check_ok(result: CheckResult) -> None:
    assert result.ok, f"{result.name} failed [{result.failure_domain}]: {result.message}\n{result.command}"


def check_pi_ssh(env: TestEnvironment) -> CheckResult:
    command = "hostname"
    if is_call_only():
        return _planned("pi_ssh", command)
    return _check_result("pi_ssh", command, _run_pi_command(env, command, timeout_sec=20), "pi_ssh")


def check_pi_required_files(env: TestEnvironment) -> CheckResult:
    command = (
        "test -d {pi} && test -s {api_key} && test -s {smtp_file}"
    ).format(pi=env.remote_pi_dir, api_key=env.openai_api_key_file, smtp_file=env.smtp_account_file)
    if is_call_only():
        return _planned("pi_required_files", command)
    return _check_result("pi_required_files", command, _run_pi_command(env, command, timeout_sec=20), "pi_dependency")


def check_pi_devices(env: TestEnvironment) -> CheckResult:
    command = f"test -e {env.capture_device} && test -e {env.uart_port}"
    if is_call_only():
        return _planned("pi_devices", command)
    return _check_result("pi_devices", command, _run_pi_command(env, command, timeout_sec=20), "capture_board")


def check_pi_python_dependencies(env: TestEnvironment) -> CheckResult:
    command = f"cd {env.remote_pi_dir}; python3 - <<'PY'\nimport flask, openai, serial, cv2\nPY"
    if is_call_only():
        return _planned("pi_python_dependencies", command)
    return _check_result(
        "pi_python_dependencies",
        command,
        _run_pi_command(env, command, timeout_sec=30),
        "pi_dependency",
    )


def check_capture_smoke(env: TestEnvironment, *, output_name: str = "preflight_capture.png") -> CheckResult:
    output_path = f"{env.artifacts_dir}/{output_name}"
    command = (
        f"cd {env.remote_pi_dir}; "
        f"python3 controller.py --capture-only --save-screenshot {output_path}"
    )
    if is_call_only():
        return _planned("capture_smoke", command)
    return _check_result("capture_smoke", command, _run_pi_command(env, command, timeout_sec=30), "capture_board")


def check_pico_uart_smoke(env: TestEnvironment) -> CheckResult:
    command = f"cd {env.remote_pi_dir}; python3 hid_client.py PING --port {env.uart_port}"
    if is_call_only():
        return _planned("pico_uart_smoke", command)
    return _check_result("pico_uart_smoke", command, _run_pi_command(env, command, timeout_sec=20), "pico_uart")


def check_openai_key(env: TestEnvironment) -> CheckResult:
    command = f"test -s {env.openai_api_key_file}"
    if is_call_only():
        return _planned("openai_key", command)
    return _check_result("openai_key", command, _run_pi_command(env, command, timeout_sec=20), "openai_api")


def copy_sources_to_pi(env: TestEnvironment) -> CheckResult:
    command = f"scp -r pi {env.pi_user}@{env.pi_host}:{Path(env.remote_pi_dir).parent}/"
    if is_call_only():
        return _planned("copy_pi_sources", command)
    if _running_on_remote_pi(env):
        return CheckResult("copy_pi_sources", ok=True, message="already running on remote Pi", command=command)
    return _check_result("copy_pi_sources", command, copy_pi_sources(env), "pi_ssh")


def run_hardware_preflight(env: TestEnvironment) -> PreflightResult:
    checks = [
        check_pi_ssh(env),
        copy_sources_to_pi(env),
        check_pi_python_dependencies(env),
        check_pi_required_files(env),
        check_pi_devices(env),
        check_capture_smoke(env),
        check_pico_uart_smoke(env),
        check_openai_key(env),
    ]
    return PreflightResult(ok=all(check.ok for check in checks), checks=tuple(checks))
