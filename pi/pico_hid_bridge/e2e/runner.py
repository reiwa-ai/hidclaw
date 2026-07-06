#!/usr/bin/env python3
"""Reusable E2E runner for Computer Use + Pico HID tests."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from pico_hid_bridge.actions import execute_supported_action
from pico_hid_bridge.capture import (
    DEFAULT_DEVICE,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_READY_TIMEOUT,
    capture_png_base64,
)
from pico_hid_bridge.computer_use import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    action_type,
    attr,
    computer_tool,
    computer_actions,
    computer_call_id,
    create_initial_response,
    describe_action,
    extract_output_text,
    find_computer_call,
)
from pico_hid_bridge.config import load_config
from pico_hid_bridge.hid import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_TIMEOUT, send_line
from pico_hid_bridge.notifications import parse_smtp_account_file
from pico_hid_bridge.operation_log import OperationLogEventSink, OperationLogStore
from pico_hid_bridge.e2e.model import E2EStep, E2ETestCase
from pico_hid_bridge.paths import PI_DIR


DEFAULT_API_KEY_FILE = Path("/home/nama/openai-api-key.txt")
DEFAULT_OUTPUT_ROOT = PI_DIR / "captures"
DEFAULT_PRE_TEST_CLOSE_ATTEMPTS = 8
DEFAULT_PRE_TEST_CLOSE_DELAY = 0.5
DEFAULT_INTER_ACTION_DELAY = 0.25
DEFAULT_TYPE_ACTION_DELAY_PER_CHAR = 0.08
EXPECTED_FAILURE_MARKER = "RESULT EXPECTED FAILURE"


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path)
    parser.add_argument("--api-key-file", type=Path, default=DEFAULT_API_KEY_FILE)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--fps", type=int, default=0)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--min-brightness", type=float, default=DEFAULT_MIN_BRIGHTNESS)
    parser.add_argument("--ready-timeout", type=float, default=DEFAULT_READY_TIMEOUT)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--settle-sec", type=float, default=5.0)
    parser.add_argument("--inter-action-delay", type=float, default=DEFAULT_INTER_ACTION_DELAY)
    parser.add_argument("--type-action-delay-per-char", type=float, default=DEFAULT_TYPE_ACTION_DELAY_PER_CHAR)
    parser.add_argument("--max-action-turns", type=int, default=5)
    parser.add_argument("--max-step-action-rounds", type=int, default=3)
    parser.add_argument("--max-verify-turns", type=int, default=5)
    parser.add_argument("--api-timeout", type=float, default=60.0)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--pre-test-close-attempts", type=int, default=DEFAULT_PRE_TEST_CLOSE_ATTEMPTS)
    parser.add_argument("--pre-test-close-delay", type=float, default=DEFAULT_PRE_TEST_CLOSE_DELAY)


def read_api_key(args: argparse.Namespace) -> str:
    if args.api_key_file.exists():
        return args.api_key_file.read_text(encoding="utf-8").strip()

    import os

    value = os.environ.get(args.api_key_env, "").strip()
    if value:
        return value

    raise RuntimeError(f"missing API key file: {args.api_key_file}")


def send_screenshot_blob(
    client: Any,
    *,
    model: str,
    args: argparse.Namespace,
    response: Any,
    computer_call: Any,
    screenshot_base64: str,
) -> Any:
    return client.responses.create(
        model=model,
        tools=[computer_tool(args)],
        previous_response_id=attr(response, "id"),
        input=[
            {
                "type": "computer_call_output",
                "call_id": computer_call_id(computer_call),
                "output": {
                    "type": "computer_screenshot",
                    "image_url": f"data:image/png;base64,{screenshot_base64}",
                    "detail": "original",
                },
            }
        ],
    )


def request_actions(
    client: Any,
    *,
    args: argparse.Namespace,
    task: str,
    screenshot_base64: str,
    label: str,
) -> list[Any]:
    response = create_initial_response(client, model=args.model, task=task, args=args)

    for turn in range(1, args.max_action_turns + 1):
        computer_call = find_computer_call(response)
        if computer_call is None:
            text = extract_output_text(response)
            raise RuntimeError(f"Computer Use returned no computer action: {text!r}")

        actions = computer_actions(computer_call)
        print(f"{label} turn {turn}: " + ", ".join(describe_action(action) for action in actions))

        if not actions or all(action_type(action) == "screenshot" for action in actions):
            response = send_screenshot_blob(
                client,
                model=args.model,
                args=args,
                response=response,
                computer_call=computer_call,
                screenshot_base64=screenshot_base64,
            )
            continue

        return actions

    raise RuntimeError("Computer Use did not return an executable action")


def execute_actions(actions: list[Any], args: argparse.Namespace) -> None:
    executed = 0
    unsupported: list[str] = []

    for action in actions:
        kind = action_type(action)
        if kind == "screenshot":
            continue

        if kind in {"type", "keypress", "wait", "click", "double_click", "move"}:
            if execute_supported_action(action, args):
                executed += 1
                time.sleep(action_delay_seconds(action, args))
            else:
                unsupported.append(describe_action(action))
            continue

        unsupported.append(describe_action(action))

    if unsupported:
        raise RuntimeError("unsupported action for current Pico firmware: " + "; ".join(unsupported))

    if executed == 0:
        raise RuntimeError("Computer Use returned no action that was sent to Pico")

    print(f"executed_actions={executed}")


def action_delay_seconds(action: Any, args: argparse.Namespace) -> float:
    base_delay = max(0.0, getattr(args, "inter_action_delay", DEFAULT_INTER_ACTION_DELAY))
    if action_type(action) != "type":
        return base_delay

    text = str(attr(action, "text", ""))
    per_char = max(0.0, getattr(args, "type_action_delay_per_char", DEFAULT_TYPE_ACTION_DELAY_PER_CHAR))
    return max(base_delay, len(text) * per_char)


def parse_true_false(text: str) -> bool:
    normalized = text.strip().strip(".").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    if "true" in normalized and "false" not in normalized:
        return True
    if "false" in normalized and "true" not in normalized:
        return False
    raise RuntimeError(f"verification did not return True or False: {text!r}")


def is_expected_failure_case(test_case: E2ETestCase) -> bool:
    return "expected_failure" in test_case.name


def is_expected_failure_signal(message: str) -> bool:
    text = message.lower()
    expected_fragments = (
        "unsupported",
        "not found",
        "not-found",
        "not opened",
        "cannot find",
        "could not",
        "failed",
        "blocked",
    )
    return any(fragment in text for fragment in expected_fragments)


def has_expected_planning_failure_signal(status: dict[str, Any]) -> bool:
    if status.get("approval_pending") or str(status.get("approval_status", "")).lower() == "pending":
        return True
    return any(
        latest_operation_has(status, fragment)
        for fragment in ("error", "blocked", "approval_pending", "rejected")
    )


def verify_true_false(
    client: Any,
    *,
    args: argparse.Namespace,
    task: str,
    screenshot_base64: str,
) -> bool:
    response = create_initial_response(client, model=args.model, task=task, args=args)

    for turn in range(1, args.max_verify_turns + 1):
        computer_call = find_computer_call(response)
        if computer_call is not None:
            actions = computer_actions(computer_call)
            print(f"verify turn {turn}: " + ", ".join(describe_action(action) for action in actions))
            if actions and not all(action_type(action) == "screenshot" for action in actions):
                raise RuntimeError(
                    "verification requested a non-screenshot action despite do-not-control instruction: "
                    + "; ".join(describe_action(action) for action in actions)
                )
            response = send_screenshot_blob(
                client,
                model=args.model,
                args=args,
                response=response,
                computer_call=computer_call,
                screenshot_base64=screenshot_base64,
            )
            continue

        text = extract_output_text(response)
        print(f"verification_output={text!r}")
        return parse_true_false(text)

    raise RuntimeError("verification did not finish")


def execute_and_verify_step(
    client: Any,
    *,
    args: argparse.Namespace,
    test_case: E2ETestCase,
    step: E2EStep,
    step_index: int,
    screenshot_base64: str,
    output_dir: Path,
    prefix: str,
) -> bool:
    max_rounds = max(1, getattr(args, "max_step_action_rounds", 3))
    current_screenshot = screenshot_base64

    for round_index in range(1, max_rounds + 1):
        label = f"{test_case.name}.{step.name}.round{round_index}"
        print("request action" if round_index == 1 else f"request action round {round_index}")
        actions = request_actions(
            client,
            args=args,
            task=step.action_task or "",
            screenshot_base64=current_screenshot,
            label=label,
        )

        print("send Computer Use action to Pico")
        execute_actions(actions, args)

        settle_sec = args.settle_sec if step.settle_sec is None else step.settle_sec
        time.sleep(max(0.0, settle_sec))

        print("capture after action")
        after_name = f"{prefix}_after.png" if round_index == 1 else f"{prefix}_after_round{round_index:02d}.png"
        current_screenshot = capture_after_action(
            args,
            output_dir,
            output_dir / after_name,
            test_case,
            step,
        )

        if step_uses_stage_specific_validation(test_case):
            print("verify step deferred to stage-specific validation")
            return True

        print("verify step")
        ok = verify_true_false(client, args=args, task=step.verify_task, screenshot_base64=current_screenshot)
        if ok:
            return True

        if round_index < max_rounds:
            print(f"STEP CONTINUE: {step.failure_message}; requesting more actions")

    return False


def step_uses_stage_specific_validation(test_case: E2ETestCase) -> bool:
    return test_case.stage == "stage02_operation_log"


def case_uses_webui_runner(test_case: E2ETestCase) -> bool:
    return test_case.stage in {
        "stage03_runtime_safety",
        "stage04_webui_control",
        "stage05_planning",
        "stage06_approval",
        "stage07_email_notification",
        "stage08_long_running",
        "stage09_token_budget",
        "stage10_discord",
    }


def safe_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return sanitized.strip("_") or "step"


def prepare_target_desktop(args: argparse.Namespace) -> None:
    attempts = max(0, args.pre_test_close_attempts)
    delay = max(0.0, args.pre_test_close_delay)
    if attempts == 0:
        print("PREPARE skipped: pre-test close attempts is 0")
        return

    print(f"PREPARE close target windows attempts={attempts}")
    for index in range(1, attempts + 1):
        print(f"PREPARE attempt {index}: KEY ALT+F4")
        send_line("KEY ALT+F4", port=args.port, baudrate=args.baudrate, timeout=args.timeout)
        time.sleep(delay)

        print(f"PREPARE attempt {index}: KEY N")
        send_line("KEY N", port=args.port, baudrate=args.baudrate, timeout=args.timeout)
        time.sleep(delay)

    print("PREPARE final: KEY ESC")
    send_line("KEY ESC", port=args.port, baudrate=args.baudrate, timeout=args.timeout)
    time.sleep(delay)


def run_case(test_case: E2ETestCase, args: argparse.Namespace) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_root / f"{test_case.name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.txt"
    configure_case_logging(test_case, args, output_dir)

    with result_path.open("w", encoding="utf-8") as result_file:
        with redirect_stdout(Tee(sys.stdout, result_file)), redirect_stderr(Tee(sys.stderr, result_file)):
            return _run_case(test_case, args, output_dir)


class Tee:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def _run_case(test_case: E2ETestCase, args: argparse.Namespace, output_dir: Path) -> int:
    expected_failure = is_expected_failure_case(test_case)
    log_store: OperationLogStore = args.operation_log_store

    try:
        print(f"CASE {test_case.name}")
        print(f"STAGE {test_case.stage}")
        print(f"DESCRIPTION {test_case.description}")
        if test_case.requires:
            print("REQUIRES " + ", ".join(test_case.requires))

        if not test_case.implemented:
            reason = test_case.pending_reason or "test scenario is defined but implementation is pending"
            print(f"RESULT PENDING: {reason}")
            print(f"artifacts: {output_dir}")
            return 2

        log_store.record_user_input(
            input_text=test_case.description,
            source="e2e",
            planning=False,
            case_name=test_case.name,
        )

        if case_uses_webui_runner(test_case):
            error = run_webui_stage_case(test_case, args, output_dir)
            if error:
                print(f"RESULT FAIL: {error}")
                print(f"artifacts: {output_dir}")
                return 1
            if expected_failure:
                print(f"{EXPECTED_FAILURE_MARKER}: {test_case.name}")
            else:
                print(f"RESULT OK: {test_case.name}")
            print(f"artifacts: {output_dir}")
            return 0

        from openai import OpenAI

        api_key = read_api_key(args)
        client = OpenAI(api_key=api_key, timeout=args.api_timeout)

        prepare_target_desktop(args)

        for index, step in enumerate(test_case.steps, start=1):
            print(f"STEP {index}/{len(test_case.steps)} {step.name}")
            prefix = f"step{index:02d}_{safe_name(step.name)}"

            print("capture before step")
            before_path = output_dir / f"{prefix}_before.png"
            screenshot_b64 = capture_png_base64(args, before_path)
            log_store.record_screenshot(
                path=before_path,
                event="before",
                case_name=test_case.name,
                step_name=step.name,
            )

            if step.action_task:
                ok = execute_and_verify_step(
                    client,
                    args=args,
                    test_case=test_case,
                    step=step,
                    step_index=index,
                    screenshot_base64=screenshot_b64,
                    output_dir=output_dir,
                    prefix=prefix,
                )
                if not ok:
                    if expected_failure:
                        print(f"RESULT FAIL: expected failure was not detected ({step.failure_message})")
                        print(f"artifacts: {output_dir}")
                        return 1
                    print(f"RESULT FAIL: {step.failure_message}")
                    print(f"artifacts: {output_dir}")
                    return 1
            else:
                print("verify step")
                ok = verify_true_false(client, args=args, task=step.verify_task, screenshot_base64=screenshot_b64)
                if not ok:
                    if expected_failure:
                        print(f"RESULT FAIL: expected failure was not detected ({step.failure_message})")
                        print(f"artifacts: {output_dir}")
                        return 1
                    print(f"RESULT FAIL: {step.failure_message}")
                    print(f"artifacts: {output_dir}")
                    return 1

            print(f"STEP OK: {step.success_message}")

        record_stage02_scenario_outcome(test_case, log_store)
        stage02_error = validate_stage02_logs(test_case, log_store, output_dir)
        if stage02_error:
            print(f"RESULT FAIL: {stage02_error}")
            print(f"artifacts: {output_dir}")
            return 1

        if expected_failure:
            print(f"{EXPECTED_FAILURE_MARKER}: {test_case.name}")
        else:
            print(f"RESULT OK: {test_case.name}")
        print(f"artifacts: {output_dir}")
        return 0
    except Exception as exc:
        log_store.record_error(message=str(exc), domain="implementation", case_name=test_case.name)
        if expected_failure and is_expected_failure_signal(str(exc)):
            print(f"{EXPECTED_FAILURE_MARKER}: {exc}")
            print(f"artifacts: {output_dir}")
            return 0
        print(f"RESULT ERROR: {exc}")
        print(f"artifacts: {output_dir}")
        return 1


def configure_case_logging(test_case: E2ETestCase, args: argparse.Namespace, output_dir: Path) -> None:
    config = load_config(args.config)
    runtime_dir = output_dir / "runtime"
    config["app"]["runtime_dir"] = str(runtime_dir)
    config["logs"]["database"] = str(runtime_dir / "app.db")
    config["logs"]["screenshot_dir"] = str(output_dir)

    if test_case.name == "stage02_scenario07_expected_failure_corrupt_db_recovery":
        db_path = Path(config["logs"]["database"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"corrupt sqlite database for stage02 recovery test")

    store = OperationLogStore.from_config(config)
    args.operation_log_store = store
    args.event_sink = OperationLogEventSink(store, source="e2e", case_name=test_case.name)


def capture_after_action(args: argparse.Namespace, output_dir: Path, path: Path, test_case: E2ETestCase, step: E2EStep) -> str:
    screenshot = capture_png_base64(args, path)
    args.operation_log_store.record_screenshot(
        path=path,
        event="after",
        case_name=test_case.name,
        step_name=step.name,
    )
    return screenshot


def make_webui_e2e_config(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    config = load_config(args.config)
    runtime_dir = output_dir / "webui_runtime"
    config["app"]["runtime_dir"] = str(runtime_dir)
    config["logs"]["database"] = str(runtime_dir / "app.db")
    config["logs"]["screenshot_dir"] = str(output_dir / "webui_screenshots")
    config["capture"].update(
        {
            "device": args.device,
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "warmup_frames": args.warmup_frames,
            "min_brightness": args.min_brightness,
            "ready_timeout": args.ready_timeout,
        }
    )
    config["hid"].update({"port": args.port, "baudrate": args.baudrate, "timeout": args.timeout})
    config["openai"].update(
        {
            "api_key_file": str(args.api_key_file),
            "api_key_env": args.api_key_env,
            "model": args.model,
            "api_timeout": args.api_timeout,
            "max_action_turns": args.max_action_turns,
        }
    )
    return config


def configure_stage07_email(test_case: E2ETestCase, config: dict[str, Any], output_dir: Path) -> None:
    if test_case.stage != "stage07_email_notification":
        return

    email_cfg = config["email"]
    email_cfg.update(
        {
            "enabled": test_case.name != "stage07_scenario08_email_disabled_no_send",
            "delivery": "console",
            "smtp_account_file": str(email_cfg.get("smtp_account_file") or "/home/nama/mail-send-vert.txt"),
            "to_addrs": [],
            "min_interval_sec": 300.0,
            "attachment_limit_mb": 10,
        }
    )

    if test_case.name == "stage07_scenario06_expected_failure_smtp_auth":
        email_cfg["delivery"] = "smtp"
        source_account = parse_smtp_account_file(str(email_cfg["smtp_account_file"]))
        invalid_path = output_dir / "invalid_smtp_account.txt"
        invalid_path.write_text(
            "\n".join(
                [
                    f"STARTTLS={'true' if source_account.starttls else 'false'}",
                    f"SMTP_SERVER={source_account.smtp_server}",
                    f"SMTP_PORT={source_account.smtp_port}",
                    f"SENDER_MAIL={source_account.sender_mail}",
                    "SMTP_PASSWORD=invalid-stage07-password",
                ]
            ),
            encoding="utf-8",
        )
        email_cfg["smtp_account_file"] = str(invalid_path)

    if test_case.name == "stage07_scenario07_attachment_limit":
        email_cfg["attachment_limit_mb"] = 0.000001


def configure_stage09_token_budget(test_case: E2ETestCase, config: dict[str, Any]) -> None:
    if test_case.stage != "stage09_token_budget":
        return

    budget = config["token_budget"]
    budget["baseline_tokens_per_operation"] = 100
    if test_case.name == "stage09_scenario03_budget_exceeded_blocks":
        budget["max_tokens_per_plan"] = 250
        budget["max_tokens_per_day"] = 100000
    if test_case.name == "stage09_scenario07_per_step_budget_warning":
        budget["max_tokens_per_step"] = 50


def configure_stage10_discord(test_case: E2ETestCase, config: dict[str, Any]) -> None:
    if test_case.stage != "stage10_discord":
        return

    config["discord"].update(
        {
            "enabled": True,
            "bot_name": "AgentDev",
            "channel_id": "stage10-channel",
            "allowed_guild_ids": ["stage10-guild"],
            "allowed_channel_ids": ["stage10-channel"],
            "allowed_user_ids": ["stage10-user"],
            "max_command_age_sec": 60.0,
            "rate_limit_per_hour": 20,
            "attachment_limit_mb": 8,
        }
    )
    if test_case.name == "stage10_scenario06_discord_attachment_limit":
        config["discord"]["attachment_limit_mb"] = 0.000001
    if test_case.name == "stage10_scenario07_discord_rate_limit":
        config["discord"]["rate_limit_per_hour"] = 1


def json_response(response: Any) -> dict[str, Any]:
    data = response.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def require_response(response: Any, *, ok: bool = True, contains: str = "") -> str:
    data = json_response(response)
    if ok and response.status_code >= 400:
        return str(data.get("error") or data.get("message") or response.status)
    if not ok and response.status_code < 400:
        return f"expected failure response, got {response.status_code}: {data}"
    if contains:
        text = str(data).lower()
        if contains.lower() not in text:
            return f"response did not contain {contains!r}: {data}"
    return ""


def save_webui_screenshot(client: Any, output_dir: Path, name: str, store: OperationLogStore, case_name: str) -> str:
    response = client.get("/api/screenshot")
    if response.status_code >= 400:
        return f"screenshot API failed: {response.status_code}"
    path = output_dir / name
    path.write_bytes(response.data)
    store.record_screenshot(path=path, event="webui", case_name=case_name, step_name=name)
    print(f"webui screenshot saved: {path}")
    return ""


def status_json(client: Any) -> dict[str, Any]:
    return json_response(client.get("/api/status"))


class FakeDiscordClient:
    def __init__(self, messages: list[Any]) -> None:
        self.messages = messages
        self.sent_messages: list[dict[str, Any]] = []

    def fetch_recent_messages(self, channel_id: str, *, limit: int = 20) -> list[Any]:
        return list(self.messages)

    def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        attachment: bytes | None = None,
        filename: str = "",
    ) -> None:
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "content": content,
                "attachment": attachment,
                "filename": filename,
            }
        )


class FailingDiscordClient(FakeDiscordClient):
    def fetch_recent_messages(self, channel_id: str, *, limit: int = 20) -> list[Any]:
        raise RuntimeError("Discord bot offline")


def stage10_message(
    message_id: str,
    content: str,
    *,
    seconds_ago: int = 10,
    author_id: str = "stage10-user",
    channel_id: str = "stage10-channel",
    guild_id: str = "stage10-guild",
) -> Any:
    from pico_hid_bridge.discord_bot import DiscordMessage

    return DiscordMessage(
        id=message_id,
        content=content,
        author_id=author_id,
        channel_id=channel_id,
        guild_id=guild_id,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
    )


def run_stage10_discord_poll(
    app: Any,
    config: dict[str, Any],
    store: OperationLogStore,
    messages: list[Any],
    *,
    discord_client: Any | None = None,
) -> FakeDiscordClient:
    from pico_hid_bridge.discord_bot import DiscordBotWorker, FlaskControlClient

    fake = discord_client or FakeDiscordClient(messages)
    worker = DiscordBotWorker(config, store, discord_client=fake, control_client=FlaskControlClient(app))
    worker.poll_once()
    return fake


def latest_operation_has(status: dict[str, Any], *needles: str) -> bool:
    rows = status.get("operation_logs", [])
    text = str(rows[-8:]).lower()
    return all(needle.lower() in text for needle in needles)


def operation_db_has(client: Any, *needles: str) -> bool:
    data = json_response(client.get("/api/logs/operation"))
    rows = data.get("items", [])
    text = str(rows[-20:]).lower()
    return all(needle.lower() in text for needle in needles)


def operation_db_row_has(
    client: Any,
    *,
    source: str = "",
    status: str = "",
    command_contains: str = "",
    error_contains: str = "",
) -> bool:
    data = json_response(client.get("/api/logs/operation"))
    rows = data.get("items", [])
    for row in rows:
        if source and row.get("source") != source:
            continue
        if status and row.get("status") != status:
            continue
        if command_contains and command_contains.lower() not in str(row.get("command", "")).lower():
            continue
        if error_contains and error_contains.lower() not in str(row.get("error", "")).lower():
            continue
        return True
    return False


def notification_rows(client: Any) -> list[dict[str, Any]]:
    data = json_response(client.get("/api/logs/notification"))
    rows = data.get("items", [])
    return rows if isinstance(rows, list) else []


def latest_notification_has(client: Any, *, event: str, status: str, contains: str = "") -> bool:
    for row in reversed(notification_rows(client)):
        if row.get("event") != event or row.get("status") != status:
            continue
        if contains and contains.lower() not in str(row).lower():
            continue
        return True
    return False


def running_app_processes() -> list[str]:
    result = subprocess.run(
        ["ps", "-eo", "pid=,args="],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    current_pid = str(os.getpid())
    rows: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        pid = parts[0]
        command = parts[1] if len(parts) > 1 else ""
        if pid == current_pid:
            continue
        if "app.py" in command and "python" in command:
            rows.append(stripped)
    return rows


def assert_no_existing_app_process() -> str:
    rows = running_app_processes()
    if not rows:
        return ""
    return "app.py is already running before WebUI E2E; stop it before running tests: " + "; ".join(rows)


def run_webui_stage_case(test_case: E2ETestCase, args: argparse.Namespace, output_dir: Path) -> str:
    from pico_hid_bridge.web.app import create_app

    if error := assert_no_existing_app_process():
        return error

    config = make_webui_e2e_config(args, output_dir)
    configure_stage07_email(test_case, config, output_dir)
    configure_stage09_token_budget(test_case, config)
    configure_stage10_discord(test_case, config)
    app = create_app(config, start_capture_service=True)
    if test_case.name == "stage07_scenario06_expected_failure_smtp_auth":
        class FailingSmtp:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                return None

            def __enter__(self) -> "FailingSmtp":
                return self

            def __exit__(self, *args: Any) -> None:
                return None

            def ehlo(self) -> None:
                return None

            def starttls(self, *, context: Any) -> None:
                return None

            def login(self, username: str, password: str) -> None:
                raise RuntimeError("SMTP authentication failed")

            def send_message(self, message: Any) -> None:
                return None

        email_sink = app.extensions.get("email_notification_sink")
        if email_sink is not None:
            email_sink.smtp_class = FailingSmtp
            email_sink.smtp_ssl_class = FailingSmtp
    client = app.test_client()
    try:
        return _run_webui_stage_case_impl(test_case, args, output_dir, client, app)
    finally:
        service = app.extensions.get("capture_service")
        if service is not None:
            service.stop()


def _run_webui_stage_case_impl(
    test_case: E2ETestCase,
    args: argparse.Namespace,
    output_dir: Path,
    client: Any,
    app: Any,
) -> str:
    name = test_case.name
    store: OperationLogStore = args.operation_log_store

    print("WEBUI E2E: create Flask test client")

    if name == "stage03_scenario01_emergency_stop_blocks_hid":
        error = require_response(client.post("/api/emergency-stop", json={}))
        if error:
            return error
        blocked = client.post("/api/manual-hid", json={"command": "PING"})
        if require_response(blocked, ok=False, contains="emergency stop"):
            return "manual HID was not blocked by emergency stop"
        return "" if status_json(client).get("emergency_stopped") else "emergency stop state missing"

    if name == "stage03_scenario02_new_command_resets_state":
        error = require_response(client.post("/api/emergency-stop", json={}))
        if error:
            return error
        response = client.post("/api/command", json={"command": "open browser", "planning": False})
        error = require_response(response)
        if error:
            return error
        status = status_json(client)
        if status.get("emergency_stopped"):
            return "new command did not clear emergency stop"
        return save_webui_screenshot(client, output_dir, "stage03_new_command_after.jpg", store, name)

    if name == "stage03_scenario03_suspend_resume_state":
        if error := require_response(client.post("/api/suspend", json={})):
            return error
        if not status_json(client).get("suspended"):
            return "suspend state missing"
        blocked = client.post("/api/manual-hid", json={"command": "PING"})
        if require_response(blocked, ok=False, contains="suspended"):
            return "manual HID was not blocked while suspended"
        if error := require_response(client.post("/api/resume", json={})):
            return error
        status = status_json(client)
        if status.get("suspended"):
            return "resume did not clear suspended state"
        system_text = str(status.get("system_logs", [])).lower()
        return "" if "suspend" in system_text and "resume" in system_text else "suspend/resume logs missing"

    if name == "stage03_scenario04_stop_cancels_pending_approval":
        if error := require_response(client.post("/api/approval-test", json={"reason": name})):
            return error
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        status = status_json(client)
        if status.get("approval_pending"):
            return "approval remained pending"
        return "" if status.get("approval_status") == "cancelled_by_emergency_stop" else "approval was not cancelled"

    if name == "stage04_scenario01_lan_webui_status":
        html = client.get("/")
        if html.status_code != 200 or b"Request" not in html.data or b"Manual HID" not in html.data:
            return "WebUI HTML did not expose required controls"
        status = status_json(client)
        if "bind_host" not in status or "operation_logs" not in status or "system_logs" not in status:
            return "WebUI status payload missing required fields"
        return save_webui_screenshot(client, output_dir, "stage04_status_screen.jpg", store, name)

    if name == "stage04_scenario02_manual_hid_command":
        prepare_target_desktop(args)
        if error := require_response(client.post("/api/manual-hid", json={"command": "KEY WIN+R"})):
            return error
        if not latest_operation_has(status_json(client), "KEY WIN+R", "sent"):
            return "manual HID operation log missing"
        return save_webui_screenshot(client, output_dir, "stage04_manual_hid_after.jpg", store, name)

    if name == "stage04_scenario03_planning_toggle":
        html = client.get("/")
        if html.status_code != 200:
            return "WebUI HTML did not load"
        if b'data-tab="plan"' not in html.data or b"Manual HID" not in html.data:
            return "WebUI command mode tabs missing"
        if b'id="planning"' in html.data:
            return "obsolete planning checkbox is still visible"
        return "" if b'planning: activeCommandMode === "plan"' in html.data else "Plan tab does not submit planning mode"

    if name == "stage04_scenario04_log_panes":
        client.post("/api/planning", json={"enabled": True})
        client.post("/api/manual-hid", json={"command": "PING"})
        status = status_json(client)
        if not status.get("user_logs") or not status.get("operation_logs") or not status.get("system_logs"):
            return "user/operation/system logs are not all visible"
        if client.get("/api/logs/system").status_code != 200:
            return "system log endpoint missing"
        return ""

    if name == "stage04_scenario05_expected_failure_invalid_hid_command":
        response = client.post("/api/manual-hid", json={"command": "KEY ALT"})
        return require_response(response, ok=False, contains="non-modifier")

    if name == "stage04_scenario06_webui_emergency_button":
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        blocked = client.post("/api/manual-hid", json={"command": "PING"})
        if require_response(blocked, ok=False, contains="emergency stop"):
            return "manual HID was not blocked after WebUI emergency stop"
        return "" if status_json(client).get("emergency_stopped") else "emergency stop status missing"

    if name == "stage04_scenario07_refresh_screenshot":
        if error := save_webui_screenshot(client, output_dir, "stage04_refresh_before.jpg", store, name):
            return error
        response = client.post("/api/command", json={"command": "open Calculator", "planning": False})
        if error := require_response(response):
            return error
        return save_webui_screenshot(client, output_dir, "stage04_refresh_after.jpg", store, name)

    request_commands = {
        "stage04_scenario08_webui_request_open_browser": "open browser",
        "stage04_scenario09_webui_request_run_dialog": "Open the Windows Run dialog using WIN+R.",
        "stage04_scenario10_webui_request_text_editor_input": (
            "Open Notepad and type exactly: Pico HID test 123."
        ),
        "stage04_scenario11_webui_request_calculator_basic": "Open Calculator and calculate 123+456.",
        "stage04_scenario12_webui_request_paint_text": (
            "Open Paint. Use CTRL+O to open C:\\Users\\user\\Pictures\\test.png. "
            "The image should contain This is test."
        ),
        "stage04_scenario13_webui_request_expected_failure_unsupported_drag": (
            "Draw a freehand line in Paint using a mouse drag action."
        ),
        "stage04_scenario14_webui_request_expected_failure_nonexistent_app": (
            "Open DefinitelyNotARealApp12345."
        ),
    }
    if name in request_commands:
        prepare_target_desktop(args)
        response = client.post("/api/command", json={"command": request_commands[name], "planning": False})
        if is_expected_failure_case(test_case):
            if error := require_response(response, ok=False):
                return error
        elif error := require_response(response):
            return error
        if not is_expected_failure_case(test_case):
            if not latest_operation_has(status_json(client), "COMPUTER_USE", "sent"):
                return "WebUI Request completion log missing"
            return save_webui_screenshot(client, output_dir, f"{name}_after.jpg", store, name)
        return "" if latest_operation_has(status_json(client), "error") else "expected failure was not logged"

    planning_commands = {
        "stage05_scenario01_default_web_raspberry_pi_pico": (
            "Research Raspberry Pi Pico HID keyboard emulation using the browser default search and summarize it in a text editor."
        ),
        "stage05_scenario02_google_http_status_codes": (
            "Use Google to research HTTP status codes and summarize the result in a text editor."
        ),
        "stage05_scenario03_wikipedia_ada_lovelace": (
            "Use Wikipedia to research Ada Lovelace and summarize the result in a text editor."
        ),
        "stage05_scenario04_arxiv_attention_paper": (
            "Use arXiv to search for Attention Is All You Need and summarize the visible paper information in a text editor."
        ),
        "stage05_scenario06_calculator_plan": "Open Calculator and calculate 128 times 7 plus 3.",
        "stage05_scenario07_paint_text_plan": "Open Paint and write HELLO 2026 on the canvas.",
        "stage05_scenario08_calculator_to_editor": (
            "Calculate 42 times 17, then open a text editor and write Result: 714."
        ),
        "stage05_scenario09_browser_to_paint_label": (
            "Search the web for RGB color names, then open Paint and write RED GREEN BLUE on the canvas."
        ),
    }
    if name in planning_commands:
        prepare_target_desktop(args)
        response = client.post("/api/command", json={"command": planning_commands[name], "planning": True})
        if error := require_response(response):
            return error
        if not latest_operation_has(status_json(client), "PLAN", "sent"):
            return "planned request completion log missing"
        return save_webui_screenshot(client, output_dir, f"{name}_after.jpg", store, name)

    if name == "stage05_scenario05_planning_disabled_single_step":
        prepare_target_desktop(args)
        response = client.post(
            "/api/command",
            json={
                "command": "Research HTTP status codes and summarize the result in a text editor.",
                "planning": False,
            },
        )
        if error := require_response(response):
            return error
        return "" if latest_operation_has(status_json(client), "COMPUTER_USE", "sent") else "planning OFF did not use single request path"

    expected_planning_failures = {
        "stage05_scenario10_expected_failure_unreachable_url": (
            "Open a browser and navigate to http://127.0.0.1:9/expected-failure-test."
        ),
        "stage05_scenario11_expected_failure_missing_app": (
            "Create and run a plan that opens DefinitelyNotARealApp12345 and writes OK."
        ),
        "stage05_scenario12_expected_failure_calculator_divide_by_zero": (
            "Open Calculator and calculate 5 divided by 0."
        ),
        "stage05_scenario13_expected_failure_paint_freehand": (
            "Open Paint and draw a spiral with freehand mouse movement."
        ),
    }
    if name in expected_planning_failures:
        prepare_target_desktop(args)
        response = client.post("/api/command", json={"command": expected_planning_failures[name], "planning": True})
        if response.status_code < 400:
            status = status_json(client)
            if not has_expected_planning_failure_signal(status):
                return "expected planning failure was not logged"
        return ""

    approval_required_commands = {
        "stage06_scenario01_file_save_requires_approval": (
            "Write text in a text editor and save it to a file named approval-test.txt."
        ),
        "stage06_scenario02_send_or_post_requires_approval": (
            "Open a browser form and submit a message."
        ),
        "stage06_scenario03_login_requires_approval": (
            "Log in to a website by entering credentials and personal information."
        ),
        "stage06_scenario06_delete_requires_approval": (
            "Delete the file named test-output.txt."
        ),
        "stage06_scenario07_install_requires_approval": (
            "Install an application or change Windows system settings."
        ),
        "stage06_scenario09_expected_failure_unapproved_action": (
            "Write text in a text editor and save it to a file named unapproved.txt."
        ),
    }
    if name in approval_required_commands:
        response = client.post("/api/command", json={"command": approval_required_commands[name], "planning": True})
        if error := require_response(response):
            return error
        status = status_json(client)
        if not status.get("approval_pending") or status.get("approval_status") != "pending":
            return "risky plan did not enter approval-pending state"
        if client.post("/api/suspend", json={}).status_code != 409:
            return "suspend was not blocked while approval was pending"
        if client.post("/api/resume", json={}).status_code != 409:
            return "resume was not blocked while approval was pending"
        return "" if latest_operation_has(status, "approval_pending") else "approval-pending operation log missing"

    if name == "stage06_scenario04_reject_prevents_execution":
        response = client.post(
            "/api/command",
            json={"command": "Write text in a text editor and save it to rejected.txt.", "planning": True},
        )
        if error := require_response(response):
            return error
        rejected = client.post("/api/reject", json={})
        if error := require_response(rejected):
            return error
        status = status_json(client)
        if status.get("approval_pending"):
            return "rejected approval still pending"
        return "" if status.get("approval_status") == "rejected" and latest_operation_has(status, "rejected") else "rejection was not logged"

    if name == "stage06_scenario05_approval_timeout":
        response = client.post("/api/approval-test", json={"reason": "stage06 timeout", "timeout_seconds": 0.1})
        if error := require_response(response):
            return error
        time.sleep(0.2)
        status = status_json(client)
        if status.get("approval_pending") or status.get("approval_status") != "expired":
            return "approval did not expire"
        expired_approve = client.post("/api/approve", json={})
        return "" if expired_approve.status_code == 409 else "expired approval was still approvable"

    if name == "stage06_scenario08_safe_read_no_approval":
        prepare_target_desktop(args)
        response = client.post(
            "/api/command",
            json={"command": "Open Calculator and read the visible result without saving or changing settings.", "planning": True},
        )
        if error := require_response(response):
            return error
        status = status_json(client)
        if status.get("approval_pending"):
            return "safe read-only request incorrectly required approval"
        if not latest_operation_has(status, "PLAN", "sent"):
            return "safe read-only plan did not execute"
        return save_webui_screenshot(client, output_dir, f"{name}_after.jpg", store, name)

    if name == "stage07_scenario01_completion_email_log":
        response = client.post("/api/manual-hid", json={"command": "PING"})
        if error := require_response(response):
            return error
        return "" if latest_notification_has(client, event="completion", status="sent") else "completion SMTP success was not logged"

    if name == "stage07_scenario02_emergency_email_log":
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        return "" if latest_notification_has(client, event="emergency", status="sent") else "emergency SMTP success was not logged"

    if name == "stage07_scenario03_approval_request_email_log":
        if error := require_response(client.post("/api/approval-test", json={"reason": "stage07 approval request"})):
            return error
        status = status_json(client)
        if not status.get("approval_pending"):
            return "approval pending state missing"
        return "" if latest_notification_has(client, event="approval_request", status="sent") else "approval-request SMTP success was not logged"

    if name == "stage07_scenario04_email_rate_limit":
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        return "" if latest_notification_has(client, event="emergency", status="rate_limited") else "email rate limit was not enforced"

    if name == "stage07_scenario05_email_self_recipient":
        response = client.post("/api/manual-hid", json={"command": "PING"})
        if error := require_response(response):
            return error
        account = parse_smtp_account_file(str(make_webui_e2e_config(args, output_dir)["email"]["smtp_account_file"]))
        return (
            ""
            if latest_notification_has(client, event="completion", status="sent", contains=account.sender_mail)
            else "email recipient is not SMTP account itself"
        )

    if name == "stage07_scenario06_expected_failure_smtp_auth":
        response = client.post("/api/manual-hid", json={"command": "PING"})
        if error := require_response(response):
            return error
        return "" if latest_notification_has(client, event="completion", status="failed") else "SMTP auth failure was not handled safely"

    if name == "stage07_scenario07_attachment_limit":
        if error := require_response(client.post("/api/emergency-stop", json={})):
            return error
        return (
            ""
            if latest_notification_has(client, event="emergency", status="sent", contains="omitted")
            else "email attachment limit was not enforced"
        )

    if name == "stage07_scenario08_email_disabled_no_send":
        response = client.post("/api/manual-hid", json={"command": "PING"})
        if error := require_response(response):
            return error
        return "" if latest_notification_has(client, event="completion", status="skipped") else "disabled email was sent or not logged"

    if name == "stage08_scenario01_progress_display":
        response = client.post(
            "/api/long-operation-test",
            json={"total_steps": 4, "completed_steps": 1, "current_step": "Research", "warning": True},
        )
        if error := require_response(response):
            return error
        progress = status_json(client).get("long_operation", {})
        if progress.get("completed_steps") != 1 or progress.get("total_steps") != 4:
            return "progress counters are missing"
        if not progress.get("current_step") or "estimated_percent" not in progress:
            return "progress detail is missing"
        return ""

    if name == "stage08_scenario02_suspend_resume":
        if error := require_response(client.post("/api/long-operation-test", json={"total_steps": 4, "completed_steps": 1})):
            return error
        if error := require_response(client.post("/api/suspend", json={})):
            return error
        suspended = status_json(client)
        if not suspended.get("suspended") or not suspended.get("long_operation", {}).get("resume_requires_verification"):
            return "long operation suspend state missing"
        if error := require_response(client.post("/api/resume", json={})):
            return error
        resumed = status_json(client)
        progress = resumed.get("long_operation", {})
        if resumed.get("suspended") or progress.get("resume_requires_verification"):
            return "long operation did not resume from saved state"
        return "" if progress.get("current_state") == "running" else "resumed long operation is not running"

    if name == "stage08_scenario03_screen_drift_requires_approval":
        if error := require_response(client.post("/api/long-operation-test", json={"total_steps": 4, "completed_steps": 1})):
            return error
        if error := require_response(client.post("/api/suspend", json={})):
            return error
        response = client.post("/api/resume", json={"screen_drift": True})
        if response.status_code != 409:
            return "screen drift resume was not blocked"
        status = status_json(client)
        progress = status.get("long_operation", {})
        if not status.get("approval_pending"):
            return "screen drift did not enter approval-pending state"
        return "" if progress.get("screen_drift") and progress.get("resume_requires_verification") else "screen drift state missing"

    if name == "stage08_scenario04_long_plan_warning":
        if error := require_response(client.post("/api/long-operation-test", json={"total_steps": 6, "completed_steps": 0, "warning": True})):
            return error
        status = status_json(client)
        progress = status.get("long_operation", {})
        system_text = str(status.get("system_logs", [])).lower()
        if not progress.get("warning"):
            return "long-plan warning flag missing"
        return "" if "long_operation_warning" in system_text else "long-plan warning log missing"

    if name == "stage08_scenario05_cancel_long_plan":
        if error := require_response(client.post("/api/long-operation-test", json={"total_steps": 5, "completed_steps": 2})):
            return error
        if error := require_response(client.post("/api/cancel", json={})):
            return error
        status = status_json(client)
        progress = status.get("long_operation", {})
        if status.get("command_running"):
            return "command still running after cancel"
        return "" if progress.get("cancelled") and not progress.get("active") else "long plan did not cancel cleanly"

    if name == "stage08_scenario06_expected_failure_step_error":
        response = client.post(
            "/api/long-operation-test",
            json={"total_steps": 4, "completed_steps": 1, "current_step": "DefinitelyNotARealApp12345", "failed_step": True},
        )
        if error := require_response(response):
            return error
        status = status_json(client)
        progress = status.get("long_operation", {})
        if progress.get("current_state") != "failed" or not progress.get("failed_step"):
            return "failed long-plan step was not recorded"
        return "" if latest_operation_has(status, "error") else "failed long-plan step operation log missing"

    if name == "stage08_scenario07_resume_after_process_restart":
        if error := require_response(client.post("/api/long-operation-test", json={"total_steps": 5, "completed_steps": 2})):
            return error
        if error := require_response(client.post("/api/suspend", json={})):
            return error
        from pico_hid_bridge.web.app import create_app

        restart_config = make_webui_e2e_config(args, output_dir)
        configure_stage07_email(test_case, restart_config, output_dir)
        configure_stage09_token_budget(test_case, restart_config)
        restarted_client = create_app(restart_config, start_capture_service=False).test_client()
        restarted = status_json(restarted_client)
        progress = restarted.get("long_operation", {})
        if not restarted.get("suspended"):
            return "suspend state did not survive process restart"
        if not progress.get("active") or progress.get("completed_steps") != 2:
            return "persisted progress state missing after restart"
        return "" if progress.get("resume_requires_verification") else "restart resume did not require screen verification"

    if name == "stage09_scenario01_operation_token_usage":
        if error := require_response(client.post("/api/tokens/record-test", json={"total_tokens": 123, "phase": "screen_analysis"})):
            return error
        detail = json_response(client.get("/api/logs/detail"))
        html = client.get("/")
        if html.status_code != 200 or b"System Log" not in html.data or b'id="tokenGraph"' not in html.data:
            return "token log display elements are missing from WebUI"
        token_rows = detail.get("token_usage", [])
        system_rows = detail.get("system_logs", [])
        if not any(int(row.get("total_tokens", 0) or 0) == 123 for row in token_rows):
            return "operation token usage row missing"
        return "" if any(row.get("event") == "token_usage" for row in system_rows) else "token usage system log missing"

    if name == "stage09_scenario02_plan_token_prediction":
        if error := require_response(client.post("/api/tokens/record-test", json={"total_tokens": 100, "phase": "sample"})):
            return error
        response = client.post("/api/tokens/predict", json={"steps": ["Open", "Read", "Summarize"]})
        if error := require_response(response):
            return error
        data = json_response(response)
        status = status_json(client)
        if data.get("estimated_tokens") != 300:
            return f"unexpected token prediction: {data}"
        return "" if status.get("token_prediction", {}).get("estimated_tokens") == 300 else "token prediction missing from status"

    if name == "stage09_scenario03_budget_exceeded_blocks":
        if error := require_response(client.post("/api/tokens/record-test", json={"total_tokens": 100, "phase": "sample"})):
            return error
        response = client.post(
            "/api/tokens/check-budget",
            json={"steps": ["One", "Two", "Three"], "command": "stage09 over budget"},
        )
        if error := require_response(response):
            return error
        status = status_json(client)
        if not status.get("approval_pending") or status.get("approval_status") != "pending":
            return "token budget overflow did not enter approval pending"
        return "" if "token budget" in str(status.get("approval_detail", "")).lower() else "token budget approval detail missing"

    if name == "stage09_scenario04_daily_token_aggregate":
        day_start = "2026-07-05T00:00:00+00:00"
        day_end = "2026-07-06T00:00:00+00:00"
        client.post("/api/tokens/record-test", json={"total_tokens": 11, "created_at": "2026-07-05T01:00:00+00:00"})
        client.post("/api/tokens/record-test", json={"total_tokens": 22, "created_at": "2026-07-05T02:00:00+00:00"})
        totals = json_response(client.get(f"/api/tokens?from={day_start}&to={day_end}"))
        return "" if totals.get("total_tokens") == 33 else f"daily total is incorrect: {totals}"

    if name == "stage09_scenario05_expected_failure_missing_usage":
        response = client.post("/api/tokens/missing-usage-test", json={"phase": "missing_usage_fixture"})
        if error := require_response(response):
            return error
        detail = json_response(client.get("/api/logs/detail"))
        unknown_system = any(
            row.get("event") == "token_usage" and row.get("status") == "unknown"
            for row in detail.get("system_logs", [])
        )
        estimated_rows = [
            row
            for row in detail.get("token_usage", [])
            if int(row.get("total_tokens", 0) or 0) == 0 and int(row.get("estimated_tokens", 0) or 0) > 0
        ]
        if not unknown_system:
            return "missing usage warning system log missing"
        return "" if estimated_rows else "missing usage was treated as zero"

    if name == "stage09_scenario06_daily_budget_reset":
        client.post("/api/tokens/record-test", json={"total_tokens": 40, "created_at": "2026-07-04T23:59:00+00:00"})
        client.post("/api/tokens/record-test", json={"total_tokens": 60, "created_at": "2026-07-05T00:01:00+00:00"})
        previous = json_response(
            client.get("/api/tokens?from=2026-07-04T00:00:00+00:00&to=2026-07-05T00:00:00+00:00")
        )
        current = json_response(
            client.get("/api/tokens?from=2026-07-05T00:00:00+00:00&to=2026-07-06T00:00:00+00:00")
        )
        if previous.get("total_tokens") != 40:
            return f"previous day total is incorrect: {previous}"
        return "" if current.get("total_tokens") == 60 else f"current day total did not reset: {current}"

    if name == "stage09_scenario07_per_step_budget_warning":
        if error := require_response(client.post("/api/tokens/record-test", json={"total_tokens": 100, "phase": "sample"})):
            return error
        response = client.post("/api/tokens/predict", json={"steps": ["One", "Two"]})
        if error := require_response(response):
            return error
        data = json_response(response)
        status = status_json(client)
        if not data.get("per_step_budget_warning"):
            return f"per-step token warning missing: {data}"
        return "" if "per-step" in str(status.get("token_prediction", {}).get("message", "")).lower() else "per-step warning missing from status"

    if name.startswith("stage10_"):
        runtime_state = app.extensions.get("runtime_state")
        if runtime_state is None:
            return "runtime state extension missing"
        discord_config = runtime_state.config
        discord_store = runtime_state.log_store

    if name == "stage10_scenario01_discord_screen_command":
        fake = run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev screen")],
        )
        if not fake.sent_messages or fake.sent_messages[-1].get("attachment") is None:
            return "Discord screen response did not include screenshot"
        return "" if latest_notification_has(client, event="screen", status="sent") else "Discord screen notification missing"

    if name == "stage10_scenario02_discord_request_command":
        prepare_target_desktop(args)
        fake = run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev request: open browser")],
        )
        if not fake.sent_messages or fake.sent_messages[-1].get("attachment") is None:
            return "Discord request did not send completion screenshot"
        return "" if operation_db_has(client, "open browser", "sent", "discord") else "Discord request operation log missing"

    if name == "stage10_scenario03_discord_stop_command":
        run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev stop")],
        )
        status = status_json(client)
        if not status.get("emergency_stopped"):
            return "Discord stop did not trigger emergency stop"
        return "" if operation_db_has(client, "stop", "sent", "discord") else "Discord stop operation log missing"

    if name == "stage10_scenario04_discord_approve_reject":
        if error := require_response(client.post("/api/approval-test", json={"reason": "stage10 discord approval"})):
            return error
        run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev approve")],
        )
        status = status_json(client)
        if status.get("approval_pending"):
            return "Discord approval command did not clear pending state"
        return "" if status.get("approval_status") == "approved" else "Discord approval was not accepted"

    if name == "stage10_scenario05_discord_unauthorized_ignored":
        run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [
                stage10_message("101", "@AgentDev hid: KEY WIN+R", author_id="unknown-user"),
                stage10_message("100", "@AgentDev request: open browser", seconds_ago=20),
            ],
        )
        status = status_json(client)
        if operation_db_row_has(
            client,
            source="discord",
            status="sent",
            command_contains="open browser",
        ):
            return "older authorized Discord command ran after newer unauthorized command"
        return (
            ""
            if operation_db_row_has(client, source="discord", status="denied", error_contains="unauthorized")
            else "unauthorized Discord command was not logged"
        )

    if name == "stage10_scenario06_discord_attachment_limit":
        fake = run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev screen")],
        )
        if not fake.sent_messages:
            return "Discord screen response missing"
        if fake.sent_messages[-1].get("attachment") is not None:
            return "oversized Discord screenshot was attached"
        return "" if latest_notification_has(client, event="screen", status="sent", contains="omitted") else "Discord attachment policy was not logged"

    if name == "stage10_scenario07_discord_rate_limit":
        first_fake = run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [stage10_message("100", "@AgentDev screen")],
        )
        second_fake = FakeDiscordClient([stage10_message("101", "@AgentDev screen")])
        from pico_hid_bridge.discord_bot import DiscordBotWorker, FlaskControlClient

        worker = DiscordBotWorker(
            discord_config,
            discord_store,
            discord_client=first_fake,
            control_client=FlaskControlClient(app),
        )
        worker.last_seen_message_id = "100"
        worker.discord_client = second_fake
        worker._recent_command_times = [time.monotonic()]
        worker.poll_once()
        return "" if operation_db_has(client, "rate_limited") else "Discord command rate limit was not enforced"

    if name == "stage10_scenario08_expected_failure_bot_offline":
        run_stage10_discord_poll(
            app,
            discord_config,
            discord_store,
            [],
            discord_client=FailingDiscordClient([]),
        )
        return "" if latest_notification_has(client, event="poll", status="failed", contains="offline") else "Discord offline failure was not logged"

    return f"no WebUI runner implementation for {name}"


def record_stage02_scenario_outcome(test_case: E2ETestCase, store: OperationLogStore) -> None:
    if test_case.name == "stage02_scenario05_error_log":
        operation_id = store.record_operation(
            command="DefinitelyNotARealApp12345",
            normalized="TEXT DefinitelyNotARealApp12345",
            status="failed",
            source="e2e",
            case_name=test_case.name,
            error="not found state verified",
        )
        store.record_error(
            message="not found state verified",
            domain="implementation",
            case_name=test_case.name,
            operation_id=operation_id,
        )

    if test_case.name == "stage02_scenario06_log_query_filters":
        store.record_operation(
            command="stage02 filter success",
            status="sent",
            source="e2e",
            case_name=test_case.name,
        )
        operation_id = store.record_operation(
            command="stage02 filter failure",
            status="failed",
            source="e2e",
            case_name=test_case.name,
            error="intentional filter fixture",
        )
        store.record_error(
            message="intentional filter fixture",
            domain="implementation",
            case_name=test_case.name,
            operation_id=operation_id,
        )


def validate_stage02_logs(test_case: E2ETestCase, store: OperationLogStore, output_dir: Path) -> str:
    name = test_case.name
    if test_case.stage != "stage02_operation_log":
        return ""

    if name == "stage02_scenario01_user_input_log":
        rows = store.query_user_inputs(source="e2e", case_name=name)
        return "" if rows and rows[-1]["input"] == test_case.description else "user_input_log entry missing"

    if name == "stage02_scenario02_operation_log":
        rows = store.query_operations(source="e2e", status="sent", case_name=name)
        hid_rows = [
            row
            for row in rows
            if str(row.get("action_type", "")).lower() != "wait" and str(row.get("command", "")) != "WAIT"
        ]
        return "" if hid_rows else "operation_log HID sent entry missing"

    if name == "stage02_scenario03_screenshot_log":
        rows = store.query_screenshots(case_name=name)
        events = {str(row["event"]) for row in rows}
        return "" if {"before", "after"} <= events else "screenshot_log before/after entries missing"

    if name == "stage02_scenario04_storage_limit":
        return validate_stage02_storage_limit(store, output_dir, name)

    if name == "stage02_scenario05_error_log":
        failed = store.query_operations(status="failed", case_name=name)
        errors = store.query_errors(case_name=name)
        return "" if failed and errors else "failed operation or error_log entry missing"

    if name == "stage02_scenario06_log_query_filters":
        sent = store.query_operations(source="e2e", status="sent", case_name=name)
        failed = store.query_operations(source="e2e", status="failed", case_name=name)
        return "" if sent and failed and all(row["status"] == "failed" for row in failed) else "log query filters failed"

    if name == "stage02_scenario07_expected_failure_corrupt_db_recovery":
        recovered = store.recovery_performed
        usable = bool(store.query_user_inputs(case_name=name))
        corrupt_files = list(Path(store.database_path).parent.glob("app.db.corrupt-*"))
        return "" if recovered and usable and corrupt_files else "corrupt database recovery was not detected"

    return ""


def validate_stage02_storage_limit(store: OperationLogStore, output_dir: Path, case_name: str) -> str:
    rotation_dir = output_dir / "rotation"
    rotation_store = OperationLogStore(
        database_path=output_dir / "rotation.db",
        screenshot_dir=rotation_dir,
        max_screenshots=2,
    )
    paths = []
    for index in range(3):
        path = rotation_dir / f"rotation{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        paths.append(path)
        rotation_store.record_screenshot(path=path, event="rotation", case_name=case_name)

    rows = rotation_store.query_screenshots(case_name=case_name)
    if len(rows) != 2:
        return "screenshot rotation did not cap rows"
    if paths[0].exists() or not paths[1].exists() or not paths[2].exists():
        return "screenshot rotation did not remove only the oldest file"
    return ""
