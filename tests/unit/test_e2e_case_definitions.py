from __future__ import annotations

import inspect

from pico_hid_bridge.e2e.cases import ALL_CASES


def test_all_case_names_are_unique() -> None:
    names = [case.name for case in ALL_CASES]
    assert len(names) == len(set(names))
    assert len(names) == 84


def test_all_case_names_have_test_functions() -> None:
    from tests.e2e import test_scenarios

    function_names = {
        name
        for name, value in inspect.getmembers(test_scenarios)
        if name.startswith("test_") and callable(value)
    }
    for case in ALL_CASES:
        assert f"test_{case.name}" in function_names


def test_all_action_tasks_are_ascii() -> None:
    for case in ALL_CASES:
        for step in case.steps:
            if step.action_task is not None:
                step.action_task.encode("ascii")
            step.verify_task.encode("ascii")


def test_expected_failure_cases_have_expected_failure_in_name_or_category() -> None:
    expected_cases = [case for case in ALL_CASES if "expected_failure" in case.name]
    assert expected_cases
    for case in expected_cases:
        assert "expected_failure" in case.name


def test_all_cases_have_stage_description_and_steps() -> None:
    for case in ALL_CASES:
        assert case.stage.startswith("stage")
        assert case.description
        assert case.steps
        for step in case.steps:
            assert step.name
            assert step.verify_task
            assert step.success_message
            assert step.failure_message


def test_stage01_scenario05_loads_picture_file_and_verifies_text() -> None:
    case = next(case for case in ALL_CASES if case.name == "stage01_scenario05_paint_text")

    assert case.implemented is True
    assert case.pending_reason == ""
    assert case.description == (
        "Scenario 5: verify Paint can open an existing image file and the image contains text."
    )
    assert [step.name for step in case.steps] == [
        "open_paint",
        "open_picture_file",
        "verify_picture_text",
    ]

    open_step = case.steps[0]
    assert open_step.action_task is not None
    assert "mspaint" in open_step.action_task.lower()
    assert "C:\\Users\\user\\Pictures" not in open_step.action_task

    load_step = case.steps[1]
    assert load_step.action_task is not None
    assert "CTRL+O" in load_step.action_task
    assert "File menu" not in load_step.action_task
    assert "C:\\Users\\user\\Pictures\\test.png" in load_step.action_task
    assert "mspaint C:\\Users\\user\\Pictures\\test.png" not in load_step.action_task

    verify_step = case.steps[2]
    assert verify_step.action_task is None
    assert "This is test" in verify_step.verify_task


def test_stage01_scenario04_uses_plus_after_jis_firmware_update() -> None:
    case = next(case for case in ALL_CASES if case.name == "stage01_scenario04_calculator_basic")
    calculate_step = next(step for step in case.steps if step.name == "calculate_expression")

    assert calculate_step.action_task is not None
    assert "123+456" in calculate_step.action_task
    assert "123:456" not in calculate_step.action_task


def test_all_stage01_cases_are_implemented() -> None:
    stage01_cases = [case for case in ALL_CASES if case.stage == "stage01_core_io"]

    assert len(stage01_cases) == 7
    assert all(case.implemented for case in stage01_cases)


def test_stage04_covers_all_stage01_operations_via_webui_request() -> None:
    expected_names = {
        "stage04_scenario08_webui_request_open_browser",
        "stage04_scenario09_webui_request_run_dialog",
        "stage04_scenario10_webui_request_text_editor_input",
        "stage04_scenario11_webui_request_calculator_basic",
        "stage04_scenario12_webui_request_paint_text",
        "stage04_scenario13_webui_request_expected_failure_unsupported_drag",
        "stage04_scenario14_webui_request_expected_failure_nonexistent_app",
    }
    stage04_names = {case.name for case in ALL_CASES if case.stage == "stage04_webui_control"}

    assert expected_names <= stage04_names

    stage04_stage01_cases = [case for case in ALL_CASES if case.name in expected_names]
    assert len(stage04_stage01_cases) == 7
    assert all(case.implemented for case in stage04_stage01_cases)
    assert all("WebUI Request" in case.description for case in stage04_stage01_cases)


def test_all_stage02_cases_are_implemented() -> None:
    stage02_cases = [case for case in ALL_CASES if case.stage == "stage02_operation_log"]

    assert len(stage02_cases) == 7
    assert all(case.implemented for case in stage02_cases)
    assert all(case.pending_reason == "" for case in stage02_cases)


def test_all_stage03_cases_are_implemented() -> None:
    stage03_cases = [case for case in ALL_CASES if case.stage == "stage03_runtime_safety"]

    assert len(stage03_cases) == 4
    assert all(case.implemented for case in stage03_cases)
    assert all(case.pending_reason == "" for case in stage03_cases)


def test_all_stage04_cases_are_implemented() -> None:
    stage04_cases = [case for case in ALL_CASES if case.stage == "stage04_webui_control"]

    assert len(stage04_cases) == 14
    assert all(case.implemented for case in stage04_cases)
    assert all(case.pending_reason == "" for case in stage04_cases)


def test_all_stage05_cases_are_implemented() -> None:
    stage05_cases = [case for case in ALL_CASES if case.stage == "stage05_planning"]

    assert len(stage05_cases) == 13
    assert all(case.implemented for case in stage05_cases)
    assert all(case.pending_reason == "" for case in stage05_cases)


def test_all_stage06_cases_are_implemented() -> None:
    stage06_cases = [case for case in ALL_CASES if case.stage == "stage06_approval"]

    assert len(stage06_cases) == 9
    assert all(case.implemented for case in stage06_cases)
    assert all(case.pending_reason == "" for case in stage06_cases)


def test_all_stage07_cases_are_implemented() -> None:
    stage07_cases = [case for case in ALL_CASES if case.stage == "stage07_email_notification"]

    assert len(stage07_cases) == 8
    assert all(case.implemented for case in stage07_cases)
    assert all(case.pending_reason == "" for case in stage07_cases)


def test_all_stage08_cases_are_implemented() -> None:
    stage08_cases = [case for case in ALL_CASES if case.stage == "stage08_long_running"]

    assert len(stage08_cases) == 7
    assert all(case.implemented for case in stage08_cases)
    assert all(case.pending_reason == "" for case in stage08_cases)


def test_all_stage09_cases_are_implemented() -> None:
    stage09_cases = [case for case in ALL_CASES if case.stage == "stage09_token_budget"]

    assert len(stage09_cases) == 7
    assert all(case.implemented for case in stage09_cases)
    assert all(case.pending_reason == "" for case in stage09_cases)


def test_all_stage10_cases_are_implemented() -> None:
    stage10_cases = [case for case in ALL_CASES if case.stage == "stage10_discord"]

    assert len(stage10_cases) == 8
    assert all(case.implemented for case in stage10_cases)
    assert all(case.pending_reason == "" for case in stage10_cases)
