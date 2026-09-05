"""OpenAI Computer Use helpers."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from .capture import capture_png_base64
from .intent import AgentIntent, analyze_user_intent, build_intent_prompt_block
from .prompt_assets import DEFAULT_COMPUTER_PROMPT


DEFAULT_API_KEY_ENV = "OPENAI_API_KEY"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.5")


def attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def computer_tool(args: Any) -> dict[str, str]:
    return {"type": "computer"}


def build_computer_use_input(
    task: str,
    *,
    prompt: str | None = None,
    intent: AgentIntent | None = None,
) -> str:
    if prompt is not None and intent is None:
        return f"{prompt.strip()}\n\nTask: {task}"

    base_prompt = (prompt or DEFAULT_COMPUTER_PROMPT).strip()
    resolved_intent = intent or analyze_user_intent(task)
    return "\n\n".join(
        [
            base_prompt,
            build_intent_prompt_block(resolved_intent, heading="Execution context"),
            f"Task: {resolved_intent.user_instruction or task}",
        ]
    )


def build_retry_input(
    task: str,
    previous_answer: str,
    *,
    prompt: str | None = None,
    intent: AgentIntent | None = None,
) -> str:
    base = build_computer_use_input(task, prompt=prompt, intent=intent)
    return "\n\n".join(
        [
            base,
            (
                "Correction: Never answer the task in natural language. "
                "Use computer tool actions now. If the task asks you to write or summarize text, "
                "open a text editor and type a short ASCII version on the physical PC. "
                "Avoid unsupported drag and scroll actions."
            ),
            f"Previous answer: {previous_answer or '(empty response)'}",
        ]
    )


def create_initial_response(
    client: OpenAI,
    *,
    model: str,
    task: str,
    args: Any,
    prompt: str | None = None,
    intent: AgentIntent | None = None,
) -> Any:
    return client.responses.create(
        model=model,
        tools=[computer_tool(args)],
        input=build_computer_use_input(task, prompt=prompt, intent=intent),
    )


def send_screenshot_response(
    client: OpenAI,
    *,
    model: str,
    args: Any,
    response: Any,
    call_id: str,
    screenshot_base64: str | None = None,
) -> Any:
    if screenshot_base64 is None:
        screenshot_base64 = capture_png_base64(args)
    return client.responses.create(
        model=model,
        tools=[computer_tool(args)],
        previous_response_id=attr(response, "id"),
        input=[
            {
                "type": "computer_call_output",
                "call_id": call_id,
                "output": {
                    "type": "computer_screenshot",
                    "image_url": f"data:image/png;base64,{screenshot_base64}",
                    "detail": "original",
                },
            }
        ],
    )


def find_computer_call(response: Any) -> Any | None:
    for item in attr(response, "output", []) or []:
        if attr(item, "type") == "computer_call":
            return item
    return None


def action_type(action: Any) -> str:
    return str(attr(action, "type", "")).lower()


def describe_action(action: Any) -> str:
    kind = action_type(action)
    if kind == "type":
        return f'type text={attr(action, "text", "")!r}'
    if kind == "keypress":
        return f"keypress keys={attr(action, 'keys', [])!r}"
    if kind in {"click", "double_click", "move", "scroll"}:
        return f"{kind} x={attr(action, 'x', None)} y={attr(action, 'y', None)}"
    if kind == "wait":
        return "wait"
    if kind == "screenshot":
        return "screenshot"
    return repr(action)


def computer_actions(computer_call: Any) -> list[Any]:
    actions = attr(computer_call, "actions", None)
    if actions is None:
        action = attr(computer_call, "action", None)
        actions = [action] if action is not None else []
    return list(actions or [])


def computer_call_id(computer_call: Any) -> str:
    call_id = attr(computer_call, "call_id", None) or attr(computer_call, "id", None)
    if not call_id:
        raise RuntimeError("computer_call has no call_id")
    return str(call_id)


def extract_output_text(response: Any) -> str:
    output_text = str(attr(response, "output_text", "") or "").strip()
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in attr(response, "output", []) or []:
        content = attr(item, "content", []) or []
        for part in content:
            text = attr(part, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()
