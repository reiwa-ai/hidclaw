"""Action execution pipeline hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
import time

from .computer_use import action_type, attr, describe_action
from .hid import TEXT_MAX_LENGTH, normalize_keypress, send_line


MAX_RELATIVE_MOUSE_MOVE = 100
POINTER_ORIGIN_RESET_STEPS = 20
HID_SETTLE_SECONDS = 0.25
MOUSE_HID_SETTLE_SECONDS = 0.12


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PipelineEvent:
    kind: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)


class EventSink(Protocol):
    def emit(self, event: PipelineEvent) -> None:
        ...


class NullEventSink:
    def emit(self, event: PipelineEvent) -> None:
        return


class CompositeEventSink:
    def __init__(self, sinks: list[EventSink] | None = None) -> None:
        self.sinks = list(sinks or [])

    def emit(self, event: PipelineEvent) -> None:
        for sink in self.sinks:
            sink.emit(event)


class PrintEventSink:
    def emit(self, event: PipelineEvent) -> None:
        print(f"{event.created_at} {event.kind}: {event.message}")


@dataclass
class HidTransport:
    port: str
    baudrate: int
    timeout: float

    def send(self, line: str) -> None:
        send_line(line, port=self.port, baudrate=self.baudrate, timeout=self.timeout)


def text_action_to_hid_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    parts = normalized.split("\n")
    for line_index, part in enumerate(parts):
        for index in range(0, len(part), TEXT_MAX_LENGTH):
            lines.append(f"TEXT {part[index : index + TEXT_MAX_LENGTH]}")
        if line_index < len(parts) - 1:
            lines.append("KEY ENTER")
    return lines


class ActionExecutor:
    def __init__(
        self,
        transport: HidTransport,
        sink: EventSink | None = None,
        *,
        hid_settle_seconds: float = HID_SETTLE_SECONDS,
        mouse_settle_seconds: float = MOUSE_HID_SETTLE_SECONDS,
    ) -> None:
        self.transport = transport
        self.sink = sink or NullEventSink()
        self.hid_settle_seconds = hid_settle_seconds
        self.mouse_settle_seconds = mouse_settle_seconds

    def send_hid(self, line: str, *, settle_seconds: float = 0.0) -> None:
        self.sink.emit(PipelineEvent("hid.attempt", "sending HID command", {"line": line}))
        self.transport.send(line)
        if settle_seconds > 0:
            time.sleep(settle_seconds)

    def execute_supported_action(self, action: Any) -> bool:
        kind = action_type(action)
        if kind == "type":
            text = str(attr(action, "text", ""))
            if not text:
                self.sink.emit(PipelineEvent("action.skipped", "empty type action"))
                return False
            hid_lines = text_action_to_hid_lines(text)
            for line in hid_lines:
                self.send_hid(line, settle_seconds=self.hid_settle_seconds)
            self.sink.emit(PipelineEvent("hid.sent", "sent text action", {"line": hid_lines[-1]}))
            return True

        if kind == "keypress":
            line = normalize_keypress(list(attr(action, "keys", []) or []))
            if line is None:
                self.sink.emit(PipelineEvent("action.skipped", "unsupported keypress"))
                return False
            self.send_hid(line, settle_seconds=self.hid_settle_seconds)
            self.sink.emit(PipelineEvent("hid.sent", "sent keypress action", {"line": line}))
            return True

        if kind == "wait":
            time.sleep(2)
            self.sink.emit(PipelineEvent("action.wait", "waited for 2 seconds"))
            return True

        if kind in {"click", "double_click", "move"}:
            x = attr(action, "x", None)
            y = attr(action, "y", None)
            if x is None or y is None:
                self.sink.emit(PipelineEvent("action.skipped", "mouse action missing coordinates"))
                return False

            try:
                target_x = int(x)
                target_y = int(y)
            except (TypeError, ValueError):
                self.sink.emit(PipelineEvent("action.skipped", "mouse action has invalid coordinates"))
                return False

            for line in mouse_move_to_lines(target_x, target_y):
                self.send_hid(line, settle_seconds=self.mouse_settle_seconds)

            if kind == "move":
                self.sink.emit(PipelineEvent("hid.sent", "sent mouse move action", {"x": target_x, "y": target_y}))
                return True

            button = str(attr(action, "button", "left") or "left").upper()
            if button not in {"LEFT", "RIGHT"}:
                self.sink.emit(PipelineEvent("action.skipped", "unsupported mouse button", {"button": button}))
                return False

            click_count = 2 if kind == "double_click" else 1
            for _ in range(click_count):
                self.send_hid(f"CLICK {button}", settle_seconds=self.mouse_settle_seconds)
            self.sink.emit(
                PipelineEvent(
                    "hid.sent",
                    "sent mouse click action",
                    {"x": target_x, "y": target_y, "button": button, "count": click_count},
                )
            )
            return True

        self.sink.emit(
            PipelineEvent(
                "action.unsupported",
                "unsupported action for current Pico firmware",
                {"action": describe_action(action)},
            )
        )
        return False


def mouse_move_to_lines(x: int, y: int) -> list[str]:
    lines = ["MOUSE_MOVE -100 -100"] * POINTER_ORIGIN_RESET_STEPS
    lines.extend(relative_mouse_move_lines(max(0, x), max(0, y)))
    return lines


def relative_mouse_move_lines(dx: int, dy: int) -> list[str]:
    lines: list[str] = []
    remaining_x = dx
    remaining_y = dy
    while remaining_x or remaining_y:
        step_x = max(-MAX_RELATIVE_MOUSE_MOVE, min(MAX_RELATIVE_MOUSE_MOVE, remaining_x))
        step_y = max(-MAX_RELATIVE_MOUSE_MOVE, min(MAX_RELATIVE_MOUSE_MOVE, remaining_y))
        lines.append(f"MOUSE_MOVE {step_x} {step_y}")
        remaining_x -= step_x
        remaining_y -= step_y
    return lines


def execute_supported_action(action: Any, args: Any) -> bool:
    sink: EventSink = PrintEventSink()
    extra_sink = getattr(args, "event_sink", None)
    if extra_sink is not None:
        sink = CompositeEventSink([sink, extra_sink])

    executor = ActionExecutor(
        HidTransport(port=args.port, baudrate=args.baudrate, timeout=args.timeout),
        sink,
    )
    return executor.execute_supported_action(action)
