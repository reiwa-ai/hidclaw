from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pico_hid_bridge.e2e.runner as e2e_hid_runner
from pico_hid_bridge.e2e.cases import (
    CASES,
    OPEN_BROWSER,
    STAGE02_SCENARIO02_OPERATION_LOG,
    STAGE02_SCENARIO03_SCREENSHOT_LOG,
    STAGE03_SCENARIO01_EMERGENCY_STOP,
    STAGE04_SCENARIO01_LAN_WEBUI_STATUS,
)
from pico_hid_bridge.operation_log import OperationLogStore


def test_execute_actions_waits_between_supported_actions(monkeypatch: Any) -> None:
    executed: list[str] = []
    sleeps: list[float] = []

    def fake_execute_supported_action(action: dict[str, str], args: object) -> bool:
        executed.append(action["type"])
        return True

    monkeypatch.setattr(e2e_hid_runner, "execute_supported_action", fake_execute_supported_action)
    monkeypatch.setattr(e2e_hid_runner.time, "sleep", sleeps.append)

    e2e_hid_runner.execute_actions(
        [
            {"type": "keypress"},
            {"type": "type"},
            {"type": "keypress"},
        ],
        SimpleNamespace(inter_action_delay=0.25),
    )

    assert executed == ["keypress", "type", "keypress"]
    assert sleeps == [0.25, 0.25, 0.25]


def test_execute_actions_passes_supported_mouse_actions(monkeypatch: Any) -> None:
    executed: list[str] = []

    def fake_execute_supported_action(action: dict[str, str], args: object) -> bool:
        executed.append(action["type"])
        return True

    monkeypatch.setattr(e2e_hid_runner, "execute_supported_action", fake_execute_supported_action)
    monkeypatch.setattr(e2e_hid_runner.time, "sleep", lambda seconds: None)

    e2e_hid_runner.execute_actions(
        [
            {"type": "click"},
            {"type": "move"},
            {"type": "double_click"},
        ],
        SimpleNamespace(inter_action_delay=0.0),
    )

    assert executed == ["click", "move", "double_click"]


def test_execute_actions_waits_for_long_type_action(monkeypatch: Any) -> None:
    sleeps: list[float] = []

    def fake_execute_supported_action(action: dict[str, str], args: object) -> bool:
        return True

    monkeypatch.setattr(e2e_hid_runner, "execute_supported_action", fake_execute_supported_action)
    monkeypatch.setattr(e2e_hid_runner.time, "sleep", sleeps.append)

    e2e_hid_runner.execute_actions(
        [{"type": "type", "text": "A" * 100}],
        SimpleNamespace(inter_action_delay=0.25, type_action_delay_per_char=0.08),
    )

    assert sleeps == [8.0]


def test_stage02_steps_defer_visual_success_to_log_validation() -> None:
    assert e2e_hid_runner.step_uses_stage_specific_validation(STAGE02_SCENARIO03_SCREENSHOT_LOG)
    assert not e2e_hid_runner.step_uses_stage_specific_validation(OPEN_BROWSER)


def test_stage03_through_stage09_use_webui_runner() -> None:
    assert e2e_hid_runner.case_uses_webui_runner(STAGE03_SCENARIO01_EMERGENCY_STOP)
    assert e2e_hid_runner.case_uses_webui_runner(STAGE04_SCENARIO01_LAN_WEBUI_STATUS)
    assert e2e_hid_runner.case_uses_webui_runner(CASES["stage05_scenario06_calculator_plan"])
    assert e2e_hid_runner.case_uses_webui_runner(CASES["stage06_scenario01_file_save_requires_approval"])
    assert e2e_hid_runner.case_uses_webui_runner(CASES["stage07_scenario01_completion_email_log"])
    assert e2e_hid_runner.case_uses_webui_runner(CASES["stage08_scenario01_progress_display"])
    assert e2e_hid_runner.case_uses_webui_runner(CASES["stage09_scenario01_operation_token_usage"])
    assert not e2e_hid_runner.case_uses_webui_runner(OPEN_BROWSER)


def test_expected_planning_failure_signal_accepts_safe_approval_pending() -> None:
    assert e2e_hid_runner.has_expected_planning_failure_signal(
        {
            "approval_pending": True,
            "approval_status": "pending",
            "operation_logs": [{"result": "approval_pending", "message": "blocked safely"}],
        }
    )


def test_expected_planning_failure_signal_accepts_error_operation() -> None:
    assert e2e_hid_runner.has_expected_planning_failure_signal(
        {
            "approval_pending": False,
            "approval_status": "idle",
            "operation_logs": [{"result": "error", "message": "unsupported"}],
        }
    )


def test_stage07_e2e_uses_console_email_delivery(tmp_path) -> None:
    config = {"email": {"enabled": False, "smtp_account_file": "/home/nama/mail-send-vert.txt"}}

    e2e_hid_runner.configure_stage07_email(
        CASES["stage07_scenario01_completion_email_log"],
        config,
        tmp_path,
    )

    assert config["email"]["enabled"] is True
    assert config["email"]["delivery"] == "console"


def test_existing_app_process_check_reports_running_webui(monkeypatch: Any) -> None:
    class Result:
        stdout = " 111 python3 app.py --host 127.0.0.1\n 222 python3 run_e2e_suite.py\n"
        stderr = ""

    monkeypatch.setattr(e2e_hid_runner.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(e2e_hid_runner.os, "getpid", lambda: 333)

    error = e2e_hid_runner.assert_no_existing_app_process()

    assert "app.py is already running" in error
    assert "111 python3 app.py" in error
    assert "run_e2e_suite.py" not in error


def test_stage02_operation_log_validation_requires_real_hid_operation(tmp_path) -> None:
    store = OperationLogStore(tmp_path / "app.db", tmp_path / "screenshots")
    store.record_operation(
        command="WAIT",
        status="sent",
        source="e2e",
        case_name=STAGE02_SCENARIO02_OPERATION_LOG.name,
        action_type="wait",
    )

    error = e2e_hid_runner.validate_stage02_logs(
        STAGE02_SCENARIO02_OPERATION_LOG,
        store,
        tmp_path,
    )

    assert error == "operation_log HID sent entry missing"


def test_stage02_screenshot_log_validation_requires_before_and_after(tmp_path) -> None:
    store = OperationLogStore(tmp_path / "app.db", tmp_path / "screenshots")
    for index in range(2):
        store.record_screenshot(
            path=tmp_path / "screenshots" / f"before{index}.png",
            event="before",
            case_name=STAGE02_SCENARIO03_SCREENSHOT_LOG.name,
            step_name="generate_event_screenshots",
        )

    error = e2e_hid_runner.validate_stage02_logs(
        STAGE02_SCENARIO03_SCREENSHOT_LOG,
        store,
        tmp_path,
    )

    assert error == "screenshot_log before/after entries missing"
