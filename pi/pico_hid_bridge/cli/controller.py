#!/usr/bin/env python3
"""Capture one frame and ask OpenAI Computer Use for the next UI action."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Any

from openai import OpenAI

from pico_hid_bridge.actions import execute_supported_action
from pico_hid_bridge.capture import (
    DEFAULT_DEVICE,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_READY_TIMEOUT,
    capture_frame,
    encode_png,
    save_png,
)
from pico_hid_bridge.computer_use import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    action_type,
    attr,
    create_initial_response,
    describe_action,
    find_computer_call,
    send_screenshot_response,
)
from pico_hid_bridge.config import load_config
from pico_hid_bridge.hid import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_TIMEOUT
from pico_hid_bridge.paths import PI_DIR
from pico_hid_bridge.planning import PlanningService


DEFAULT_OUTPUT_DIR = PI_DIR / "captures"
DEFAULT_INTER_ACTION_DELAY = 0.25
DEFAULT_TYPE_ACTION_DELAY_PER_CHAR = 0.08
DEFAULT_POST_ACTION_WAIT = 2.0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "task",
        nargs="*",
        default=["Describe the screen and suggest one safe next action."],
        help="Computer Use instruction. Dry-run is the default.",
    )
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--fps", type=int, default=0)
    parser.add_argument("--warmup-frames", type=int, default=60)
    parser.add_argument("--min-brightness", type=float, default=DEFAULT_MIN_BRIGHTNESS)
    parser.add_argument("--ready-timeout", type=float, default=DEFAULT_READY_TIMEOUT)
    parser.add_argument("--save-screenshot", type=Path)
    parser.add_argument("--capture-only", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--inter-action-delay", type=float, default=DEFAULT_INTER_ACTION_DELAY)
    parser.add_argument("--type-action-delay-per-char", type=float, default=DEFAULT_TYPE_ACTION_DELAY_PER_CHAR)
    parser.add_argument("--post-action-wait", type=float, default=DEFAULT_POST_ACTION_WAIT)
    parser.add_argument("--execute", action="store_true", help="Send supported actions to Pico.")
    parser.add_argument("--config", type=Path, help="TOML config file for Computer Use prompt settings.")
    parser.add_argument("--computer-prompt", help="Override the Computer Use system prompt.")
    parser.add_argument("--planning", action="store_true", help="Create a plan before executing the task.")
    parser.add_argument("--approve-risk", action="store_true", help="Approve a high-risk plan for CLI execution.")
    return parser.parse_args(argv)


def capture_png_base64(args: argparse.Namespace) -> str:
    frame = capture_frame(
        args.device,
        args.width,
        args.height,
        args.fps,
        args.warmup_frames,
        args.min_brightness,
        args.ready_timeout,
    )
    png = encode_png(frame)
    if args.save_screenshot is not None:
        save_png(args.save_screenshot, png)
        print(f"saved screenshot sent to API: {args.save_screenshot}")
    import base64

    return base64.b64encode(png).decode("ascii")


def print_frame_info(frame: Any) -> None:
    height, width = frame.shape[:2]
    print(f"captured: {width}x{height}, mean_brightness={frame.mean():.1f}")


def action_delay_seconds(action: Any, args: argparse.Namespace) -> float:
    base_delay = max(0.0, getattr(args, "inter_action_delay", DEFAULT_INTER_ACTION_DELAY))
    if action_type(action) != "type":
        return base_delay

    text = str(attr(action, "text", ""))
    per_char = max(0.0, getattr(args, "type_action_delay_per_char", DEFAULT_TYPE_ACTION_DELAY_PER_CHAR))
    return max(base_delay, len(text) * per_char)


def step_argv_from_args(args: argparse.Namespace, instruction: str) -> list[str]:
    argv: list[str] = []
    if args.execute:
        argv.append("--execute")
    if args.config is not None:
        argv.extend(["--config", str(args.config)])
    if args.computer_prompt:
        argv.extend(["--computer-prompt", args.computer_prompt])
    argv.extend(["--device", str(args.device)])
    if args.width:
        argv.extend(["--width", str(args.width)])
    if args.height:
        argv.extend(["--height", str(args.height)])
    if args.fps:
        argv.extend(["--fps", str(args.fps)])
    argv.extend(
        [
            "--warmup-frames",
            str(args.warmup_frames),
            "--min-brightness",
            str(args.min_brightness),
            "--ready-timeout",
            str(args.ready_timeout),
            "--model",
            str(args.model),
            "--api-key-env",
            str(args.api_key_env),
            "--max-steps",
            str(args.max_steps),
            "--port",
            str(args.port),
            "--baudrate",
            str(args.baudrate),
            "--timeout",
            str(args.timeout),
            "--inter-action-delay",
            str(args.inter_action_delay),
            "--type-action-delay-per-char",
            str(args.type_action_delay_per_char),
            "--post-action-wait",
            str(args.post_action_wait),
            instruction,
        ]
    )
    return argv


def run_planned_cli(argv: list[str]) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    task = " ".join(args.task)
    try:
        plan = PlanningService.from_config(config).create_plan(task)
    except Exception as exc:
        print(f"planning failed: {exc}", file=sys.stderr)
        return 1

    approval_required = plan.requires_approval or plan.risk_level.lower() == "high"
    if approval_required and not args.approve_risk:
        print("approval required for high-risk plan; rerun with --approve-risk to execute", file=sys.stderr)
        return 3

    for index, step in enumerate(plan.steps, start=1):
        print(f"plan step {index}/{len(plan.steps)}: {step.title}")
        result = main(step_argv_from_args(args, step.instruction))
        if result != 0:
            return result
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.planning:
        return run_planned_cli(argv)
    config = load_config(args.config)
    openai_cfg = config.get("openai", {})
    computer_prompt = args.computer_prompt or str(openai_cfg.get("computer_prompt", "")).strip() or None
    task = " ".join(args.task)

    try:
        if args.capture_only:
            frame = capture_frame(
                args.device,
                args.width,
                args.height,
                args.fps,
                args.warmup_frames,
                args.min_brightness,
                args.ready_timeout,
            )
            png = encode_png(frame)
            output_path = args.save_screenshot or DEFAULT_OUTPUT_DIR / "controller_check.png"
            save_png(output_path, png)
            print_frame_info(frame)
            print(f"saved: {output_path}")
            return 0

        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            print(f"missing environment variable: {args.api_key_env}", file=sys.stderr)
            return 2

        client = OpenAI(api_key=api_key)
        response = create_initial_response(
            client,
            model=args.model,
            task=task,
            args=args,
            prompt=computer_prompt,
        )
    except Exception as exc:
        print(f"controller failed: {exc}", file=sys.stderr)
        return 1

    for _ in range(max(1, args.max_steps)):
        computer_call = find_computer_call(response)
        if computer_call is None:
            output_text = attr(response, "output_text", "")
            if output_text:
                print(output_text)
            else:
                print("no computer action returned")
            return 0

        actions = attr(computer_call, "actions", []) or []
        for action in actions:
            print(f"action: {describe_action(action)}")

        if not actions:
            print("no action in computer_call")
            return 0

        needs_only_screenshot = all(action_type(action) == "screenshot" for action in actions)
        if not args.execute and not needs_only_screenshot:
            print("dry-run: add --execute to send supported actions to Pico")
            return 0

        if args.execute:
            executed = 0
            for action in actions:
                if action_type(action) == "screenshot":
                    continue
                try:
                    if execute_supported_action(action, args):
                        print("executed")
                        executed += 1
                        time.sleep(action_delay_seconds(action, args))
                except Exception as exc:
                    print(f"execute failed: {exc}", file=sys.stderr)
                    return 1
            if executed:
                time.sleep(max(0.0, args.post_action_wait))

        try:
            response = send_screenshot_response(
                client,
                model=args.model,
                args=args,
                response=response,
                call_id=attr(computer_call, "call_id"),
            )
        except Exception as exc:
            print(f"screenshot response failed: {exc}", file=sys.stderr)
            return 1

    print("stopped: max steps reached")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
