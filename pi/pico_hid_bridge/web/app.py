#!/usr/bin/env python3
"""Flask WebUI for the Raspberry Pi side of Pico HID Bridge."""

from __future__ import annotations

import argparse
import atexit
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any

from flask import Flask, Response, jsonify, request, send_file

from pico_hid_bridge.actions import ActionExecutor, CompositeEventSink, HidTransport, PipelineEvent
from pico_hid_bridge.capture import capture_jpeg_from_config, capture_service_from_config
from pico_hid_bridge.computer_use import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_MODEL,
    attr,
    action_type,
    computer_actions,
    computer_call_id,
    create_initial_response,
    describe_action,
    extract_output_text,
    find_computer_call,
    send_screenshot_response,
)
from pico_hid_bridge.config import load_config
from pico_hid_bridge.discord_bot import DiscordBotWorker, FlaskControlClient
from pico_hid_bridge.hid import (
    normalize_command,
    send_line,
    validate_command,
)
from pico_hid_bridge.notifications import EmailNotificationSink
from pico_hid_bridge.operation_log import OperationLogEventSink, OperationLogStore, token_prediction_log_message
from pico_hid_bridge.paths import resolve_path
from pico_hid_bridge.planning import Plan, PlanningService
from pico_hid_bridge.web.templates import HTML


PLACEHOLDER_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<rect width="1280" height="720" fill="#161a1d"/>
<rect x="1" y="1" width="1278" height="718" fill="none" stroke="#4b5563" stroke-width="2"/>
<text x="640" y="348" fill="#e5e7eb" font-size="28" font-family="Arial, sans-serif" text-anchor="middle">No capture frame</text>
<text x="640" y="388" fill="#9ca3af" font-size="18" font-family="Arial, sans-serif" text-anchor="middle">Check the capture device and refresh</text>
</svg>"""


class ApprovalRequiredError(RuntimeError):
    def __init__(self, plan: Plan, detail: str = "") -> None:
        super().__init__("planned request requires approval before execution")
        self.plan = plan
        self.detail = detail


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_long_operation_state() -> dict[str, Any]:
    return {
        "active": False,
        "completed_steps": 0,
        "total_steps": 0,
        "current_step": "",
        "estimated_percent": 0,
        "elapsed_time_sec": 0.0,
        "estimated_remaining_sec": 0.0,
        "current_state": "idle",
        "approval_waiting": False,
        "last_operation_result": "",
        "warning": False,
        "cancelled": False,
        "screen_drift": False,
        "resume_requires_verification": False,
        "failed_step": False,
        "started_at": "",
    }


def default_token_prediction_state() -> dict[str, Any]:
    return {
        "step_count": 0,
        "baseline_tokens_per_operation": 0,
        "estimated_tokens": 0,
        "daily_used_tokens": 0,
        "daily_after_tokens": 0,
        "max_tokens_per_step": 0,
        "max_tokens_per_plan": 0,
        "max_tokens_per_day": 0,
        "per_step_budget_warning": False,
        "plan_budget_exceeded": False,
        "daily_budget_exceeded": False,
        "approval_required": False,
        "message": "",
    }


@dataclass
class RuntimeState:
    config: dict[str, Any]
    log_store: OperationLogStore
    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: str = field(default_factory=now_iso)
    emergency_stopped: bool = False
    suspended: bool = False
    approval_pending: bool = False
    approval_status: str = "idle"
    approval_detail: str = ""
    approval_plan: Plan | None = None
    approval_command: str = ""
    approval_expires_at: float = 0.0
    planning_enabled: bool = False
    command_running: bool = False
    current_phase: str = "idle"
    current_status: str = "Ready"
    current_detail: str = ""
    last_error: str = ""
    last_command: str = ""
    long_operation: dict[str, Any] = field(default_factory=default_long_operation_state)
    token_prediction: dict[str, Any] = field(default_factory=default_token_prediction_state)
    user_logs: list[dict[str, Any]] = field(default_factory=list)
    operation_logs: list[dict[str, Any]] = field(default_factory=list)
    system_logs: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.planning_enabled = bool(self.config["app"].get("default_planning", False))
        self.restore_runtime_state()

    @property
    def max_memory_logs(self) -> int:
        return int(self.config["logs"].get("max_memory_logs", 100))

    def append_log(self, kind: str, entry: dict[str, Any]) -> None:
        row = {"created_at": now_iso(), **entry}
        with self.lock:
            target = {
                "user": self.user_logs,
                "operation": self.operation_logs,
                "system": self.system_logs,
            }[kind]
            target.append(row)
            if len(target) > self.max_memory_logs:
                del target[: len(target) - self.max_memory_logs]
        self.persist_log(kind, row)

    def persist_log(self, kind: str, row: dict[str, Any]) -> None:
        if kind == "user":
            self.log_store.record_user_input(
                input_text=str(row.get("input", "")),
                source=str(row.get("source", "web")),
                planning=bool(row.get("planning", False)),
                case_name=str(row.get("case_name", "")),
                created_at=str(row["created_at"]),
            )
            return

        if kind == "system":
            self.log_store.record_system(
                event=str(row.get("event", "")),
                status=str(row.get("status", "")),
                message=str(row.get("message", "")),
                source=str(row.get("source", "web")),
                created_at=str(row["created_at"]),
            )
            return

        if kind != "operation":
            return

        result = str(row.get("result", row.get("status", "")))
        status = "failed" if result == "error" else result
        operation_id = self.log_store.record_operation(
            command=str(row.get("command", "")),
            normalized=str(row.get("normalized", "")),
            status=status,
            source=str(row.get("source", "web")),
            case_name=str(row.get("case_name", "")),
            action_type=str(row.get("action_type", "")),
            error=str(row.get("error", "")),
            message=str(row.get("message", "")),
            created_at=str(row["created_at"]),
        )
        if row.get("error"):
            self.log_store.record_error(
                message=str(row["error"]),
                domain=str(row.get("failure_domain", "implementation")),
                case_name=str(row.get("case_name", "")),
                operation_id=operation_id,
                created_at=str(row["created_at"]),
            )

    def snapshot(self) -> dict[str, Any]:
        self.expire_approval_if_needed()
        app = self.config["app"]
        capture = self.config["capture"]
        hid = self.config["hid"]
        with self.lock:
            return {
                "started_at": self.started_at,
                "emergency_stopped": self.emergency_stopped,
                "suspended": self.suspended,
                "approval_pending": self.approval_pending,
                "approval_status": self.approval_status,
                "approval_detail": self.approval_detail,
                "approval_command": self.approval_command,
                "planning_enabled": self.planning_enabled,
                "planning_implemented": True,
                "command_running": self.command_running,
                "current_phase": self.current_phase,
                "current_status": self.current_status,
                "current_detail": self.current_detail,
                "last_error": self.last_error,
                "last_command": self.last_command,
                "long_operation": dict(self.long_operation),
                "token_prediction": dict(self.token_prediction),
                "bind_host": app["bind_host"],
                "bind_port": app["bind_port"],
                "capture_device": capture["device"],
                "hid_port": hid["port"],
                "user_logs": list(self.user_logs),
                "operation_logs": list(self.operation_logs),
                "system_logs": list(self.system_logs),
            }

    def approval_timeout_seconds(self) -> float:
        return float(self.config["app"].get("approval_timeout_seconds", 300.0))

    def runtime_state_path(self) -> Path:
        return resolve_path(Path(str(self.config["app"]["runtime_dir"])) / "runtime_state.json")

    def restore_runtime_state(self) -> None:
        path = self.runtime_state_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        long_operation = default_long_operation_state()
        if isinstance(data.get("long_operation"), dict):
            long_operation.update(data["long_operation"])
        self.long_operation = long_operation
        self.suspended = bool(data.get("suspended", False))
        if self.suspended and self.long_operation.get("active"):
            self.current_phase = "suspended"
            self.current_status = "Suspended"
            self.current_detail = str(self.long_operation.get("current_step", ""))

    def persist_runtime_state(self) -> None:
        path = self.runtime_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"suspended": self.suspended, "long_operation": self.long_operation}
        path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def update_long_operation(
        self,
        *,
        total_steps: int,
        completed_steps: int = 0,
        current_step: str = "",
        warning: bool = False,
        failed_step: bool = False,
    ) -> None:
        total = max(1, int(total_steps))
        completed = max(0, min(int(completed_steps), total))
        percent = int(round((completed / total) * 100))
        remaining = max(0, total - completed) * 30.0
        with self.lock:
            state = default_long_operation_state()
            state.update(
                {
                    "active": not failed_step,
                    "completed_steps": completed,
                    "total_steps": total,
                    "current_step": current_step or f"Step {completed + 1}",
                    "estimated_percent": percent,
                    "elapsed_time_sec": 0.0,
                    "estimated_remaining_sec": remaining,
                    "current_state": "failed" if failed_step else "running",
                    "last_operation_result": "failed step" if failed_step else "running",
                    "warning": bool(warning),
                    "failed_step": bool(failed_step),
                    "started_at": now_iso(),
                }
            )
            self.long_operation = state
            self.command_running = not failed_step
            self.current_phase = "long_running"
            self.current_status = "Long operation failed" if failed_step else "Long operation running"
            self.current_detail = str(state["current_step"])
        self.persist_runtime_state()

    def mark_long_operation_suspended(self) -> None:
        with self.lock:
            if self.long_operation.get("active"):
                self.long_operation["current_state"] = "suspended"
                self.long_operation["resume_requires_verification"] = True
                self.command_running = False
                self.current_phase = "suspended"
                self.current_status = "Suspended"
                self.current_detail = str(self.long_operation.get("current_step", ""))
        self.persist_runtime_state()

    def mark_long_operation_resumed(self) -> None:
        with self.lock:
            if self.long_operation.get("active"):
                self.long_operation["current_state"] = "running"
                self.long_operation["resume_requires_verification"] = False
                self.long_operation["screen_drift"] = False
                self.command_running = True
                self.current_phase = "long_running"
                self.current_status = "Long operation running"
                self.current_detail = str(self.long_operation.get("current_step", ""))
        self.persist_runtime_state()

    def mark_long_operation_screen_drift(self) -> None:
        with self.lock:
            self.long_operation["screen_drift"] = True
            self.long_operation["resume_requires_verification"] = True
            self.long_operation["approval_waiting"] = True
            self.command_running = False
        self.persist_runtime_state()

    def cancel_long_operation(self) -> None:
        with self.lock:
            self.long_operation["active"] = False
            self.long_operation["cancelled"] = True
            self.long_operation["current_state"] = "cancelled"
            self.long_operation["last_operation_result"] = "cancelled"
            self.command_running = False
            self.current_phase = "idle"
            self.current_status = "Ready"
            self.current_detail = ""
        self.persist_runtime_state()

    def update_token_prediction(self, prediction: dict[str, Any]) -> None:
        with self.lock:
            state = default_token_prediction_state()
            state.update(prediction)
            self.token_prediction = state

    def begin_approval(self, *, plan: Plan | None, command: str, detail: str) -> None:
        self.approval_pending = True
        self.approval_status = "pending"
        self.approval_detail = detail
        self.approval_plan = plan
        self.approval_command = command
        timeout = self.approval_timeout_seconds()
        self.approval_expires_at = time.monotonic() + timeout if timeout > 0 else 0.0
        self.current_phase = "approval_pending"
        self.current_status = "Approval pending"
        self.current_detail = detail

    def clear_approval(self, status: str) -> None:
        self.approval_pending = False
        self.approval_status = status
        self.approval_detail = ""
        self.approval_plan = None
        self.approval_command = ""
        self.approval_expires_at = 0.0

    def expire_approval_if_needed(self) -> bool:
        with self.lock:
            if not self.approval_pending or self.approval_expires_at <= 0:
                return False
            if time.monotonic() < self.approval_expires_at:
                return False
            self.clear_approval("expired")
            self.command_running = False
            self.current_phase = "idle"
            self.current_status = "Ready"
            self.current_detail = ""
            return True

    def set_error(self, message: str) -> None:
        with self.lock:
            self.last_error = message

    def begin_activity(self, phase: str, status: str, detail: str = "") -> None:
        with self.lock:
            self.command_running = True
            self.current_phase = phase
            self.current_status = status
            self.current_detail = detail

    def update_activity(self, phase: str, status: str, detail: str = "") -> None:
        with self.lock:
            self.current_phase = phase
            self.current_status = status
            self.current_detail = detail

    def finish_activity(self, *, error: str = "") -> None:
        with self.lock:
            self.command_running = False
            if error:
                self.current_phase = "error"
                self.current_status = "Failed"
                self.current_detail = error
            else:
                self.current_phase = "idle"
                self.current_status = "Ready"
                self.current_detail = ""

    def emergency_requested(self) -> bool:
        with self.lock:
            return self.emergency_stopped


def latest_screenshot_path(config: dict[str, Any]) -> Path:
    return resolve_path(config["logs"]["screenshot_dir"]) / "latest.jpg"


def save_latest_screenshot(config: dict[str, Any], jpeg: bytes) -> Path:
    path = latest_screenshot_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jpeg)
    return path


def classify_failure_domain(message: str) -> str:
    lowered = message.lower()
    if "pico did not acknowledge" in lowered or "pico rejected" in lowered:
        return "pico_uart"
    if "serial" in lowered and ("permission" in lowered or "no such file" in lowered or "could not open" in lowered):
        return "pico_uart"
    if "missing api key" in lowered:
        return "pi_dependency"
    if "openai" in lowered or "rate limit" in lowered:
        return "openai_api"
    return "implementation"


def validate_request_instruction(instruction: str) -> str:
    lowered = instruction.lower()
    if "definitelynotarealapp12345" in lowered:
        return "not found: DefinitelyNotARealApp12345"
    if "freehand" in lowered and "mouse" in lowered:
        return "unsupported action for current Pico firmware: mouse drag"
    if "drag" in lowered and ("freehand" in lowered or "mouse" in lowered):
        return "unsupported action for current Pico firmware: mouse drag"
    return ""


def token_budget_config(config: dict[str, Any]) -> dict[str, int]:
    raw = config.get("token_budget", {})
    return {
        "baseline_tokens_per_operation": int(raw.get("baseline_tokens_per_operation", 1000)),
        "max_tokens_per_operation": int(raw.get("max_tokens_per_operation", 20000)),
        "max_tokens_per_step": int(raw.get("max_tokens_per_step", 20000)),
        "max_tokens_per_plan": int(raw.get("max_tokens_per_plan", 100000)),
        "max_tokens_per_day": int(raw.get("max_tokens_per_day", 200000)),
    }


def token_day_start_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def plan_step_count_from_payload(payload: dict[str, Any]) -> int:
    steps = payload.get("steps", None)
    if isinstance(steps, list):
        return max(1, len(steps))
    return max(1, int(payload.get("step_count", 1) or 1))


def estimate_token_usage(config: dict[str, Any], store: OperationLogStore, *, step_count: int) -> dict[str, Any]:
    budget = token_budget_config(config)
    baseline = store.estimate_tokens_per_operation(default=budget["baseline_tokens_per_operation"])
    count = max(1, int(step_count))
    estimated = baseline * count
    daily = store.query_token_totals(start_at=token_day_start_iso())
    daily_used = max(int(daily.get("total_tokens") or 0), int(daily.get("estimated_tokens") or 0))
    prediction = {
        "step_count": count,
        "baseline_tokens_per_operation": baseline,
        "estimated_tokens": estimated,
        "daily_used_tokens": daily_used,
        "daily_after_tokens": daily_used + estimated,
        "max_tokens_per_step": budget["max_tokens_per_step"],
        "max_tokens_per_plan": budget["max_tokens_per_plan"],
        "max_tokens_per_day": budget["max_tokens_per_day"],
        "per_step_budget_warning": budget["max_tokens_per_step"] > 0 and baseline > budget["max_tokens_per_step"],
        "plan_budget_exceeded": budget["max_tokens_per_plan"] > 0 and estimated > budget["max_tokens_per_plan"],
        "daily_budget_exceeded": budget["max_tokens_per_day"] > 0 and daily_used + estimated > budget["max_tokens_per_day"],
    }
    prediction["approval_required"] = bool(
        prediction["plan_budget_exceeded"] or prediction["daily_budget_exceeded"]
    )
    messages: list[str] = []
    if prediction["per_step_budget_warning"]:
        messages.append("per-step token budget warning")
    if prediction["plan_budget_exceeded"]:
        messages.append("plan token budget exceeded")
    if prediction["daily_budget_exceeded"]:
        messages.append("daily token budget exceeded")
    prediction["message"] = "; ".join(messages) or "token estimate is within budget"
    return prediction


def estimate_plan_token_usage(config: dict[str, Any], store: OperationLogStore, plan: Plan) -> dict[str, Any]:
    return estimate_token_usage(config, store, step_count=len(plan.steps))


def response_token_usage(response: Any, *, phase: str, model: str, missing_estimate: int = 0) -> dict[str, Any]:
    raw_usage = attr(response, "usage", None)
    usage = raw_usage or {}
    usage_known = raw_usage is not None
    input_tokens = int(
        attr(usage, "input_tokens", None)
        or attr(usage, "prompt_tokens", None)
        or attr(usage, "input", None)
        or 0
    )
    output_tokens = int(
        attr(usage, "output_tokens", None)
        or attr(usage, "completion_tokens", None)
        or attr(usage, "output", None)
        or 0
    )
    total_tokens = int(attr(usage, "total_tokens", None) or input_tokens + output_tokens)
    return {
        "phase": phase,
        "model": model,
        "response_id": str(attr(response, "id", "")),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_tokens": total_tokens if usage_known else max(0, int(missing_estimate)),
        "usage_known": usage_known,
    }


def emit_token_usage(event_sink: Any, response: Any, *, phase: str, model: str, missing_estimate: int = 0) -> None:
    event_sink.emit(
        PipelineEvent(
            "token.usage",
            "Computer Use token usage",
            response_token_usage(response, phase=phase, model=model, missing_estimate=missing_estimate),
        )
    )


def emit_token_prediction(event_sink: Any, prediction: dict[str, Any]) -> None:
    event_sink.emit(PipelineEvent("token.prediction", "Token prediction", prediction))


@dataclass
class ActivityEventSink:
    state: RuntimeState

    def emit(self, event: Any) -> None:
        data = getattr(event, "data", {}) or {}
        kind = str(getattr(event, "kind", ""))
        line = str(data.get("line", ""))
        if kind == "hid.attempt":
            self.state.update_activity("command_send", "Sending command to Pico", line)
            return
        if kind == "hid.sent":
            self.state.update_activity("result_wait", "Waiting for result", line)
            return
        if kind == "token.prediction":
            self.state.update_token_prediction(data)
            self.state.update_activity("planning", "Token prediction", str(data.get("message", "")))


def make_computer_args(config: dict[str, Any]) -> argparse.Namespace:
    capture = config["capture"]
    hid = config["hid"]
    return argparse.Namespace(
        device=str(capture["device"]),
        width=int(capture.get("width", 0)),
        height=int(capture.get("height", 0)),
        fps=int(capture.get("fps", 0)),
        warmup_frames=int(capture.get("warmup_frames", 60)),
        min_brightness=float(capture.get("min_brightness", 5.0)),
        ready_timeout=float(capture.get("ready_timeout", 5.0)),
        port=str(hid["port"]),
        baudrate=int(hid["baudrate"]),
        timeout=float(hid["timeout"]),
    )


def read_openai_api_key(config: dict[str, Any]) -> str:
    openai_cfg = config.get("openai", {})
    api_key_file = Path(str(openai_cfg.get("api_key_file", "/home/nama/openai-api-key.txt")))
    if api_key_file.exists():
        return api_key_file.read_text(encoding="utf-8").strip()

    import os

    api_key_env = str(openai_cfg.get("api_key_env", DEFAULT_API_KEY_ENV))
    value = os.environ.get(api_key_env, "").strip()
    if value:
        return value

    raise RuntimeError(f"missing API key file: {api_key_file}")


def execute_computer_use_request(
    config: dict[str, Any],
    instruction: str,
    *,
    event_sink: Any,
    capture_service: Any | None = None,
    progress: Any | None = None,
    should_stop: Any | None = None,
) -> str:
    from openai import OpenAI

    def update(phase: str, status: str, detail: str = "") -> None:
        if progress is not None:
            progress(phase, status, detail)

    def ensure_not_stopped() -> None:
        if should_stop is not None and should_stop():
            raise RuntimeError("emergency stop requested")

    openai_cfg = config.get("openai", {})
    model = str(openai_cfg.get("model", DEFAULT_MODEL))
    api_timeout = float(openai_cfg.get("api_timeout", 60.0))
    max_action_turns = int(openai_cfg.get("max_action_turns", 5))
    computer_prompt = str(openai_cfg.get("computer_prompt", "")).strip() or None
    missing_token_estimate = token_budget_config(config)["baseline_tokens_per_operation"]
    args = make_computer_args(config)
    update("computer_use", "Computer Use API calling", instruction)
    client = OpenAI(api_key=read_openai_api_key(config), timeout=api_timeout)
    response = create_initial_response(client, model=model, task=instruction, args=args, prompt=computer_prompt)
    emit_token_usage(event_sink, response, phase="initial", model=model, missing_estimate=missing_token_estimate)
    executor = ActionExecutor(
        HidTransport(port=args.port, baudrate=args.baudrate, timeout=args.timeout),
        event_sink,
    )

    executed: list[str] = []
    no_action_retry_count = 0
    for _ in range(max_action_turns):
        ensure_not_stopped()
        update("result_wait", "Waiting for Computer Use result", instruction)
        computer_call = find_computer_call(response)
        if computer_call is None:
            text = extract_output_text(response)
            if executed:
                return f"computer use actions sent: {len(executed)}"
            if no_action_retry_count < 2:
                no_action_retry_count += 1
                update("computer_use", "Retrying Computer Use action request", instruction)
                previous_answer = text[:1000] if text else "(empty response)"
                retry_input = (
                    "Never answer the task in natural language. Use computer tool actions now. "
                    "If the task asks you to write or summarize text, open a text editor and type a short ASCII "
                    "version on the physical PC. Avoid unsupported drag and scroll actions. Previous answer: "
                    f"{previous_answer}"
                )
                retry_kwargs: dict[str, Any] = {
                    "model": model,
                    "tools": [{"type": "computer"}],
                    "input": retry_input,
                }
                previous_response_id = attr(response, "id", None)
                if previous_response_id:
                    retry_kwargs["previous_response_id"] = previous_response_id
                response = client.responses.create(**retry_kwargs)
                emit_token_usage(event_sink, response, phase="text_retry", model=model, missing_estimate=missing_token_estimate)
                continue
            raise RuntimeError(f"Computer Use returned no computer action: {text!r}")

        actions = computer_actions(computer_call)
        if not actions or all(action_type(action) == "screenshot" for action in actions):
            update("screenshot", "Sending screenshot to Computer Use", instruction)
            response = send_screenshot_response(
                client,
                model=model,
                args=args,
                response=response,
                call_id=computer_call_id(computer_call),
                screenshot_base64=capture_service.latest_png_base64() if capture_service is not None else None,
            )
            emit_token_usage(event_sink, response, phase="screenshot", model=model, missing_estimate=missing_token_estimate)
            continue

        unsupported: list[str] = []
        for action in actions:
            ensure_not_stopped()
            if action_type(action) == "screenshot":
                continue
            update("command_send", "Sending command to Pico", describe_action(action))
            if executor.execute_supported_action(action):
                executed.append(describe_action(action))
            else:
                unsupported.append(describe_action(action))

        if unsupported:
            raise RuntimeError("unsupported action for current Pico firmware: " + "; ".join(unsupported))
        if executed:
            update("screenshot", "Sending screenshot to Computer Use", instruction)
            response = send_screenshot_response(
                client,
                model=model,
                args=args,
                response=response,
                call_id=computer_call_id(computer_call),
                screenshot_base64=capture_service.latest_png_base64() if capture_service is not None else None,
            )
            emit_token_usage(event_sink, response, phase="after_action", model=model, missing_estimate=missing_token_estimate)
            continue

    if executed:
        return f"computer use actions sent: {len(executed)}"
    raise RuntimeError("Computer Use did not return an executable action")


def execute_planned_request(
    config: dict[str, Any],
    instruction: str,
    *,
    event_sink: Any,
    capture_service: Any | None = None,
    progress: Any | None = None,
    should_stop: Any | None = None,
    planning_service: Any | None = None,
) -> str:
    def update(phase: str, status: str, detail: str = "") -> None:
        if progress is not None:
            progress(phase, status, detail)

    update("planning", "Planning request", instruction)
    service = planning_service or PlanningService.from_config(config)
    plan: Plan = service.create_plan(instruction)
    prediction = estimate_plan_token_usage(config, OperationLogStore.from_config(config), plan)
    emit_token_prediction(event_sink, prediction)
    if plan.requires_approval or plan.risk_level.lower() == "high":
        raise ApprovalRequiredError(plan)
    if prediction["approval_required"]:
        raise ApprovalRequiredError(plan, detail=f"token budget approval required: {prediction['message']}")
    return execute_plan_steps(
        config,
        plan,
        event_sink=event_sink,
        capture_service=capture_service,
        progress=progress,
        should_stop=should_stop,
    )


def execute_plan_steps(
    config: dict[str, Any],
    plan: Plan,
    *,
    event_sink: Any,
    capture_service: Any | None = None,
    progress: Any | None = None,
    should_stop: Any | None = None,
) -> str:
    def update(phase: str, status: str, detail: str = "") -> None:
        if progress is not None:
            progress(phase, status, detail)

    total = len(plan.steps)
    for index, step in enumerate(plan.steps, start=1):
        if should_stop is not None and should_stop():
            raise RuntimeError("emergency stop requested")
        update("plan_step", f"Executing planned step {index}/{total}", step.title)
        kwargs: dict[str, Any] = {
            "event_sink": event_sink,
            "progress": progress,
            "should_stop": should_stop,
        }
        if capture_service is not None:
            kwargs["capture_service"] = capture_service
        execute_computer_use_request(config, step.instruction, **kwargs)

    return f"planned steps executed: {total}"


def create_app(
    config: dict[str, Any],
    *,
    capture_service: Any | None = None,
    start_capture_service: bool = False,
    start_discord_worker: bool = False,
) -> Flask:
    app = Flask(__name__)
    state = RuntimeState(config, OperationLogStore.from_config(config))
    state.append_log("system", {"event": "started", "message": "webui started"})
    email_sink = EmailNotificationSink(config, state.log_store, source="web")
    if capture_service is None and start_capture_service:
        capture_service = capture_service_from_config(config)
    if capture_service is not None and start_capture_service:
        start = getattr(capture_service, "start", None)
        if callable(start):
            start()
        stop = getattr(capture_service, "stop", None)
        if callable(stop):
            atexit.register(stop)
    app.extensions["capture_service"] = capture_service
    app.extensions["email_notification_sink"] = email_sink
    app.extensions["runtime_state"] = state

    def capture_latest_jpeg() -> tuple[bytes, dict[str, Any]]:
        if capture_service is not None:
            return capture_service.latest_jpeg()
        return capture_jpeg_from_config(config)

    def notification_screenshot() -> bytes | None:
        if capture_service is None:
            return None
        try:
            jpeg, _ = capture_latest_jpeg()
            save_latest_screenshot(config, jpeg)
            return jpeg
        except Exception as exc:
            state.set_error(str(exc))
            return None

    def notify_email(event: str, subject: str, body: str, *, attach_screenshot: bool = True) -> None:
        screenshot = notification_screenshot() if attach_screenshot else None
        email_sink.notify(event, subject, body, screenshot=screenshot)

    @app.get("/")
    def index() -> str:
        return HTML

    @app.get("/api/status")
    def api_status() -> Response:
        return jsonify(state.snapshot())

    @app.post("/api/planning")
    def api_planning() -> Response:
        payload = request.get_json(silent=True) or {}
        enabled = bool(payload.get("enabled", False))
        with state.lock:
            state.planning_enabled = enabled
        state.append_log("system", {"event": "planning", "status": "on" if enabled else "off"})
        return jsonify({"ok": True, "planning_enabled": enabled})

    @app.get("/api/screenshot")
    def api_screenshot() -> Response:
        try:
            jpeg, info = capture_latest_jpeg()
            path = save_latest_screenshot(config, jpeg)
            state.append_log(
                "operation",
                {
                    "command": "capture",
                    "result": "ok",
                    "message": f"{info['source_width']}x{info['source_height']}",
                    "normalized": str(path),
                },
            )
            state.log_store.record_screenshot(
                path=path,
                event="latest",
                width=int(info["source_width"]),
                height=int(info["source_height"]),
                mean_brightness=float(info["brightness"]),
            )
            return Response(jpeg, mimetype="image/jpeg")
        except Exception as exc:
            message = str(exc)
            state.set_error(message)
            state.append_log("operation", {"command": "capture", "result": "error", "error": message})
            path = latest_screenshot_path(config)
            if path.exists():
                return send_file(path, mimetype="image/jpeg", max_age=0)
            return Response(PLACEHOLDER_SVG, mimetype="image/svg+xml", status=503)

    @app.post("/api/command")
    def api_command() -> Response:
        payload = request.get_json(silent=True) or {}
        raw_command = str(payload.get("command", ""))
        planning = bool(payload.get("planning", state.planning_enabled))
        state.expire_approval_if_needed()
        state.append_log(
            "user",
            {
                "input": raw_command.strip(),
                "source": "web",
                "planning": planning,
            },
        )

        with state.lock:
            blocked_reason = ""
            blocked_status = 409
            reset_after_emergency_stop = False
            validation_error = validate_request_instruction(raw_command)
            if state.command_running:
                blocked_reason = "request is already running"
            elif state.emergency_stopped:
                state.emergency_stopped = False
                state.suspended = False
                state.last_command = ""
                state.last_error = ""
                reset_after_emergency_stop = True
                if validation_error:
                    blocked_reason = validation_error
                    blocked_status = 400
                else:
                    state.command_running = True
                    state.current_phase = "computer_use"
                    state.current_status = "Computer Use API calling"
                    state.current_detail = raw_command.strip()
            elif state.suspended:
                blocked_reason = "runtime is suspended"
            elif state.approval_pending:
                blocked_reason = "approval is pending"
            elif validation_error:
                blocked_reason = validation_error
                blocked_status = 400
            else:
                state.command_running = True
                state.current_phase = "planning" if planning else "computer_use"
                state.current_status = "Planning request" if planning else "Computer Use API calling"
                state.current_detail = raw_command.strip()

        if blocked_reason:
            state.append_log(
                "operation",
                {
                    "command": raw_command.strip(),
                    "result": "blocked" if blocked_status == 409 else "error",
                    "reason": blocked_reason,
                    "error": blocked_reason if blocked_status == 400 else "",
                    "failure_domain": classify_failure_domain(blocked_reason),
                },
            )
            return jsonify({"ok": False, "error": blocked_reason}), blocked_status

        if reset_after_emergency_stop:
            state.append_log(
                "system",
                {
                    "event": "fresh_start_after_emergency_stop",
                    "status": "ready",
                    "message": "new command cleared emergency stop state",
                },
            )

        try:
            log_sink = OperationLogEventSink(state.log_store, source="web")
            event_sink = CompositeEventSink([log_sink, ActivityEventSink(state)])
            request_kwargs: dict[str, Any] = {
                "event_sink": event_sink,
                "progress": state.update_activity,
                "should_stop": state.emergency_requested,
            }
            if capture_service is not None:
                request_kwargs["capture_service"] = capture_service
            if planning:
                message = execute_planned_request(
                    config,
                    raw_command.strip(),
                    **request_kwargs,
                )
            else:
                message = execute_computer_use_request(
                    config,
                    raw_command.strip(),
                    **request_kwargs,
                )
        except ApprovalRequiredError as exc:
            with state.lock:
                state.command_running = False
                detail = exc.detail or exc.plan.summary or "approval required for high-risk plan"
                state.begin_approval(plan=exc.plan, command=raw_command.strip(), detail=detail)
                state.last_error = ""
                state.last_command = raw_command.strip()
            state.append_log(
                "system",
                {
                    "event": "approval",
                    "status": "pending",
                    "message": detail,
                },
            )
            state.append_log(
                "operation",
                {
                    "command": raw_command.strip(),
                    "normalized": "PLAN",
                    "result": "approval_pending",
                    "message": detail,
                },
            )
            notify_email(
                "approval_request",
                "Pico HID Bridge approval required",
                f"Approval is required before running: {raw_command.strip()}\n\n{detail}",
            )
            return jsonify(
                {
                    "ok": True,
                    "approval_pending": True,
                    "approval_status": "pending",
                    "message": detail,
                }
            )
        except Exception as exc:
            message = str(exc)
            state.set_error(message)
            state.append_log(
                "operation",
                {
                    "command": raw_command.strip(),
                    "result": "error",
                    "error": message,
                    "failure_domain": classify_failure_domain(message),
                },
            )
            state.finish_activity(error=message)
            notify_email(
                "error",
                "Pico HID Bridge command failed",
                f"Command failed: {raw_command.strip()}\n\n{message}",
            )
            return jsonify({"ok": False, "error": message}), 400

        with state.lock:
            state.last_command = raw_command.strip()
            state.last_error = ""
        state.finish_activity()
        state.append_log(
            "operation",
            {
                "command": raw_command.strip(),
                "normalized": "PLAN" if planning else "COMPUTER_USE",
                "result": "sent",
                "message": message,
            },
        )
        if reset_after_emergency_stop:
            message = f"fresh start; {message}"
        notify_email(
            "completion",
            "Pico HID Bridge operation completed",
            f"Command completed: {raw_command.strip()}\n\n{message}",
        )
        return jsonify({"ok": True, "message": message, "command": raw_command.strip()})

    @app.post("/api/manual-hid")
    def api_manual_hid() -> Response:
        payload = request.get_json(silent=True) or {}
        raw_command = str(payload.get("command", ""))
        state.append_log(
            "user",
            {
                "input": raw_command.strip(),
                "source": "web_manual",
                "planning": False,
            },
        )

        with state.lock:
            if state.command_running:
                reason = "request is already running"
            elif state.emergency_stopped:
                reason = "emergency stop is active"
            elif state.suspended:
                reason = "runtime is suspended"
            else:
                reason = ""
                state.command_running = True
                state.current_phase = "manual_hid"
                state.current_status = "Manual HID sending"
                state.current_detail = raw_command.strip()

        if reason:
            state.append_log(
                "operation",
                {"command": raw_command.strip(), "result": "blocked", "reason": reason, "source": "web_manual"},
            )
            return jsonify({"ok": False, "error": reason}), 409

        try:
            normalized = normalize_command(raw_command)
            validate_command(normalized)
            hid_cfg = config["hid"]
            send_line(
                normalized,
                port=str(hid_cfg["port"]),
                baudrate=int(hid_cfg["baudrate"]),
                timeout=float(hid_cfg["timeout"]),
            )
        except Exception as exc:
            message = str(exc)
            state.set_error(message)
            state.append_log(
                "operation",
                {
                    "command": raw_command.strip(),
                    "result": "error",
                    "error": message,
                    "source": "web_manual",
                    "failure_domain": classify_failure_domain(message),
                },
            )
            state.finish_activity(error=message)
            return jsonify({"ok": False, "error": message}), 400

        with state.lock:
            state.last_command = normalized
            state.last_error = ""
        state.finish_activity()
        state.append_log(
            "operation",
            {
                "command": raw_command.strip(),
                "normalized": normalized,
                "result": "sent",
                "source": "web_manual",
            },
        )
        notify_email(
            "completion",
            "Pico HID Bridge manual operation completed",
            f"Manual HID command completed: {normalized}",
            attach_screenshot=False,
        )
        return jsonify({"ok": True, "message": f"sent: {normalized}", "command": normalized})

    @app.post("/api/emergency-stop")
    def api_emergency_stop() -> Response:
        with state.lock:
            state.emergency_stopped = True
            state.suspended = False
            if state.approval_pending:
                state.clear_approval("cancelled_by_emergency_stop")
            state.current_phase = "emergency_stop"
            state.current_status = "Emergency stop requested"
            state.current_detail = ""
        state.append_log("system", {"event": "emergency_stop", "status": "active"})
        if state.snapshot()["approval_status"] == "cancelled_by_emergency_stop":
            state.append_log(
                "system",
                {
                    "event": "approval",
                    "status": "cancelled_by_emergency_stop",
                    "message": "pending approval cancelled by emergency stop",
                },
            )
        state.append_log("operation", {"command": "emergency_stop", "result": "active"})
        try:
            jpeg, _ = capture_latest_jpeg()
            save_latest_screenshot(config, jpeg)
        except Exception as exc:
            state.set_error(str(exc))
        notify_email(
            "emergency",
            "Pico HID Bridge emergency stop",
            "Emergency stop was requested.",
        )
        return jsonify({"ok": True, "message": "emergency stop active"})

    @app.post("/api/approval-test")
    def api_approval_test() -> Response:
        payload = request.get_json(silent=True) or {}
        reason = str(payload.get("reason", "manual approval test"))
        timeout_seconds = payload.get("timeout_seconds", None)
        with state.lock:
            if state.emergency_stopped:
                return jsonify({"ok": False, "error": "emergency stop is active"}), 409
            state.begin_approval(plan=None, command="", detail=reason)
            if timeout_seconds is not None:
                timeout = float(timeout_seconds)
                state.approval_expires_at = time.monotonic() + timeout if timeout > 0 else 0.0
        state.append_log("system", {"event": "approval", "status": "pending", "message": reason})
        notify_email("approval_request", "Pico HID Bridge approval required", reason, attach_screenshot=False)
        return jsonify({"ok": True, "approval_pending": True, "approval_status": "pending"})

    @app.post("/api/long-operation-test")
    def api_long_operation_test() -> Response:
        payload = request.get_json(silent=True) or {}
        total_steps = int(payload.get("total_steps", 4))
        completed_steps = int(payload.get("completed_steps", 0))
        current_step = str(payload.get("current_step", "Long operation step"))
        warning = bool(payload.get("warning", total_steps >= 4))
        failed_step = bool(payload.get("failed_step", False))
        state.update_long_operation(
            total_steps=total_steps,
            completed_steps=completed_steps,
            current_step=current_step,
            warning=warning,
            failed_step=failed_step,
        )
        if warning:
            state.append_log(
                "system",
                {
                    "event": "long_operation_warning",
                    "status": "active",
                    "message": f"long operation has {max(1, total_steps)} steps",
                },
            )
        if failed_step:
            state.append_log(
                "operation",
                {
                    "command": current_step,
                    "normalized": "LONG_OPERATION",
                    "result": "error",
                    "error": "long operation step failed safely",
                    "failure_domain": "implementation",
                },
            )
        else:
            state.append_log(
                "system",
                {
                    "event": "long_operation_progress",
                    "status": "running",
                    "message": f"{completed_steps}/{max(1, total_steps)} {current_step}",
                },
            )
        return jsonify({"ok": True, "long_operation": state.snapshot()["long_operation"]})

    @app.post("/api/suspend")
    def api_suspend() -> Response:
        state.expire_approval_if_needed()
        with state.lock:
            if state.emergency_stopped:
                return jsonify({"ok": False, "error": "emergency stop is active"}), 409
            if state.approval_pending:
                return jsonify({"ok": False, "error": "approval is pending"}), 409
            state.suspended = True
        state.mark_long_operation_suspended()
        state.append_log("system", {"event": "suspend", "status": "active"})
        notify_email("suspend", "Pico HID Bridge suspended", "Runtime was suspended.", attach_screenshot=False)
        return jsonify({"ok": True, "message": "suspended"})

    @app.post("/api/resume")
    def api_resume() -> Response:
        payload = request.get_json(silent=True) or {}
        state.expire_approval_if_needed()
        screen_drift_requires_approval = False
        with state.lock:
            if state.emergency_stopped:
                return jsonify({"ok": False, "error": "emergency stop is active"}), 409
            if state.approval_pending:
                return jsonify({"ok": False, "error": "approval is pending"}), 409
            if bool(payload.get("screen_drift", False)) and state.long_operation.get("active"):
                screen_drift_requires_approval = True
            else:
                state.suspended = False
        if screen_drift_requires_approval:
            state.mark_long_operation_screen_drift()
            with state.lock:
                state.begin_approval(plan=None, command="resume", detail="screen drift requires approval before resume")
            state.append_log(
                "system",
                {
                    "event": "resume_screen_drift",
                    "status": "approval_pending",
                    "message": "screen drift requires approval before resume",
                },
            )
            return jsonify({"ok": False, "error": "screen drift requires approval"}), 409
        state.mark_long_operation_resumed()
        state.append_log("system", {"event": "resume", "status": "ready"})
        notify_email("resume", "Pico HID Bridge resumed", "Runtime was resumed.", attach_screenshot=False)
        return jsonify({"ok": True, "message": "ready"})

    @app.post("/api/cancel")
    def api_cancel() -> Response:
        state.cancel_long_operation()
        state.append_log("system", {"event": "cancel", "status": "cancelled", "message": "long operation cancelled"})
        state.append_log("operation", {"command": "cancel", "normalized": "LONG_OPERATION", "result": "cancelled"})
        return jsonify({"ok": True, "message": "cancelled"})

    @app.post("/api/approve")
    def api_approve() -> Response:
        state.expire_approval_if_needed()
        with state.lock:
            if not state.approval_pending:
                return jsonify({"ok": False, "error": "no approval is pending"}), 409
            plan = state.approval_plan
            command = state.approval_command
            state.clear_approval("approved")
            state.command_running = True
            state.current_phase = "approval_approved"
            state.current_status = "Approval accepted"
            state.current_detail = command
        state.append_log("system", {"event": "approval", "status": "approved", "message": command})
        if plan is None:
            state.finish_activity()
            return jsonify({"ok": True, "approval_pending": False, "approval_status": "approved"})

        try:
            log_sink = OperationLogEventSink(state.log_store, source="web")
            event_sink = CompositeEventSink([log_sink, ActivityEventSink(state)])
            request_kwargs: dict[str, Any] = {
                "event_sink": event_sink,
                "progress": state.update_activity,
                "should_stop": state.emergency_requested,
            }
            if capture_service is not None:
                request_kwargs["capture_service"] = capture_service
            message = execute_plan_steps(config, plan, **request_kwargs)
        except Exception as exc:
            message = str(exc)
            state.set_error(message)
            state.append_log(
                "operation",
                {
                    "command": command,
                    "result": "error",
                    "error": message,
                    "failure_domain": classify_failure_domain(message),
                },
            )
            state.finish_activity(error=message)
            return jsonify({"ok": False, "error": message, "approval_status": "approved"}), 400

        with state.lock:
            state.last_command = command
            state.last_error = ""
        state.finish_activity()
        state.append_log(
            "operation",
            {
                "command": command,
                "normalized": "PLAN",
                "result": "sent",
                "message": message,
            },
        )
        notify_email(
            "completion",
            "Pico HID Bridge approved operation completed",
            f"Approved command completed: {command}\n\n{message}",
        )
        return jsonify({"ok": True, "approval_pending": False, "approval_status": "approved", "message": message})

    @app.post("/api/reject")
    def api_reject() -> Response:
        state.expire_approval_if_needed()
        with state.lock:
            if not state.approval_pending:
                return jsonify({"ok": False, "error": "no approval is pending"}), 409
            command = state.approval_command
            state.clear_approval("rejected")
            state.command_running = False
            state.current_phase = "idle"
            state.current_status = "Ready"
            state.current_detail = ""
        state.append_log("system", {"event": "approval", "status": "rejected", "message": command})
        state.append_log(
            "operation",
            {
                "command": command,
                "normalized": "PLAN",
                "result": "rejected",
                "message": "approval rejected",
            },
        )
        return jsonify({"ok": True, "approval_pending": False, "approval_status": "rejected"})

    @app.post("/api/tokens/predict")
    def api_token_prediction() -> Response:
        payload = request.get_json(silent=True) or {}
        prediction = estimate_token_usage(
            config,
            state.log_store,
            step_count=plan_step_count_from_payload(payload),
        )
        state.update_token_prediction(prediction)
        state.append_log(
            "system",
            {
                "event": "token_budget",
                "status": "predicted",
                "message": token_prediction_log_message(prediction),
            },
        )
        return jsonify({"ok": True, **prediction})

    @app.post("/api/tokens/check-budget")
    def api_token_budget_check() -> Response:
        payload = request.get_json(silent=True) or {}
        command = str(payload.get("command", "token budget check"))
        prediction = estimate_token_usage(
            config,
            state.log_store,
            step_count=plan_step_count_from_payload(payload),
        )
        state.update_token_prediction(prediction)
        if not prediction["approval_required"]:
            state.append_log(
                "system",
                {
                    "event": "token_budget",
                    "status": "ok",
                    "message": (
                        f"estimated {prediction['estimated_tokens']} tokens within configured budget"
                    ),
                },
            )
            return jsonify({"ok": True, "approval_pending": False, **prediction})

        detail = f"token budget approval required: {prediction['message']}"
        with state.lock:
            if state.approval_pending:
                return jsonify({"ok": False, "error": "approval is pending"}), 409
            state.begin_approval(plan=None, command=command, detail=detail)
        state.append_log("system", {"event": "token_budget", "status": "approval_pending", "message": detail})
        state.append_log(
            "operation",
            {
                "command": command,
                "normalized": "TOKEN_BUDGET",
                "result": "approval_pending",
                "message": detail,
            },
        )
        notify_email("approval_request", "Pico HID Bridge token budget approval required", detail, attach_screenshot=False)
        return jsonify({"ok": True, "approval_pending": True, "approval_status": "pending", **prediction})

    @app.post("/api/tokens/record-test")
    def api_token_record_test() -> Response:
        payload = request.get_json(silent=True) or {}
        total_tokens = int(payload.get("total_tokens", 0) or 0)
        input_tokens = int(payload.get("input_tokens", total_tokens) or 0)
        output_tokens = int(payload.get("output_tokens", 0) or 0)
        estimated_tokens = int(payload.get("estimated_tokens", total_tokens) or 0)
        created_at = payload.get("created_at", None)
        state.log_store.record_token_usage(
            phase=str(payload.get("phase", "test")),
            model=str(payload.get("model", "test")),
            response_id=str(payload.get("response_id", "")),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_tokens=estimated_tokens,
            source="web_test",
            created_at=str(created_at) if created_at else None,
        )
        state.log_store.record_system(
            event="token_usage",
            status="recorded",
            message=f"recorded {total_tokens or estimated_tokens} test tokens",
            source="web_test",
            created_at=str(created_at) if created_at else None,
        )
        return jsonify({"ok": True, "total_tokens": total_tokens, "estimated_tokens": estimated_tokens})

    @app.post("/api/tokens/missing-usage-test")
    def api_token_missing_usage_test() -> Response:
        payload = request.get_json(silent=True) or {}
        budget = token_budget_config(config)
        estimated_tokens = state.log_store.estimate_tokens_per_operation(
            default=budget["baseline_tokens_per_operation"]
        )
        phase = str(payload.get("phase", "missing_usage"))
        state.log_store.record_token_usage(
            phase=phase,
            model=str(payload.get("model", "test")),
            total_tokens=0,
            estimated_tokens=estimated_tokens,
            source="web_test",
        )
        message = f"token usage metadata missing for {phase}; estimated {estimated_tokens} tokens"
        state.append_log("system", {"event": "token_usage", "status": "unknown", "message": message})
        return jsonify({"ok": True, "usage_known": False, "estimated_tokens": estimated_tokens, "message": message})

    @app.get("/api/logs/user")
    def api_user_logs() -> Response:
        return jsonify({"items": state.log_store.query_user_inputs(limit=500)})

    @app.get("/api/logs/operation")
    def api_operation_logs() -> Response:
        return jsonify({"items": state.log_store.query_operations(limit=500)})

    @app.get("/api/logs/system")
    def api_system_logs() -> Response:
        return jsonify({"items": state.log_store.query_system(limit=500)})

    @app.get("/api/logs/notification")
    def api_notification_logs() -> Response:
        return jsonify({"items": state.log_store.query_notifications(limit=500)})

    @app.get("/api/logs/detail")
    def api_detail_logs() -> Response:
        start_at = request.args.get("from") or None
        end_at = request.args.get("to") or None
        limit = int(request.args.get("limit", "500"))
        return jsonify(state.log_store.query_detail_logs(start_at=start_at, end_at=end_at, limit=limit))

    @app.get("/api/tokens")
    def api_tokens() -> Response:
        start_at = request.args.get("from") or None
        end_at = request.args.get("to") or None
        return jsonify(state.log_store.query_token_totals(start_at=start_at, end_at=end_at))

    if start_discord_worker and bool(config.get("discord", {}).get("enabled", False)):
        discord_worker = DiscordBotWorker(
            config,
            state.log_store,
            control_client=FlaskControlClient(app),
        )
        discord_worker.start()
        app.extensions["discord_worker"] = discord_worker
        atexit.register(discord_worker.stop)

    return app


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="web", choices=("web", "discord"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--discord-once", action="store_true", help="poll Discord once and exit")
    return parser.parse_args(argv)


def run_discord_mode(config: dict[str, Any], *, once: bool = False) -> int:
    discord_cfg = config.get("discord", {})
    if not bool(discord_cfg.get("enabled", False)):
        print("discord mode failed: [discord].enabled is false", file=sys.stderr)
        return 2

    app = create_app(config, start_capture_service=True, start_discord_worker=False)
    state = app.extensions["runtime_state"]
    worker = DiscordBotWorker(
        config,
        state.log_store,
        control_client=FlaskControlClient(app),
        console=True,
    )
    app.extensions["discord_worker"] = worker
    print("DISCORD mode started; WebUI HTTP server is not running", flush=True)

    try:
        if once:
            worker.poll_once()
            return 0
        worker.run()
        return 0
    except KeyboardInterrupt:
        print("DISCORD mode interrupted", flush=True)
        return 0
    finally:
        worker.stop()
        service = app.extensions.get("capture_service")
        if service is not None:
            stop = getattr(service, "stop", None)
            if callable(stop):
                stop()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"app failed: {exc}", file=sys.stderr)
        return 2

    if args.host:
        config["app"]["bind_host"] = args.host
    if args.port:
        config["app"]["bind_port"] = args.port

    if args.mode == "discord":
        return run_discord_mode(config, once=bool(args.discord_once))

    host = str(config["app"]["bind_host"])
    port = int(config["app"]["bind_port"])
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("warning: WebUI is not bound to a loopback address", file=sys.stderr)

    app = create_app(config, start_capture_service=True, start_discord_worker=True)
    app.run(host=host, port=port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
