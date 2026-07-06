from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pico_hid_bridge.computer_use import build_computer_use_input, create_initial_response


def test_default_computer_use_prompt_prefers_keyboard_shortcuts() -> None:
    prompt = build_computer_use_input("open browser")

    assert "keyboard-first" in prompt
    assert "WIN+R" in prompt
    assert "ALT+TAB" in prompt
    assert "Do not use drag or scroll actions" in prompt
    assert "Task: open browser" in prompt


def test_computer_use_prompt_can_be_overridden() -> None:
    prompt = build_computer_use_input("open browser", prompt="custom prompt")

    assert prompt == "custom prompt\n\nTask: open browser"


@dataclass
class FakeResponses:
    calls: list[dict[str, Any]]

    def create(self, **kwargs: Any) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"output": []}


@dataclass
class FakeClient:
    responses: FakeResponses


def test_create_initial_response_passes_custom_prompt() -> None:
    responses = FakeResponses([])
    client = FakeClient(responses)

    create_initial_response(client, model="test-model", task="open browser", args=object(), prompt="custom prompt")

    assert responses.calls[-1]["input"] == "custom prompt\n\nTask: open browser"
