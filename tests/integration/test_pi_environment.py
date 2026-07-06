from __future__ import annotations

import pytest

from tests.helpers.environment import (
    TestEnvironment,
    assert_check_ok,
    check_capture_smoke,
    check_openai_key,
    check_pi_devices,
    check_pi_python_dependencies,
    check_pi_required_files,
    check_pi_ssh,
    check_pico_uart_smoke,
)


pytestmark = pytest.mark.pi_integration


def test_pi_ssh_connects(env: TestEnvironment) -> None:
    assert_check_ok(check_pi_ssh(env))


def test_pi_required_files_exist(env: TestEnvironment) -> None:
    assert_check_ok(check_pi_required_files(env))
    assert_check_ok(check_openai_key(env))


def test_pi_python_dependencies(env: TestEnvironment) -> None:
    assert_check_ok(check_pi_python_dependencies(env))


def test_pi_capture_device_exists(env: TestEnvironment) -> None:
    result = check_pi_devices(env)
    assert_check_ok(result)
    assert env.capture_device in result.command


def test_pi_uart_device_exists(env: TestEnvironment) -> None:
    result = check_pi_devices(env)
    assert_check_ok(result)
    assert env.uart_port in result.command


def test_pi_capture_smoke(env: TestEnvironment) -> None:
    assert_check_ok(check_capture_smoke(env))


def test_pi_pico_uart_smoke(env: TestEnvironment) -> None:
    result = check_pico_uart_smoke(env)
    assert_check_ok(result)
    assert "PING" in result.command
