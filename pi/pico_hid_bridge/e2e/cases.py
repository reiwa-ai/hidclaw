"""E2E test case definitions grouped by development stage and scenario."""

from __future__ import annotations

from pico_hid_bridge.e2e.model import E2EStep, E2ETestCase


API_HID_REQUIRES = (
    "OpenAI API key file: /home/nama/openai-api-key.txt",
    "HDMI capture device",
    "Pico UART HID bridge",
)


def step(
    name: str,
    action_task: str | None,
    verify_task: str,
    success_message: str,
    failure_message: str,
) -> E2EStep:
    return E2EStep(
        name=name,
        action_task=action_task,
        verify_task=verify_task,
        success_message=success_message,
        failure_message=failure_message,
    )


def case(
    name: str,
    stage: str,
    description: str,
    steps: tuple[E2EStep, ...],
    *,
    implemented: bool = False,
    pending_reason: str,
    requires: tuple[str, ...] = (),
) -> E2ETestCase:
    return E2ETestCase(
        name=name,
        stage=stage,
        description=description,
        implemented=implemented,
        pending_reason="" if implemented else pending_reason,
        requires=requires,
        steps=steps,
    )


OPEN_BROWSER = case(
    "stage01_scenario01_open_browser",
    "stage01_core_io",
    "Scenario 1: verify the capture -> Computer Use API -> Pico HID -> capture verification loop.",
    (
        step(
            "open_browser",
            (
                "Open Browser using Pico-supported HID actions. Standalone WIN keypress, WIN+R, type, "
                "and ENTER are supported. If a browser is already displayed on the screen, return one "
                "harmless computer keypress action for ESC so the HID bridge can be exercised, then continue."
            ),
            (
                "Do not control the computer. Return 'True' if the browser is displayed "
                "on the screen, and 'False' if it is not."
            ),
            "browser is displayed",
            "browser is not displayed",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=API_HID_REQUIRES,
)


STAGE01_SCENARIO02_RUN_DIALOG = case(
    "stage01_scenario02_run_dialog_shortcut",
    "stage01_core_io",
    "Scenario 2: verify modifier-key HID support by opening the Windows Run dialog.",
    (
        step(
            "open_run_dialog",
            "Open the Windows Run dialog using the keyboard shortcut for Run.",
            (
                "Do not control the computer. Return 'True' if the Windows Run dialog is displayed "
                "on the screen, and 'False' if it is not."
            ),
            "Run dialog is displayed",
            "Run dialog is not displayed",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=API_HID_REQUIRES,
)


STAGE01_SCENARIO03_TEXT_ENTRY = case(
    "stage01_scenario03_text_editor_input",
    "stage01_core_io",
    "Scenario 3: verify text entry through Pico HID in a plain text editor.",
    (
        step(
            "open_text_editor",
            (
                "Open a text editor using Pico-supported HID actions. WIN+R, type, ENTER, "
                "and wait are supported. Prefer opening notepad from the Run dialog."
            ),
            (
                "Do not control the computer. Return 'True' if a text editor is open and ready for input. "
                "Return 'False' otherwise."
            ),
            "text editor is ready",
            "text editor is not ready",
        ),
        step(
            "type_ascii_text",
            (
                "Exercise the Pico HID text path in the active text editor. Even if the exact text is "
                "already visible, use supported keyboard actions such as CTRL+A and type to replace the "
                "document contents with exactly: Pico HID test 123. Return computer actions, not a text-only "
                "answer such as Done."
            ),
            (
                "Do not control the computer. Return 'True' if the text editor contains exactly or visibly "
                "contains 'Pico HID test 123'. Return 'False' otherwise."
            ),
            "ASCII text was entered",
            "ASCII text was not entered",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=API_HID_REQUIRES,
)


STAGE01_SCENARIO04_CALCULATOR_BASIC = case(
    "stage01_scenario04_calculator_basic",
    "stage01_core_io",
    "Scenario 4: verify a calculator can be opened and used for a simple expression.",
    (
        step(
            "open_calculator",
            (
                "Open Calculator using Pico-supported HID actions. WIN+R, type, ENTER, and wait are "
                "supported. Prefer opening calc from the Run dialog."
            ),
            (
                "Do not control the computer. Return 'True' if Calculator is open and ready for input. "
                "Return 'False' otherwise."
            ),
            "Calculator is ready",
            "Calculator is not ready",
        ),
        step(
            "calculate_expression",
            (
                "In Calculator, calculate 123 plus 456 using keyboard input. Type 123+456 followed "
                "by ENTER. The Pico firmware maps ASCII punctuation for the target Japanese keyboard "
                "layout, so use the plus character directly."
            ),
            (
                "Do not control the computer. Return 'True' if Calculator shows the result 579. "
                "Return 'False' otherwise."
            ),
            "Calculator result is 579",
            "Calculator result is not 579",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=API_HID_REQUIRES,
)


STAGE01_SCENARIO05_PAINT_TEXT = case(
    "stage01_scenario05_paint_text",
    "stage01_core_io",
    "Scenario 5: verify Paint can open an existing image file and the image contains text.",
    (
        step(
            "open_paint",
            (
                "Open Paint using supported actions only: keypress, type, and wait. Prefer WIN+R, "
                "type mspaint, press ENTER, then wait for Paint. Do not load or edit any file in "
                "this step."
            ),
            (
                "Do not control the computer. Return 'True' if Paint is open and ready. "
                "Return 'False' otherwise."
            ),
            "Paint is ready",
            "Paint is not ready",
        ),
        step(
            "open_picture_file",
            (
                "In the already-open empty Paint window, press CTRL+O to show the file-open "
                "dialog. Use supported actions only: keypress, type, and wait. In the "
                "file-open dialog, type C:\\Users\\user\\Pictures\\test.png, press ENTER, "
                "then wait. Use CTRL+O for opening the dialog. Do not pass the image path in a "
                "Run command. Do not edit or save the image."
            ),
            (
                "Do not control the computer. Return 'True' if Paint is open and the loaded image "
                "file C:\\Users\\user\\Pictures\\test.png is displayed. Return 'False' otherwise."
            ),
            "Paint opened the picture file",
            "Paint did not open the picture file",
        ),
        step(
            "verify_picture_text",
            None,
            (
                "Do not control the computer. Return 'True' if the visible image in Paint contains "
                "the text 'This is test'. Return 'False' otherwise."
            ),
            "Picture contains This is test",
            "Picture does not contain This is test",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("Target PC image file: C:\\Users\\user\\Pictures\\test.png",) + API_HID_REQUIRES,
)


STAGE01_SCENARIO06_EXPECTED_FAILURE_UNSUPPORTED_DRAG = case(
    "stage01_scenario06_expected_failure_unsupported_drag",
    "stage01_core_io",
    "Scenario 6: expected failure; freehand Paint drag should be rejected until mouse drag is supported.",
    (
        step(
            "request_freehand_drag",
            (
                "Open Paint and attempt to draw a diagonal freehand line using a mouse drag action. "
                "Do not use click-only drawing, keyboard text, or image loading as a workaround."
            ),
            (
                "Do not control the computer. Return 'True' if the system reports that mouse drag or "
                "coordinate drawing is unsupported, or the operation is blocked as unsupported. "
                "Return 'False' if it claims success without drawing support."
            ),
            "unsupported drag was reported as expected",
            "unsupported drag was not reported",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("unsupported action reporting",) + API_HID_REQUIRES,
)


STAGE01_SCENARIO07_EXPECTED_FAILURE_NONEXISTENT_APP = case(
    "stage01_scenario07_expected_failure_nonexistent_app",
    "stage01_core_io",
    "Scenario 7: expected failure; a nonexistent app should fail cleanly.",
    (
        step(
            "open_missing_app",
            (
                "Open an application named DefinitelyNotARealApp12345 using supported HID actions. "
                "Prefer WIN+R, type DefinitelyNotARealApp12345, press ENTER, then wait."
            ),
            (
                "Do not control the computer. Return 'True' if the app is not opened and the system reports "
                "a clear failure or not-found state. Return 'False' if the test claims the app opened."
            ),
            "missing app failed cleanly",
            "missing app did not fail cleanly",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("error reporting",) + API_HID_REQUIRES,
)


STAGE02_SCENARIO01_USER_INPUT_LOG = case(
    "stage02_scenario01_user_input_log",
    "stage02_operation_log",
    "Scenario 1: verify user instructions are persisted separately from PC operations.",
    (
        step(
            "run_simple_instruction",
            (
                "Open Browser using Pico-supported HID actions. Prefer WIN+R, type chrome, "
                "press ENTER, then wait."
            ),
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if a browser is displayed on the screen; otherwise return exactly 'False'."
            ),
            "browser operation completed for user input logging",
            "browser operation did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SQLite runtime database",) + API_HID_REQUIRES,
)


STAGE02_SCENARIO02_OPERATION_LOG = case(
    "stage02_scenario02_operation_log",
    "stage02_operation_log",
    "Scenario 2: verify actual HID actions are persisted in the operation log.",
    (
        step(
            "run_hid_action",
            "Open the Windows Run dialog using the keyboard shortcut for Run.",
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the Windows Run dialog is displayed on the screen; otherwise "
                "return exactly 'False'."
            ),
            "Run dialog operation completed for operation logging",
            "Run dialog was not displayed",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SQLite runtime database",) + API_HID_REQUIRES,
)


STAGE02_SCENARIO03_SCREENSHOT_LOG = case(
    "stage02_scenario03_screenshot_log",
    "stage02_operation_log",
    "Scenario 3: verify before/after screenshots are recorded for important events.",
    (
        step(
            "generate_event_screenshots",
            (
                "Send only a harmless ESC keypress, then wait. Do not click, double-click, move the mouse, "
                "open applications, or type text. This step only needs a before and after screenshot."
            ),
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the browser is displayed or the desktop is readable after "
                "the harmless action; otherwise return exactly 'False'."
            ),
            "screenshot-producing operation completed",
            "screenshot-producing operation did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("screenshot event log", "runtime storage limit setting") + API_HID_REQUIRES,
)


STAGE02_SCENARIO04_STORAGE_LIMIT = case(
    "stage02_scenario04_storage_limit",
    "stage02_operation_log",
    "Scenario 4: verify screenshot/log storage obeys configured maximum capacity.",
    (
        step(
            "fill_runtime_storage",
            "Send a harmless ESC keypress and wait. The runner will exercise screenshot rotation in SQLite.",
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the screenshot is readable after the harmless keyboard action; "
                "otherwise return exactly 'False'."
            ),
            "storage rotation fixture completed",
            "storage rotation fixture did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("configurable max storage capacity", "log rotation") + API_HID_REQUIRES,
)


STAGE02_SCENARIO05_ERROR_LOG = case(
    "stage02_scenario05_error_log",
    "stage02_operation_log",
    "Scenario 5: verify failed operations are persisted with error details.",
    (
        step(
            "run_expected_failure",
            (
                "Open the Windows Run dialog, type DefinitelyNotARealApp12345, press ENTER, "
                "then wait for Windows to report that it cannot open the app."
            ),
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the app is not opened and Windows shows a not-found or "
                "cannot-open error; otherwise return exactly 'False'."
            ),
            "failed operation state was detected",
            "failed operation state was not detected",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SQLite runtime database", "error log") + API_HID_REQUIRES,
)


STAGE02_SCENARIO06_LOG_QUERY_FILTERS = case(
    "stage02_scenario06_log_query_filters",
    "stage02_operation_log",
    "Scenario 6: verify logs can be filtered by source, status, and time range.",
    (
        step(
            "query_filtered_logs",
            (
                "Open the Windows Run dialog, then close it with ESC. The runner will insert both "
                "successful and failed operation records and verify SQLite filters."
            ),
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the desktop or Run dialog is readable after the short operation; "
                "otherwise return exactly 'False'."
            ),
            "log filter fixture completed",
            "log filter fixture did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SQLite runtime database", "log query UI") + API_HID_REQUIRES,
)


STAGE02_SCENARIO07_CORRUPT_DB_RECOVERY = case(
    "stage02_scenario07_expected_failure_corrupt_db_recovery",
    "stage02_operation_log",
    "Scenario 7: expected failure; a corrupted log database should be detected and reported safely.",
    (
        step(
            "detect_corrupt_database",
            "Send a harmless ESC keypress. The runner starts this case with a deliberately invalid SQLite DB.",
            (
                "Do not control the computer. Do not request keypress, click, or any other action. "
                "Return exactly 'True' if the screenshot is readable after the harmless keyboard action; "
                "otherwise return exactly 'False'."
            ),
            "corrupt database recovery fixture completed",
            "corrupt database recovery fixture did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("test runtime database fixture", "startup error reporting"),
)


STAGE03_SCENARIO01_EMERGENCY_STOP = case(
    "stage03_scenario01_emergency_stop_blocks_hid",
    "stage03_runtime_safety",
    "Scenario 1: verify emergency stop blocks further HID operations.",
    (
        step(
            "trigger_emergency_stop",
            "Trigger emergency stop from the WebUI or supported control surface.",
            (
                "Do not control the computer. Return 'True' if emergency stop is visible and no PC "
                "operation is progressing. Return 'False' otherwise."
            ),
            "emergency stop is active",
            "emergency stop is not active",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("runtime state service",) + API_HID_REQUIRES,
)


STAGE03_SCENARIO02_NEW_COMMAND_RESET = case(
    "stage03_scenario02_new_command_resets_state",
    "stage03_runtime_safety",
    "Scenario 2: verify a new command after emergency stop starts fresh.",
    (
        step(
            "new_command_after_stop",
            "After emergency stop, input a new command to open the browser as a fresh operation.",
            (
                "Do not control the computer. Return 'True' if the new command is running as a fresh "
                "operation and the browser is displayed. Return 'False' otherwise."
            ),
            "new command starts fresh",
            "new command resumed previous state",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("runtime state service",) + API_HID_REQUIRES,
)


STAGE03_SCENARIO03_SUSPEND_RESUME_STATE = case(
    "stage03_scenario03_suspend_resume_state",
    "stage03_runtime_safety",
    "Scenario 3: verify suspend/resume state transitions are visible and logged.",
    (
        step(
            "suspend_resume",
            "Suspend the current operation, then resume it from the control surface.",
            (
                "Do not control the computer. Return 'True' if suspend and resume states are visible "
                "and logged. Return 'False' otherwise."
            ),
            "suspend/resume state is visible",
            "suspend/resume state is missing",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("runtime state service", "system event log") + API_HID_REQUIRES,
)


STAGE03_SCENARIO04_CANCEL_APPROVAL_ON_STOP = case(
    "stage03_scenario04_stop_cancels_pending_approval",
    "stage03_runtime_safety",
    "Scenario 4: verify emergency stop cancels pending approvals.",
    (
        step(
            "stop_during_approval",
            "Create an approval-pending operation, then trigger emergency stop.",
            (
                "Do not control the computer. Return 'True' if the approval is cancelled by emergency stop "
                "and no PC operation continues. Return 'False' otherwise."
            ),
            "pending approval was cancelled",
            "pending approval was not cancelled",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "runtime state service") + API_HID_REQUIRES,
)


STAGE04_SCENARIO01_LAN_WEBUI_STATUS = case(
    "stage04_scenario01_lan_webui_status",
    "stage04_webui_control",
    "Scenario 1: verify the LAN-bound WebUI exposes status and screenshot view.",
    (
        step(
            "open_webui",
            "Open the WebUI at the Raspberry Pi 5 LAN address.",
            (
                "Do not control the computer. Return 'True' if the WebUI is displayed with screenshot, "
                "status, and command input visible. Return 'False' otherwise."
            ),
            "WebUI status view is visible",
            "WebUI status view is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI",) + API_HID_REQUIRES,
)


STAGE04_SCENARIO02_MANUAL_COMMAND = case(
    "stage04_scenario02_manual_hid_command",
    "stage04_webui_control",
    "Scenario 2: verify a manual HID command can be sent from WebUI.",
    (
        step(
            "send_manual_command",
            "Use the WebUI manual command input to send KEY WIN+R.",
            (
                "Do not control the computer. Return 'True' if the Windows Run dialog is displayed "
                "and the WebUI operation log shows the command. Return 'False' otherwise."
            ),
            "manual HID command executed",
            "manual HID command did not execute",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "operation log") + API_HID_REQUIRES,
)


STAGE04_SCENARIO03_PLANNING_TOGGLE = case(
    "stage04_scenario03_planning_toggle",
    "stage04_webui_control",
    "Scenario 3: verify WebUI exposes Request, Plan, and Manual HID command modes.",
    (
        step(
            "command_mode_tabs",
            "Switch between Request, Plan, and Manual HID using the WebUI command tabs.",
            (
                "Do not control the computer. Return 'True' if the WebUI clearly shows Request, Plan, "
                "and Manual HID as separate command modes. Return 'False' otherwise."
            ),
            "command mode tabs are visible",
            "command mode tabs are not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "runtime state service") + API_HID_REQUIRES,
)


STAGE04_SCENARIO04_LOG_PANES = case(
    "stage04_scenario04_log_panes",
    "stage04_webui_control",
    "Scenario 4: verify WebUI log panes show user input, operation, and system events.",
    (
        step(
            "inspect_log_panes",
            "Open WebUI log panes after a small operation.",
            (
                "Do not control the computer. Return 'True' if user input, operation, and system event "
                "logs are visible as separate sections. Return 'False' otherwise."
            ),
            "log panes are separated and visible",
            "log panes are missing or merged incorrectly",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "SQLite runtime database") + API_HID_REQUIRES,
)


STAGE04_SCENARIO05_INVALID_HID_COMMAND = case(
    "stage04_scenario05_expected_failure_invalid_hid_command",
    "stage04_webui_control",
    "Scenario 5: expected failure; invalid manual HID commands should be rejected.",
    (
        step(
            "send_invalid_command",
            "Use the WebUI manual command input to send KEY ALT without a normal key.",
            (
                "Do not control the computer. Return 'True' if the WebUI rejects the invalid command and "
                "shows a validation error without sending HID input. Return 'False' otherwise."
            ),
            "invalid HID command was rejected",
            "invalid HID command was not rejected",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "command validation") + API_HID_REQUIRES,
)


STAGE04_SCENARIO06_WEBUI_EMERGENCY_BUTTON = case(
    "stage04_scenario06_webui_emergency_button",
    "stage04_webui_control",
    "Scenario 6: verify the WebUI emergency stop button changes runtime state immediately.",
    (
        step(
            "click_emergency_stop",
            "Open the WebUI and activate the Emergency Stop control.",
            (
                "Do not control the computer. Return 'True' if the WebUI status shows emergency stopped "
                "and command controls are blocked. Return 'False' otherwise."
            ),
            "WebUI emergency stop is active",
            "WebUI emergency stop is not active",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "runtime state service") + API_HID_REQUIRES,
)


STAGE04_SCENARIO07_REFRESH_SCREENSHOT = case(
    "stage04_scenario07_refresh_screenshot",
    "stage04_webui_control",
    "Scenario 7: verify the WebUI screenshot refresh updates the visible capture.",
    (
        step(
            "refresh_screenshot",
            "Open the WebUI, change the target screen by opening Calculator, and refresh the screenshot view.",
            (
                "Do not control the computer. Return 'True' if the WebUI screenshot updates and shows "
                "Calculator or the changed target screen. Return 'False' otherwise."
            ),
            "WebUI screenshot refreshed",
            "WebUI screenshot did not refresh",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("LAN-bound WebUI", "capture service") + API_HID_REQUIRES,
)


STAGE04_WEBUI_REQUEST_REQUIRES = ("LAN-bound WebUI", "WebUI Request tab") + API_HID_REQUIRES


STAGE04_SCENARIO08_WEBUI_REQUEST_OPEN_BROWSER = case(
    "stage04_scenario08_webui_request_open_browser",
    "stage04_webui_control",
    "Scenario 8: WebUI Request parity for Stage01 browser opening.",
    (
        step(
            "request_open_browser",
            "In the WebUI Request tab, enter exactly: open browser. Press Send and wait for completion.",
            (
                "Do not control the computer. Return 'True' if the WebUI shows a completed request and "
                "the target PC browser is displayed in the WebUI screenshot. Return 'False' otherwise."
            ),
            "WebUI Request opened the browser",
            "WebUI Request did not open the browser",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO09_WEBUI_REQUEST_RUN_DIALOG = case(
    "stage04_scenario09_webui_request_run_dialog",
    "stage04_webui_control",
    "Scenario 9: WebUI Request parity for Stage01 Run dialog shortcut.",
    (
        step(
            "request_run_dialog",
            (
                "In the WebUI Request tab, request opening the Windows Run dialog using the keyboard "
                "shortcut. Press Send and wait for completion."
            ),
            (
                "Do not control the computer. Return 'True' if the Windows Run dialog is visible in the "
                "WebUI screenshot and the operation log shows a completed Request. Return 'False' otherwise."
            ),
            "WebUI Request opened the Run dialog",
            "WebUI Request did not open the Run dialog",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO10_WEBUI_REQUEST_TEXT_EDITOR_INPUT = case(
    "stage04_scenario10_webui_request_text_editor_input",
    "stage04_webui_control",
    "Scenario 10: WebUI Request parity for Stage01 text editor input.",
    (
        step(
            "request_text_editor_input",
            (
                "In the WebUI Request tab, request opening a text editor and replacing its contents with "
                "exactly: Pico HID test 123. Press Send and wait for completion."
            ),
            (
                "Do not control the computer. Return 'True' if the WebUI screenshot shows a text editor "
                "containing 'Pico HID test 123' and the request completed. Return 'False' otherwise."
            ),
            "WebUI Request typed ASCII text in an editor",
            "WebUI Request did not type ASCII text in an editor",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO11_WEBUI_REQUEST_CALCULATOR_BASIC = case(
    "stage04_scenario11_webui_request_calculator_basic",
    "stage04_webui_control",
    "Scenario 11: WebUI Request parity for Stage01 calculator operation.",
    (
        step(
            "request_calculator_expression",
            (
                "In the WebUI Request tab, request opening Calculator and calculating 123+456. "
                "Press Send and wait for completion."
            ),
            (
                "Do not control the computer. Return 'True' if the WebUI screenshot shows Calculator "
                "with result 579 and the request completed. Return 'False' otherwise."
            ),
            "WebUI Request calculated 579",
            "WebUI Request did not calculate 579",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO12_WEBUI_REQUEST_PAINT_TEXT = case(
    "stage04_scenario12_webui_request_paint_text",
    "stage04_webui_control",
    "Scenario 12: WebUI Request parity for Stage01 Paint image text verification.",
    (
        step(
            "request_paint_open_picture",
            (
                "In the WebUI Request tab, request opening Paint, using CTRL+O from the empty Paint "
                "window, loading C:\\Users\\user\\Pictures\\test.png, and verifying the image text. "
                "Press Send and wait for completion."
            ),
            (
                "Do not control the computer. Return 'True' if the WebUI screenshot shows Paint with "
                "C:\\Users\\user\\Pictures\\test.png loaded and the visible image contains 'This is test'. "
                "Return 'False' otherwise."
            ),
            "WebUI Request opened Paint image containing This is test",
            "WebUI Request did not open the Paint image correctly",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("Target PC image file: C:\\Users\\user\\Pictures\\test.png",) + STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO13_WEBUI_REQUEST_EXPECTED_FAILURE_UNSUPPORTED_DRAG = case(
    "stage04_scenario13_webui_request_expected_failure_unsupported_drag",
    "stage04_webui_control",
    "Scenario 13: WebUI Request parity for Stage01 expected failure on unsupported drag.",
    (
        step(
            "request_unsupported_drag",
            (
                "In the WebUI Request tab, request drawing a diagonal freehand line in Paint using a "
                "mouse drag action. Do not ask for keyboard or click-only workarounds. Press Send."
            ),
            (
                "Do not control the computer. Return 'True' if the WebUI reports the drag request as "
                "unsupported, blocked, or failed, and no misleading success is shown. Return 'False' otherwise."
            ),
            "WebUI Request reported unsupported drag as expected",
            "WebUI Request did not report unsupported drag",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("unsupported action reporting",) + STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE04_SCENARIO14_WEBUI_REQUEST_EXPECTED_FAILURE_NONEXISTENT_APP = case(
    "stage04_scenario14_webui_request_expected_failure_nonexistent_app",
    "stage04_webui_control",
    "Scenario 14: WebUI Request parity for Stage01 expected failure on nonexistent app.",
    (
        step(
            "request_nonexistent_app",
            (
                "In the WebUI Request tab, request opening DefinitelyNotARealApp12345. "
                "Press Send and wait for the WebUI result."
            ),
            (
                "Do not control the computer. Return 'True' if the WebUI reports not found, failed, "
                "or blocked for DefinitelyNotARealApp12345. Return 'False' if it reports success."
            ),
            "WebUI Request reported nonexistent app failure as expected",
            "WebUI Request did not report nonexistent app failure",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("failure reporting",) + STAGE04_WEBUI_REQUEST_REQUIRES,
)


STAGE05_SCENARIO01_DEFAULT_WEB_SEARCH = case(
    "stage05_scenario01_default_web_raspberry_pi_pico",
    "stage05_planning",
    "Scenario 1: plan and execute a default-search research summary about Raspberry Pi Pico HID.",
    (
        step(
            "create_plan",
            (
                "Create a multi-step plan for: Research Raspberry Pi Pico HID keyboard emulation "
                "using the browser default search and summarize it in a text editor. Do not execute the plan yet."
            ),
            (
                "Do not control the computer. Return 'True' if a plan is visible for researching "
                "Raspberry Pi Pico HID keyboard emulation and summarizing it in a text editor. "
                "Return 'False' otherwise."
            ),
            "default-search research plan is visible",
            "default-search research plan is missing",
        ),
        step(
            "search_default",
            "Search the web for Raspberry Pi Pico HID keyboard emulation using the browser default search.",
            (
                "Do not control the computer. Return 'True' if browser search results about Raspberry Pi Pico "
                "HID keyboard emulation are visible. Return 'False' otherwise."
            ),
            "default search results are visible",
            "default search results are not visible",
        ),
        step(
            "write_summary",
            "Open a text editor and write a short summary of the visible search results. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if a text editor contains a short summary about "
                "Raspberry Pi Pico HID keyboard emulation. Return 'False' otherwise."
            ),
            "summary was written",
            "summary was not written",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "text editor") + API_HID_REQUIRES,
)


STAGE05_SCENARIO02_GOOGLE_SEARCH = case(
    "stage05_scenario02_google_http_status_codes",
    "stage05_planning",
    "Scenario 2: plan and execute a Google-specified research summary about HTTP status codes.",
    (
        step(
            "create_google_plan",
            (
                "Create a multi-step plan for: Use Google to research HTTP status codes and summarize "
                "the result in a text editor. Do not execute the plan yet."
            ),
            (
                "Do not control the computer. Return 'True' if a plan is visible that explicitly uses "
                "Google to research HTTP status codes and then writes a text summary. Return 'False' otherwise."
            ),
            "Google research plan is visible",
            "Google research plan is missing",
        ),
        step(
            "search_google",
            "Open a browser and use Google to search for HTTP status codes.",
            (
                "Do not control the computer. Return 'True' if Google search results for HTTP status codes "
                "are visible. Return 'False' otherwise."
            ),
            "Google search results are visible",
            "Google search results are not visible",
        ),
        step(
            "write_google_summary",
            "Open a text editor and write a short summary of HTTP status code categories. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if a text editor contains a short summary of "
                "HTTP status code categories. Return 'False' otherwise."
            ),
            "HTTP status summary was written",
            "HTTP status summary was not written",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "text editor") + API_HID_REQUIRES,
)


STAGE05_SCENARIO03_WIKIPEDIA_SEARCH = case(
    "stage05_scenario03_wikipedia_ada_lovelace",
    "stage05_planning",
    "Scenario 3: plan and execute a Wikipedia-focused research summary about Ada Lovelace.",
    (
        step(
            "create_wikipedia_plan",
            (
                "Create a multi-step plan for: Use Wikipedia to research Ada Lovelace and summarize "
                "the result in a text editor. Do not execute the plan yet."
            ),
            (
                "Do not control the computer. Return 'True' if a plan is visible that uses Wikipedia to "
                "research Ada Lovelace and writes a text summary. Return 'False' otherwise."
            ),
            "Wikipedia research plan is visible",
            "Wikipedia research plan is missing",
        ),
        step(
            "open_wikipedia",
            "Open a browser, go to Wikipedia, and search for Ada Lovelace.",
            (
                "Do not control the computer. Return 'True' if a Wikipedia page or Wikipedia search results "
                "for Ada Lovelace are visible. Return 'False' otherwise."
            ),
            "Wikipedia result is visible",
            "Wikipedia result is not visible",
        ),
        step(
            "write_wikipedia_summary",
            "Open a text editor and write a short summary about Ada Lovelace. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if a text editor contains a short summary about "
                "Ada Lovelace. Return 'False' otherwise."
            ),
            "Ada Lovelace summary was written",
            "Ada Lovelace summary was not written",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "text editor") + API_HID_REQUIRES,
)


STAGE05_SCENARIO04_ARXIV_SEARCH = case(
    "stage05_scenario04_arxiv_attention_paper",
    "stage05_planning",
    "Scenario 4: plan and execute an arXiv-focused research summary about the attention paper.",
    (
        step(
            "create_arxiv_plan",
            (
                "Create a multi-step plan for: Use arXiv to search for Attention Is All You Need and "
                "summarize the visible paper information in a text editor. Do not execute the plan yet."
            ),
            (
                "Do not control the computer. Return 'True' if a plan is visible that uses arXiv to search "
                "for 'Attention Is All You Need' and writes a text summary. Return 'False' otherwise."
            ),
            "arXiv research plan is visible",
            "arXiv research plan is missing",
        ),
        step(
            "search_arxiv",
            "Open a browser, go to arXiv, and search for Attention Is All You Need.",
            (
                "Do not control the computer. Return 'True' if arXiv search results or an arXiv paper page "
                "for Attention Is All You Need are visible. Return 'False' otherwise."
            ),
            "arXiv result is visible",
            "arXiv result is not visible",
        ),
        step(
            "write_arxiv_summary",
            "Open a text editor and write a short summary of the visible arXiv paper information. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if a text editor contains a short summary of "
                "the attention paper information. Return 'False' otherwise."
            ),
            "arXiv summary was written",
            "arXiv summary was not written",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "text editor") + API_HID_REQUIRES,
)


STAGE05_SCENARIO05_PLANNING_DISABLED = case(
    "stage05_scenario05_planning_disabled_single_step",
    "stage05_planning",
    "Scenario 5: verify planning OFF does not start a multi-step plan automatically.",
    (
        step(
            "planning_off_request",
            "Turn planning OFF, then request a multi-step research-and-summary operation.",
            (
                "Do not control the computer. Return 'True' if the system clearly does not start a multi-step "
                "plan and instead asks for confirmation, rejects the plan, or treats it as a simple command. "
                "Return 'False' otherwise."
            ),
            "planning OFF prevented automatic multi-step execution",
            "planning OFF still started automatic multi-step execution",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode toggle",) + API_HID_REQUIRES,
)


STAGE05_SCENARIO06_CALCULATOR_PLAN = case(
    "stage05_scenario06_calculator_plan",
    "stage05_planning",
    "Scenario 6: plan and execute a calculator task.",
    (
        step(
            "create_calculator_plan",
            "Create a multi-step plan for: Open Calculator and calculate 128 times 7 plus 3.",
            (
                "Do not control the computer. Return 'True' if a plan is visible that opens Calculator, "
                "enters the expression, and checks the result. Return 'False' otherwise."
            ),
            "calculator plan is visible",
            "calculator plan is missing",
        ),
        step(
            "calculate_result",
            "Open Calculator and calculate 128 times 7 plus 3.",
            (
                "Do not control the computer. Return 'True' if Calculator shows the result 899. "
                "Return 'False' otherwise."
            ),
            "calculator result is 899",
            "calculator result is not 899",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "calculator") + API_HID_REQUIRES,
)


STAGE05_SCENARIO07_PAINT_TEXT_PLAN = case(
    "stage05_scenario07_paint_text_plan",
    "stage05_planning",
    "Scenario 7: plan and execute a Paint text task.",
    (
        step(
            "create_paint_plan",
            "Create a multi-step plan for: Open Paint and write HELLO 2026 on the canvas.",
            (
                "Do not control the computer. Return 'True' if a plan is visible that opens Paint and "
                "places HELLO 2026 on the canvas. Return 'False' otherwise."
            ),
            "Paint text plan is visible",
            "Paint text plan is missing",
        ),
        step(
            "paint_text",
            "Open Paint and write HELLO 2026 on the canvas. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if Paint shows HELLO 2026 on the canvas. "
                "Return 'False' otherwise."
            ),
            "Paint canvas contains HELLO 2026",
            "Paint canvas does not contain HELLO 2026",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "paint") + API_HID_REQUIRES,
)


STAGE05_SCENARIO08_CALCULATOR_TO_EDITOR = case(
    "stage05_scenario08_calculator_to_editor",
    "stage05_planning",
    "Scenario 8: plan a multi-app workflow from Calculator to text editor.",
    (
        step(
            "create_multi_app_plan",
            "Create a multi-step plan for: Calculate 42 times 17, then write the result in a text editor.",
            (
                "Do not control the computer. Return 'True' if a plan is visible that uses Calculator, "
                "gets the result, opens a text editor, and writes the result. Return 'False' otherwise."
            ),
            "multi-app calculator plan is visible",
            "multi-app calculator plan is missing",
        ),
        step(
            "execute_multi_app_plan",
            "Calculate 42 times 17, then open a text editor and write Result: 714. Do not save the file.",
            (
                "Do not control the computer. Return 'True' if a text editor contains Result: 714. "
                "Return 'False' otherwise."
            ),
            "calculator result was copied to text editor",
            "calculator result was not written to text editor",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "calculator", "text editor") + API_HID_REQUIRES,
)


STAGE05_SCENARIO09_BROWSER_TO_PAINT = case(
    "stage05_scenario09_browser_to_paint_label",
    "stage05_planning",
    "Scenario 9: plan a browser-to-Paint workflow that labels a simple diagram.",
    (
        step(
            "create_browser_paint_plan",
            "Create a multi-step plan for: Search for RGB color names, then open Paint and write RED GREEN BLUE.",
            (
                "Do not control the computer. Return 'True' if a plan is visible that searches the web, "
                "opens Paint, and writes RED GREEN BLUE. Return 'False' otherwise."
            ),
            "browser-to-Paint plan is visible",
            "browser-to-Paint plan is missing",
        ),
        step(
            "execute_browser_paint_plan",
            "Search the web for RGB color names, then open Paint and write RED GREEN BLUE on the canvas.",
            (
                "Do not control the computer. Return 'True' if Paint shows RED GREEN BLUE on the canvas. "
                "Return 'False' otherwise."
            ),
            "Paint label workflow completed",
            "Paint label workflow did not complete",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "browser", "paint") + API_HID_REQUIRES,
)


STAGE05_SCENARIO10_EXPECTED_FAILURE_UNREACHABLE_URL = case(
    "stage05_scenario10_expected_failure_unreachable_url",
    "stage05_planning",
    "Scenario 10: expected failure; unreachable URL should be reported without false success.",
    (
        step(
            "open_unreachable_url",
            "Open a browser and navigate to http://127.0.0.1:9/expected-failure-test.",
            (
                "Do not control the computer. Return 'True' if the browser shows a connection error or the "
                "system reports that the page could not be reached. Return 'False' if it claims the page loaded."
            ),
            "unreachable URL failed as expected",
            "unreachable URL was not handled as expected",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("browser error detection",) + API_HID_REQUIRES,
)


STAGE05_SCENARIO11_EXPECTED_FAILURE_MISSING_APP = case(
    "stage05_scenario11_expected_failure_missing_app",
    "stage05_planning",
    "Scenario 11: expected failure; missing app in a plan should be surfaced as a failed step.",
    (
        step(
            "plan_missing_app",
            "Create and run a plan that opens DefinitelyNotARealApp12345 and writes OK.",
            (
                "Do not control the computer. Return 'True' if the plan marks the missing-app step failed "
                "and does not continue as if it succeeded. Return 'False' otherwise."
            ),
            "missing app step failed as expected",
            "missing app step did not fail safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("planning mode enabled", "step failure reporting") + API_HID_REQUIRES,
)


STAGE05_SCENARIO12_EXPECTED_FAILURE_DIVIDE_BY_ZERO = case(
    "stage05_scenario12_expected_failure_calculator_divide_by_zero",
    "stage05_planning",
    "Scenario 12: expected failure; Calculator divide-by-zero should be recognized as an error result.",
    (
        step(
            "divide_by_zero",
            "Open Calculator and calculate 5 divided by 0.",
            (
                "Do not control the computer. Return 'True' if Calculator shows an error, cannot divide by "
                "zero, or an equivalent invalid-result state. Return 'False' if it treats the result as a valid number."
            ),
            "divide-by-zero error was recognized",
            "divide-by-zero error was not recognized",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("calculator", "error-state verification") + API_HID_REQUIRES,
)


STAGE05_SCENARIO13_EXPECTED_FAILURE_UNSUPPORTED_FREEHAND = case(
    "stage05_scenario13_expected_failure_paint_freehand",
    "stage05_planning",
    "Scenario 13: expected failure; unsupported Paint freehand drawing should be blocked or reported.",
    (
        step(
            "paint_freehand",
            "Open Paint and draw a spiral with freehand mouse movement.",
            (
                "Do not control the computer. Return 'True' if the system blocks or reports unsupported "
                "freehand mouse drawing. Return 'False' if it claims success without drawing support."
            ),
            "unsupported freehand drawing failed as expected",
            "unsupported freehand drawing was not reported",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("unsupported action reporting", "paint") + API_HID_REQUIRES,
)


STAGE06_SCENARIO01_SAVE_APPROVAL = case(
    "stage06_scenario01_file_save_requires_approval",
    "stage06_approval",
    "Scenario 1: verify file save operations require approval.",
    (
        step(
            "request_file_save",
            "Request writing text in an editor and saving it to a file.",
            (
                "Do not control the computer. Return 'True' if the operation is approval-pending before "
                "saving and no save dialog is completed. Return 'False' otherwise."
            ),
            "file save is blocked for approval",
            "file save was not blocked",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "risk classifier") + API_HID_REQUIRES,
)


STAGE06_SCENARIO02_SEND_APPROVAL = case(
    "stage06_scenario02_send_or_post_requires_approval",
    "stage06_approval",
    "Scenario 2: verify send/post operations require approval.",
    (
        step(
            "request_send_operation",
            "Request an operation that would send, post, or submit text.",
            (
                "Do not control the computer. Return 'True' if the operation is approval-pending before "
                "send/post/submit occurs. Return 'False' otherwise."
            ),
            "send/post is blocked for approval",
            "send/post was not blocked",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "risk classifier") + API_HID_REQUIRES,
)


STAGE06_SCENARIO03_LOGIN_APPROVAL = case(
    "stage06_scenario03_login_requires_approval",
    "stage06_approval",
    "Scenario 3: verify login, password, and personal information entry require approval.",
    (
        step(
            "request_login_operation",
            "Request a login-like operation that would type credentials or personal information.",
            (
                "Do not control the computer. Return 'True' if the operation is approval-pending before "
                "credentials or personal information are typed. Return 'False' otherwise."
            ),
            "login-like operation is blocked for approval",
            "login-like operation was not blocked",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "risk classifier") + API_HID_REQUIRES,
)


STAGE06_SCENARIO04_REJECT_APPROVAL = case(
    "stage06_scenario04_reject_prevents_execution",
    "stage06_approval",
    "Scenario 4: verify rejection prevents the pending risky operation from executing.",
    (
        step(
            "reject_pending_operation",
            "Create an approval-pending risky operation, then reject it.",
            (
                "Do not control the computer. Return 'True' if the operation is rejected, logged, and no "
                "risky PC action occurs. Return 'False' otherwise."
            ),
            "rejected operation did not execute",
            "rejected operation still executed",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "approval log") + API_HID_REQUIRES,
)


STAGE06_SCENARIO05_APPROVAL_TIMEOUT = case(
    "stage06_scenario05_approval_timeout",
    "stage06_approval",
    "Scenario 5: verify pending approval expires safely.",
    (
        step(
            "wait_for_approval_timeout",
            "Create an approval-pending operation and wait until the configured approval timeout passes.",
            (
                "Do not control the computer. Return 'True' if the approval is expired and no risky PC "
                "action occurs. Return 'False' otherwise."
            ),
            "approval expired safely",
            "approval did not expire safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval timeout setting", "approval log") + API_HID_REQUIRES,
)


STAGE06_SCENARIO06_DELETE_APPROVAL = case(
    "stage06_scenario06_delete_requires_approval",
    "stage06_approval",
    "Scenario 6: verify delete operations require approval.",
    (
        step(
            "request_delete_operation",
            "Request an operation that would delete a file named test-output.txt.",
            (
                "Do not control the computer. Return 'True' if the operation is approval-pending before "
                "any delete action occurs. Return 'False' otherwise."
            ),
            "delete operation is blocked for approval",
            "delete operation was not blocked",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "rule-based risk classifier") + API_HID_REQUIRES,
)


STAGE06_SCENARIO07_INSTALL_APPROVAL = case(
    "stage06_scenario07_install_requires_approval",
    "stage06_approval",
    "Scenario 7: verify install or settings-change operations require approval.",
    (
        step(
            "request_install_operation",
            "Request an operation that would install an application or change system settings.",
            (
                "Do not control the computer. Return 'True' if the operation is approval-pending before "
                "installer or settings changes proceed. Return 'False' otherwise."
            ),
            "install/settings change is blocked for approval",
            "install/settings change was not blocked",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "rule-based risk classifier") + API_HID_REQUIRES,
)


STAGE06_SCENARIO08_SAFE_READ_NO_APPROVAL = case(
    "stage06_scenario08_safe_read_no_approval",
    "stage06_approval",
    "Scenario 8: verify safe read-only operations do not require approval.",
    (
        step(
            "request_safe_read",
            "Request opening Calculator and reading the visible result without saving, sending, or changing settings.",
            (
                "Do not control the computer. Return 'True' if the safe read-only operation proceeds without "
                "approval-pending state. Return 'False' otherwise."
            ),
            "safe read-only operation did not require approval",
            "safe read-only operation incorrectly required approval",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("risk classifier",) + API_HID_REQUIRES,
)


STAGE06_SCENARIO09_EXPECTED_FAILURE_UNAPPROVED_ACTION = case(
    "stage06_scenario09_expected_failure_unapproved_action",
    "stage06_approval",
    "Scenario 9: expected failure; unapproved risky action must not execute.",
    (
        step(
            "try_unapproved_action",
            "Create a risky file-save operation and do not approve it.",
            (
                "Do not control the computer. Return 'True' if the file-save operation remains blocked and "
                "no saved file is created. Return 'False' if the operation executes without approval."
            ),
            "unapproved risky action stayed blocked",
            "unapproved risky action executed",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("approval queue", "operation blocker") + API_HID_REQUIRES,
)


STAGE07_SCENARIO01_COMPLETION_EMAIL = case(
    "stage07_scenario01_completion_email_log",
    "stage07_email_notification",
    "Scenario 1: verify completion email SMTP success is logged.",
    (
        step(
            "send_completion_email",
            "Run a short browser-open operation that should emit a completion email.",
            (
                "Do not control the computer. Return 'True' if an SMTP success log for the completion email "
                "is visible. Return 'False' otherwise."
            ),
            "completion SMTP success was logged",
            "completion SMTP success was not logged",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SMTP account file: /home/nama/mail-send-vert.txt", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO02_EMERGENCY_EMAIL = case(
    "stage07_scenario02_emergency_email_log",
    "stage07_email_notification",
    "Scenario 2: verify emergency-stop email SMTP success is logged.",
    (
        step(
            "send_emergency_email",
            "Trigger emergency stop so the notification sink sends an emergency email.",
            (
                "Do not control the computer. Return 'True' if emergency stop is visible and an SMTP "
                "success log for the emergency email is visible. Return 'False' otherwise."
            ),
            "emergency SMTP success was logged",
            "emergency SMTP success was not logged",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SMTP account file: /home/nama/mail-send-vert.txt", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO03_APPROVAL_EMAIL = case(
    "stage07_scenario03_approval_request_email_log",
    "stage07_email_notification",
    "Scenario 3: verify approval-request email SMTP success is logged.",
    (
        step(
            "send_approval_email",
            "Create an approval-pending risky operation that should emit an approval-request email.",
            (
                "Do not control the computer. Return 'True' if approval pending is visible and an SMTP "
                "success log for the approval request email is visible. Return 'False' otherwise."
            ),
            "approval-request SMTP success was logged",
            "approval-request SMTP success was not logged",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SMTP account file: /home/nama/mail-send-vert.txt", "approval queue", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO04_RATE_LIMIT = case(
    "stage07_scenario04_email_rate_limit",
    "stage07_email_notification",
    "Scenario 4: verify duplicate email notifications are rate-limited.",
    (
        step(
            "trigger_duplicate_events",
            "Trigger the same notification-worthy state repeatedly within the email rate-limit interval.",
            (
                "Do not control the computer. Return 'True' if notification logs show duplicate emails were "
                "suppressed or rate-limited. Return 'False' otherwise."
            ),
            "email rate limit was enforced",
            "email rate limit was not enforced",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("email min_interval_sec setting", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO05_SELF_RECIPIENT = case(
    "stage07_scenario05_email_self_recipient",
    "stage07_email_notification",
    "Scenario 5: verify email is addressed to the SMTP account itself.",
    (
        step(
            "send_self_email",
            "Run an operation that sends an email notification to the SMTP account itself.",
            (
                "Do not control the computer. Return 'True' if notification logs show the recipient matches "
                "the SMTP account address. Return 'False' otherwise."
            ),
            "email recipient is SMTP account itself",
            "email recipient is not SMTP account itself",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("SMTP account file: /home/nama/mail-send-vert.txt", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO06_EXPECTED_FAILURE_SMTP_AUTH = case(
    "stage07_scenario06_expected_failure_smtp_auth",
    "stage07_email_notification",
    "Scenario 6: expected failure; invalid SMTP credentials should be logged without crashing.",
    (
        step(
            "send_with_invalid_smtp",
            "Run a test notification with deliberately invalid SMTP credentials.",
            (
                "Do not control the computer. Return 'True' if notification logs show SMTP authentication "
                "failure and the main operation remains safe. Return 'False' otherwise."
            ),
            "SMTP auth failure was logged safely",
            "SMTP auth failure was not handled safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("test SMTP failure fixture", "notification log"),
)


STAGE07_SCENARIO07_ATTACHMENT_LIMIT = case(
    "stage07_scenario07_attachment_limit",
    "stage07_email_notification",
    "Scenario 7: verify screenshot attachments obey configured size limits.",
    (
        step(
            "send_large_attachment_notification",
            "Trigger an email notification with a screenshot larger than the configured attachment limit.",
            (
                "Do not control the computer. Return 'True' if notification logs show the screenshot was "
                "resized, omitted, or rejected according to the attachment limit. Return 'False' otherwise."
            ),
            "email attachment limit was enforced",
            "email attachment limit was not enforced",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("email attachment settings", "notification log") + API_HID_REQUIRES,
)


STAGE07_SCENARIO08_EMAIL_DISABLED = case(
    "stage07_scenario08_email_disabled_no_send",
    "stage07_email_notification",
    "Scenario 8: verify disabled email does not send but records skipped notification.",
    (
        step(
            "email_disabled_event",
            "Disable email notifications, then run a short operation that normally emits a completion email.",
            (
                "Do not control the computer. Return 'True' if no SMTP send occurs and notification logs "
                "show the email was skipped because email is disabled. Return 'False' otherwise."
            ),
            "disabled email was skipped and logged",
            "disabled email was sent or not logged",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("email enabled setting", "notification log") + API_HID_REQUIRES,
)


STAGE08_SCENARIO01_PROGRESS = case(
    "stage08_scenario01_progress_display",
    "stage08_long_running",
    "Scenario 1: verify long-running progress display.",
    (
        step(
            "start_long_plan",
            "Start a multi-step research-and-write plan that is long enough to show progress.",
            (
                "Do not control the computer. Return 'True' if progress, current step, and estimated "
                "remaining work are visible. Return 'False' otherwise."
            ),
            "progress is visible",
            "progress is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("progress model",) + API_HID_REQUIRES,
)


STAGE08_SCENARIO02_SUSPEND_RESUME = case(
    "stage08_scenario02_suspend_resume",
    "stage08_long_running",
    "Scenario 2: verify suspend and resume of a long-running plan.",
    (
        step(
            "suspend_and_resume",
            "Suspend the long-running plan, then resume it after recapturing the screen.",
            (
                "Do not control the computer. Return 'True' if the plan resumed from saved state after "
                "screen verification. Return 'False' otherwise."
            ),
            "plan resumed from saved state",
            "plan did not resume safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("suspend/resume persistence", "screen verification") + API_HID_REQUIRES,
)


STAGE08_SCENARIO03_SCREEN_DRIFT = case(
    "stage08_scenario03_screen_drift_requires_approval",
    "stage08_long_running",
    "Scenario 3: verify resume asks for approval when the screen changed too much.",
    (
        step(
            "resume_after_screen_drift",
            "Suspend a plan, change the visible screen, then try to resume.",
            (
                "Do not control the computer. Return 'True' if resume is blocked or approval-pending due "
                "to screen difference. Return 'False' otherwise."
            ),
            "screen drift required approval",
            "screen drift did not require approval",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("screen-difference check", "approval queue") + API_HID_REQUIRES,
)


STAGE08_SCENARIO04_LONG_PLAN_WARNING = case(
    "stage08_scenario04_long_plan_warning",
    "stage08_long_running",
    "Scenario 4: verify long plans show warnings before execution.",
    (
        step(
            "create_long_plan",
            "Create a plan that exceeds the configured long-operation threshold.",
            (
                "Do not control the computer. Return 'True' if a long-operation warning is visible before "
                "execution. Return 'False' otherwise."
            ),
            "long-plan warning is visible",
            "long-plan warning is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("long-operation threshold settings",) + API_HID_REQUIRES,
)


STAGE08_SCENARIO05_CANCEL_LONG_PLAN = case(
    "stage08_scenario05_cancel_long_plan",
    "stage08_long_running",
    "Scenario 5: verify a long-running plan can be cancelled cleanly.",
    (
        step(
            "cancel_long_plan",
            "Start a long-running plan, then cancel it from the control surface.",
            (
                "Do not control the computer. Return 'True' if the plan is cancelled, progress stops, and "
                "no further PC operations occur. Return 'False' otherwise."
            ),
            "long plan cancelled cleanly",
            "long plan did not cancel cleanly",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("long-running plan state", "cancel control") + API_HID_REQUIRES,
)


STAGE08_SCENARIO06_EXPECTED_FAILURE_STEP_ERROR = case(
    "stage08_scenario06_expected_failure_step_error",
    "stage08_long_running",
    "Scenario 6: expected failure; a failed long-plan step should stop or request intervention.",
    (
        step(
            "long_plan_step_failure",
            "Start a long-running plan that includes opening DefinitelyNotARealApp12345 as one step.",
            (
                "Do not control the computer. Return 'True' if the plan records the failed step and stops "
                "or asks for intervention instead of continuing blindly. Return 'False' otherwise."
            ),
            "failed long-plan step was handled safely",
            "failed long-plan step was not handled safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("long-running plan state", "step failure reporting") + API_HID_REQUIRES,
)


STAGE08_SCENARIO07_RESUME_AFTER_REBOOT = case(
    "stage08_scenario07_resume_after_process_restart",
    "stage08_long_running",
    "Scenario 7: verify persisted suspend state survives a process restart.",
    (
        step(
            "resume_after_restart",
            "Suspend a long-running plan, restart the Pi-side process, then inspect the resume state.",
            (
                "Do not control the computer. Return 'True' if the suspended plan is visible after restart "
                "and requires screen verification before resuming. Return 'False' otherwise."
            ),
            "suspend state survived process restart",
            "suspend state did not survive process restart",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("persistent runtime state", "process restart fixture") + API_HID_REQUIRES,
)


STAGE09_SCENARIO01_USAGE_DISPLAY = case(
    "stage09_scenario01_operation_token_usage",
    "stage09_token_budget",
    "Scenario 1: verify token usage is displayed per operation.",
    (
        step(
            "show_operation_usage",
            "Record a token usage fixture through the WebUI token test endpoint.",
            (
                "Do not control the computer. Return 'True' if the Logs view has System Log and Token Graph "
                "elements and the recorded token usage appears in /api/logs/detail. Return 'False' otherwise."
            ),
            "operation token usage is visible",
            "operation token usage is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token usage log",) + API_HID_REQUIRES,
)


STAGE09_SCENARIO02_PLAN_PREDICTION = case(
    "stage09_scenario02_plan_token_prediction",
    "stage09_token_budget",
    "Scenario 2: verify token usage is predicted before a multi-step plan runs.",
    (
        step(
            "show_plan_prediction",
            "Create a multi-step token prediction through /api/tokens/predict.",
            (
                "Do not control the computer. Return 'True' if the predicted token usage is returned by the API "
                "and is visible in /api/status token_prediction before plan execution. Return 'False' otherwise."
            ),
            "plan token prediction is visible",
            "plan token prediction is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token prediction model",) + API_HID_REQUIRES,
)


STAGE09_SCENARIO03_BUDGET_ENFORCEMENT = case(
    "stage09_scenario03_budget_exceeded_blocks",
    "stage09_token_budget",
    "Scenario 3: verify budget overflow blocks or requires approval.",
    (
        step(
            "exceed_budget",
            "Request a token budget check that exceeds the configured per-plan token budget.",
            (
                "Do not control the computer. Return 'True' if the WebUI enters approval-pending state "
                "because of token budget. Return 'False' otherwise."
            ),
            "token budget was enforced",
            "token budget was not enforced",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token budget settings", "approval queue") + API_HID_REQUIRES,
)


STAGE09_SCENARIO04_DAILY_AGGREGATE = case(
    "stage09_scenario04_daily_token_aggregate",
    "stage09_token_budget",
    "Scenario 4: verify daily token totals are logged and visible.",
    (
        step(
            "show_daily_total",
            "Record two token usage fixtures on the same day and inspect /api/tokens.",
            (
                "Do not control the computer. Return 'True' if the daily token total returned by /api/tokens "
                "includes both fixture rows. Return 'False' otherwise."
            ),
            "daily token total is visible",
            "daily token total is not visible",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token usage log", "daily aggregate view") + API_HID_REQUIRES,
)


STAGE09_SCENARIO05_EXPECTED_FAILURE_MISSING_USAGE = case(
    "stage09_scenario05_expected_failure_missing_usage",
    "stage09_token_budget",
    "Scenario 5: expected failure; missing token usage data should be logged and surfaced.",
    (
        step(
            "simulate_missing_usage",
            "Run the WebUI missing-usage fixture whose response has no token usage metadata.",
            (
                "Do not control the computer. Return 'True' if the system records unknown token usage, "
                "shows a warning, and records an estimated token count instead of treating usage as zero. "
                "Return 'False' otherwise."
            ),
            "missing token usage was handled safely",
            "missing token usage was not handled safely",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token usage log", "API response fixture"),
)


STAGE09_SCENARIO06_BUDGET_RESET = case(
    "stage09_scenario06_daily_budget_reset",
    "stage09_token_budget",
    "Scenario 6: verify daily token budget resets on the configured day boundary.",
    (
        step(
            "daily_budget_reset",
            "Record token usage fixtures on both sides of a UTC day boundary and inspect /api/tokens ranges.",
            (
                "Do not control the computer. Return 'True' if each day range only includes that day's usage. "
                "Return 'False' otherwise."
            ),
            "daily token budget reset is correct",
            "daily token budget reset is incorrect",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token usage log", "test clock fixture"),
)


STAGE09_SCENARIO07_PER_STEP_BUDGET = case(
    "stage09_scenario07_per_step_budget_warning",
    "stage09_token_budget",
    "Scenario 7: verify per-step token budget warnings are shown during a plan.",
    (
        step(
            "per_step_budget_warning",
            "Create a multi-step token prediction with a small per-step token budget.",
            (
                "Do not control the computer. Return 'True' if /api/tokens/predict and /api/status show a "
                "per-step token budget warning before execution. Return 'False' otherwise."
            ),
            "per-step token warning is visible",
            "per-step token warning is missing",
        ),
    ),
    implemented=True,
    pending_reason="",
    requires=("token budget settings", "planning mode enabled") + API_HID_REQUIRES,
)


STAGE10_SCENARIO01_SCREEN_COMMAND = case(
    "stage10_scenario01_discord_screen_command",
    "stage10_discord",
    "Scenario 1: verify /screen works in configured guild/channel/user scope.",
    (
        step(
            "discord_screen",
            "Send a Discord /screen command from an allowed user and channel configured in the project config.",
            (
                "Do not control the computer. Return 'True' if local status shows the Discord screen request "
                "was received and processed. Return 'False' otherwise."
            ),
            "Discord /screen was processed",
            "Discord /screen was not processed",
        ),
    ),
    implemented=True,
    pending_reason="Discord integration is scheduled as the final development stage.",
    requires=("project Discord config", "Discord bot token") + API_HID_REQUIRES,
)


STAGE10_SCENARIO02_REQUEST_COMMAND = case(
    "stage10_scenario02_discord_request_command",
    "stage10_discord",
    "Scenario 2: verify /request controls the target PC and records Discord as the source.",
    (
        step(
            "discord_request",
            "Send a Discord /request command to open the browser from an allowed user and channel.",
            (
                "Do not control the computer. Return 'True' if the browser is displayed and the command "
                "is logged as coming from Discord. Return 'False' otherwise."
            ),
            "Discord request controlled the target PC",
            "Discord request did not complete correctly",
        ),
    ),
    implemented=True,
    pending_reason="Discord integration is scheduled as the final development stage.",
    requires=("project Discord config", "Discord bot token") + API_HID_REQUIRES,
)


STAGE10_SCENARIO03_STOP_COMMAND = case(
    "stage10_scenario03_discord_stop_command",
    "stage10_discord",
    "Scenario 3: verify /stop triggers emergency stop.",
    (
        step(
            "discord_stop",
            "Send a Discord /stop command from an allowed user and channel.",
            (
                "Do not control the computer. Return 'True' if emergency stop is visible and logged as "
                "coming from Discord. Return 'False' otherwise."
            ),
            "Discord /stop triggered emergency stop",
            "Discord /stop did not trigger emergency stop",
        ),
    ),
    implemented=True,
    pending_reason="Discord integration is scheduled as the final development stage.",
    requires=("project Discord config", "Discord bot token") + API_HID_REQUIRES,
)


STAGE10_SCENARIO04_APPROVAL_COMMANDS = case(
    "stage10_scenario04_discord_approve_reject",
    "stage10_discord",
    "Scenario 4: verify Discord approve/reject handles pending approval safely.",
    (
        step(
            "discord_approve_reject",
            "Create an approval-pending operation, then send /approve or /reject from Discord.",
            (
                "Do not control the computer. Return 'True' if the approval decision is applied and logged "
                "as coming from Discord. Return 'False' otherwise."
            ),
            "Discord approval command was applied",
            "Discord approval command was not applied",
        ),
    ),
    implemented=True,
    pending_reason="Discord integration is scheduled as the final development stage.",
    requires=("project Discord config", "Discord bot token", "approval queue") + API_HID_REQUIRES,
)


STAGE10_SCENARIO05_UNAUTHORIZED_IGNORED = case(
    "stage10_scenario05_discord_unauthorized_ignored",
    "stage10_discord",
    "Scenario 5: verify unauthorized Discord guild/channel/user commands are ignored.",
    (
        step(
            "discord_unauthorized",
            "Send a Discord command from a guild, channel, or user not allowed by the project config.",
            (
                "Do not control the computer. Return 'True' if the command is ignored, logged as denied, "
                "and no PC operation occurs. Return 'False' otherwise."
            ),
            "unauthorized Discord command was ignored",
            "unauthorized Discord command was not ignored",
        ),
    ),
    implemented=True,
    pending_reason="Discord integration is scheduled as the final development stage.",
    requires=("project Discord config", "Discord bot token", "security log") + API_HID_REQUIRES,
)


STAGE10_SCENARIO06_ATTACHMENT_LIMIT = case(
    "stage10_scenario06_discord_attachment_limit",
    "stage10_discord",
    "Scenario 6: verify Discord screenshot attachment limits are enforced.",
    (
        step(
            "discord_large_screen",
            "Send a Discord /screen command when the screenshot exceeds the configured attachment size limit.",
            (
                "Do not control the computer. Return 'True' if the screenshot is resized, omitted, or "
                "reported as too large according to config. Return 'False' otherwise."
            ),
            "Discord attachment limit was enforced",
            "Discord attachment limit was not enforced",
        ),
    ),
    implemented=True,
    pending_reason="Discord attachment size enforcement is not implemented yet.",
    requires=("project Discord config", "Discord bot token", "attachment limit settings") + API_HID_REQUIRES,
)


STAGE10_SCENARIO07_RATE_LIMIT = case(
    "stage10_scenario07_discord_rate_limit",
    "stage10_discord",
    "Scenario 7: verify repeated Discord commands are rate-limited.",
    (
        step(
            "discord_rate_limit",
            "Send repeated Discord /screen commands faster than the configured rate limit.",
            (
                "Do not control the computer. Return 'True' if duplicate commands are throttled or queued "
                "according to config and no uncontrolled PC operations occur. Return 'False' otherwise."
            ),
            "Discord rate limit was enforced",
            "Discord rate limit was not enforced",
        ),
    ),
    implemented=True,
    pending_reason="Discord rate limiting is not implemented yet.",
    requires=("project Discord config", "Discord bot token", "rate limit settings") + API_HID_REQUIRES,
)


STAGE10_SCENARIO08_EXPECTED_FAILURE_BOT_OFFLINE = case(
    "stage10_scenario08_expected_failure_bot_offline",
    "stage10_discord",
    "Scenario 8: expected failure; Discord bot offline state should be reported safely.",
    (
        step(
            "discord_bot_offline",
            "Start Discord mode without a valid bot connection.",
            (
                "Do not control the computer. Return 'True' if the system reports Discord offline or "
                "connection failure and WebUI/CLI controls remain usable. Return 'False' otherwise."
            ),
            "Discord offline failure was handled safely",
            "Discord offline failure was not handled safely",
        ),
    ),
    implemented=True,
    pending_reason="Discord offline failure handling is not implemented yet.",
    requires=("project Discord config", "Discord failure fixture"),
)


ALL_CASES = (
    OPEN_BROWSER,
    STAGE01_SCENARIO02_RUN_DIALOG,
    STAGE01_SCENARIO03_TEXT_ENTRY,
    STAGE01_SCENARIO04_CALCULATOR_BASIC,
    STAGE01_SCENARIO05_PAINT_TEXT,
    STAGE01_SCENARIO06_EXPECTED_FAILURE_UNSUPPORTED_DRAG,
    STAGE01_SCENARIO07_EXPECTED_FAILURE_NONEXISTENT_APP,
    STAGE02_SCENARIO01_USER_INPUT_LOG,
    STAGE02_SCENARIO02_OPERATION_LOG,
    STAGE02_SCENARIO03_SCREENSHOT_LOG,
    STAGE02_SCENARIO04_STORAGE_LIMIT,
    STAGE02_SCENARIO05_ERROR_LOG,
    STAGE02_SCENARIO06_LOG_QUERY_FILTERS,
    STAGE02_SCENARIO07_CORRUPT_DB_RECOVERY,
    STAGE03_SCENARIO01_EMERGENCY_STOP,
    STAGE03_SCENARIO02_NEW_COMMAND_RESET,
    STAGE03_SCENARIO03_SUSPEND_RESUME_STATE,
    STAGE03_SCENARIO04_CANCEL_APPROVAL_ON_STOP,
    STAGE04_SCENARIO01_LAN_WEBUI_STATUS,
    STAGE04_SCENARIO02_MANUAL_COMMAND,
    STAGE04_SCENARIO03_PLANNING_TOGGLE,
    STAGE04_SCENARIO04_LOG_PANES,
    STAGE04_SCENARIO05_INVALID_HID_COMMAND,
    STAGE04_SCENARIO06_WEBUI_EMERGENCY_BUTTON,
    STAGE04_SCENARIO07_REFRESH_SCREENSHOT,
    STAGE04_SCENARIO08_WEBUI_REQUEST_OPEN_BROWSER,
    STAGE04_SCENARIO09_WEBUI_REQUEST_RUN_DIALOG,
    STAGE04_SCENARIO10_WEBUI_REQUEST_TEXT_EDITOR_INPUT,
    STAGE04_SCENARIO11_WEBUI_REQUEST_CALCULATOR_BASIC,
    STAGE04_SCENARIO12_WEBUI_REQUEST_PAINT_TEXT,
    STAGE04_SCENARIO13_WEBUI_REQUEST_EXPECTED_FAILURE_UNSUPPORTED_DRAG,
    STAGE04_SCENARIO14_WEBUI_REQUEST_EXPECTED_FAILURE_NONEXISTENT_APP,
    STAGE05_SCENARIO01_DEFAULT_WEB_SEARCH,
    STAGE05_SCENARIO02_GOOGLE_SEARCH,
    STAGE05_SCENARIO03_WIKIPEDIA_SEARCH,
    STAGE05_SCENARIO04_ARXIV_SEARCH,
    STAGE05_SCENARIO05_PLANNING_DISABLED,
    STAGE05_SCENARIO06_CALCULATOR_PLAN,
    STAGE05_SCENARIO07_PAINT_TEXT_PLAN,
    STAGE05_SCENARIO08_CALCULATOR_TO_EDITOR,
    STAGE05_SCENARIO09_BROWSER_TO_PAINT,
    STAGE05_SCENARIO10_EXPECTED_FAILURE_UNREACHABLE_URL,
    STAGE05_SCENARIO11_EXPECTED_FAILURE_MISSING_APP,
    STAGE05_SCENARIO12_EXPECTED_FAILURE_DIVIDE_BY_ZERO,
    STAGE05_SCENARIO13_EXPECTED_FAILURE_UNSUPPORTED_FREEHAND,
    STAGE06_SCENARIO01_SAVE_APPROVAL,
    STAGE06_SCENARIO02_SEND_APPROVAL,
    STAGE06_SCENARIO03_LOGIN_APPROVAL,
    STAGE06_SCENARIO04_REJECT_APPROVAL,
    STAGE06_SCENARIO05_APPROVAL_TIMEOUT,
    STAGE06_SCENARIO06_DELETE_APPROVAL,
    STAGE06_SCENARIO07_INSTALL_APPROVAL,
    STAGE06_SCENARIO08_SAFE_READ_NO_APPROVAL,
    STAGE06_SCENARIO09_EXPECTED_FAILURE_UNAPPROVED_ACTION,
    STAGE07_SCENARIO01_COMPLETION_EMAIL,
    STAGE07_SCENARIO02_EMERGENCY_EMAIL,
    STAGE07_SCENARIO03_APPROVAL_EMAIL,
    STAGE07_SCENARIO04_RATE_LIMIT,
    STAGE07_SCENARIO05_SELF_RECIPIENT,
    STAGE07_SCENARIO06_EXPECTED_FAILURE_SMTP_AUTH,
    STAGE07_SCENARIO07_ATTACHMENT_LIMIT,
    STAGE07_SCENARIO08_EMAIL_DISABLED,
    STAGE08_SCENARIO01_PROGRESS,
    STAGE08_SCENARIO02_SUSPEND_RESUME,
    STAGE08_SCENARIO03_SCREEN_DRIFT,
    STAGE08_SCENARIO04_LONG_PLAN_WARNING,
    STAGE08_SCENARIO05_CANCEL_LONG_PLAN,
    STAGE08_SCENARIO06_EXPECTED_FAILURE_STEP_ERROR,
    STAGE08_SCENARIO07_RESUME_AFTER_REBOOT,
    STAGE09_SCENARIO01_USAGE_DISPLAY,
    STAGE09_SCENARIO02_PLAN_PREDICTION,
    STAGE09_SCENARIO03_BUDGET_ENFORCEMENT,
    STAGE09_SCENARIO04_DAILY_AGGREGATE,
    STAGE09_SCENARIO05_EXPECTED_FAILURE_MISSING_USAGE,
    STAGE09_SCENARIO06_BUDGET_RESET,
    STAGE09_SCENARIO07_PER_STEP_BUDGET,
    STAGE10_SCENARIO01_SCREEN_COMMAND,
    STAGE10_SCENARIO02_REQUEST_COMMAND,
    STAGE10_SCENARIO03_STOP_COMMAND,
    STAGE10_SCENARIO04_APPROVAL_COMMANDS,
    STAGE10_SCENARIO05_UNAUTHORIZED_IGNORED,
    STAGE10_SCENARIO06_ATTACHMENT_LIMIT,
    STAGE10_SCENARIO07_RATE_LIMIT,
    STAGE10_SCENARIO08_EXPECTED_FAILURE_BOT_OFFLINE,
)


CASES = {test_case.name: test_case for test_case in ALL_CASES}
CASES["open_browser_e2e"] = OPEN_BROWSER
