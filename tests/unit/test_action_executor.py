from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pico_hid_bridge.actions import ActionExecutor, PipelineEvent


@dataclass
class FakeTransport:
    sent: list[str] = field(default_factory=list)
    error: Exception | None = None

    def send(self, line: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(line)


@dataclass
class FakeSink:
    events: list[PipelineEvent] = field(default_factory=list)

    def emit(self, event: PipelineEvent) -> None:
        self.events.append(event)


@dataclass
class FakeSleep:
    calls: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def test_execute_type_action_sends_text(fake_transport: FakeTransport) -> None:
    sink = FakeSink()
    executor = ActionExecutor(fake_transport, sink)

    assert executor.execute_supported_action({"type": "type", "text": "Pico HID test 123"})
    assert fake_transport.sent == ["TEXT Pico HID test 123"]
    assert sink.events[-1].kind == "hid.sent"


def test_execute_type_action_splits_newlines_into_enter_keys(fake_transport: FakeTransport) -> None:
    executor = ActionExecutor(fake_transport, FakeSink())

    assert executor.execute_supported_action({"type": "type", "text": "Line one\nLine two"})

    assert fake_transport.sent == ["TEXT Line one", "KEY ENTER", "TEXT Line two"]


def test_execute_type_action_splits_text_above_hid_line_limit(fake_transport: FakeTransport) -> None:
    executor = ActionExecutor(fake_transport, FakeSink())

    assert executor.execute_supported_action({"type": "type", "text": "A" * 300})

    assert fake_transport.sent == ["TEXT " + ("A" * 256), "TEXT " + ("A" * 44)]


def test_execute_type_action_reports_hid_attempt_before_send_failure() -> None:
    sink = FakeSink()
    executor = ActionExecutor(FakeTransport(error=TimeoutError("Pico did not acknowledge command completion")), sink)

    try:
        executor.execute_supported_action({"type": "type", "text": "open browser"})
    except TimeoutError:
        pass
    else:
        raise AssertionError("expected send failure")

    assert sink.events[0].kind == "hid.attempt"
    assert sink.events[0].data["line"] == "TEXT open browser"


def test_execute_keypress_action_sends_key_combo(fake_transport: FakeTransport) -> None:
    executor = ActionExecutor(fake_transport, FakeSink())

    assert executor.execute_supported_action({"type": "keypress", "keys": ["WIN", "R"]})
    assert fake_transport.sent == ["KEY WIN+R"]


def test_execute_keyboard_actions_settle_after_each_hid_command(
    fake_transport: FakeTransport,
    fake_sleep: FakeSleep,
    monkeypatch: Any,
) -> None:
    from pico_hid_bridge import actions

    monkeypatch.setattr(actions.time, "sleep", fake_sleep)
    executor = ActionExecutor(fake_transport, FakeSink(), hid_settle_seconds=0.4)

    assert executor.execute_supported_action({"type": "keypress", "keys": ["WIN", "R"]})
    assert executor.execute_supported_action({"type": "type", "text": "chrome"})

    assert fake_transport.sent == ["KEY WIN+R", "TEXT chrome"]
    assert fake_sleep.calls == [0.4, 0.4]


def test_execute_keyboard_actions_can_disable_settle(
    fake_transport: FakeTransport,
    fake_sleep: FakeSleep,
    monkeypatch: Any,
) -> None:
    from pico_hid_bridge import actions

    monkeypatch.setattr(actions.time, "sleep", fake_sleep)
    executor = ActionExecutor(fake_transport, FakeSink(), hid_settle_seconds=0)

    assert executor.execute_supported_action({"type": "keypress", "keys": ["WIN", "R"]})

    assert fake_sleep.calls == []


def test_execute_wait_action_waits(fake_sleep: FakeSleep, monkeypatch: Any) -> None:
    from pico_hid_bridge import actions

    monkeypatch.setattr(actions.time, "sleep", fake_sleep)
    executor = ActionExecutor(FakeTransport(), FakeSink())

    assert executor.execute_supported_action({"type": "wait"})
    assert fake_sleep.calls == [2]


def test_execute_unsupported_action_reports_event(fake_transport: FakeTransport) -> None:
    sink = FakeSink()
    executor = ActionExecutor(fake_transport, sink)

    assert not executor.execute_supported_action({"type": "drag", "x": 1, "y": 2})
    assert fake_transport.sent == []
    assert sink.events[-1].kind == "action.unsupported"


def test_execute_click_action_moves_from_origin_and_clicks(fake_transport: FakeTransport) -> None:
    sink = FakeSink()
    executor = ActionExecutor(fake_transport, sink, mouse_settle_seconds=0)

    assert executor.execute_supported_action({"type": "click", "x": 230, "y": 120, "button": "left"})

    assert fake_transport.sent[:2] == ["MOUSE_MOVE -100 -100", "MOUSE_MOVE -100 -100"]
    assert "MOUSE_MOVE 100 100" in fake_transport.sent
    assert "MOUSE_MOVE 100 20" in fake_transport.sent
    assert "MOUSE_MOVE 30 0" in fake_transport.sent
    assert fake_transport.sent[-1] == "CLICK LEFT"
    assert sink.events[-1].kind == "hid.sent"


def test_execute_mouse_action_settles_between_hid_commands(
    fake_transport: FakeTransport,
    fake_sleep: FakeSleep,
    monkeypatch: Any,
) -> None:
    from pico_hid_bridge import actions

    monkeypatch.setattr(actions.time, "sleep", fake_sleep)
    executor = ActionExecutor(fake_transport, FakeSink(), mouse_settle_seconds=0.12)

    assert executor.execute_supported_action({"type": "click", "x": 0, "y": 0, "button": "left"})

    assert len(fake_sleep.calls) == len(fake_transport.sent)
    assert set(fake_sleep.calls) == {0.12}
