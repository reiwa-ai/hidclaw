"""Planning wrapper for turning user requests into executable step instructions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from openai import OpenAI

from .computer_use import DEFAULT_API_KEY_ENV, DEFAULT_MODEL, attr


DEFAULT_PLANNING_PROMPT = (
    "You are a planning layer for a physical Windows PC controlled through a Computer Use API. "
    "Your job is to convert one user request into a short ordered list of concrete instructions. "
    "Each instruction will later be sent independently to a separate Computer Use executor. "
    "Do not produce low-level HID commands. Do not mention tests, scenarios, or implementation internals. "
    "Do not specialize for test scenarios. Keep steps generic, observable, and safe. "
    "Prefer keyboard-friendly Windows workflows. Use WIN+R to open apps when appropriate. "
    "Avoid plan steps that depend on scrolling or page navigation keys; use visible information when enough is available. "
    "When a step asks to write a summary, keep it to one short ASCII sentence unless the user explicitly asks for more. "
    "Do not save, delete, send, post, purchase, install, change settings, enter passwords, or enter personal data. "
    "Mathematically undefined operations such as division by zero are impossible. "
    "Do not plan navigation to localhost or loopback URLs unless the user explicitly states that a reachable service is running. "
    "If the request asks for an unsafe or impossible action, return requires_approval=true or risk_level=high. "
    "Return JSON only."
)


PLANNING_JSON_SCHEMA: dict[str, Any] = {
    "name": "pc_operation_plan",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "requires_approval": {"type": "boolean"},
            "summary": {"type": "string"},
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "instruction": {"type": "string"},
                        "expected_result": {"type": "string"},
                    },
                    "required": ["instruction"],
                },
            },
        },
        "required": ["steps"],
    },
    "strict": False,
}


@dataclass(frozen=True)
class PlanningStep:
    title: str
    instruction: str
    expected_result: str = ""


@dataclass(frozen=True)
class Plan:
    user_instruction: str
    steps: tuple[PlanningStep, ...]
    risk_level: str = "low"
    requires_approval: bool = False
    summary: str = ""


def build_planning_input(user_instruction: str, *, prompt: str | None = None) -> str:
    base_prompt = (prompt or DEFAULT_PLANNING_PROMPT).strip()
    return (
        f"{base_prompt}\n\n"
        "Create a plan for this user instruction. Return JSON only with keys: "
        "risk_level, requires_approval, summary, steps. Each step must include an instruction. "
        f"\n\nUser instruction: {user_instruction.strip()}"
    )


def _response_text(response: Any) -> str:
    output_text = str(attr(response, "output_text", "") or "").strip()
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in attr(response, "output", []) or []:
        for part in attr(item, "content", []) or []:
            text = attr(part, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def parse_planning_response(response: Any, *, user_instruction: str) -> Plan:
    text = _response_text(response)
    if not text:
        raise RuntimeError("planning response did not contain JSON text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"planning response was not valid JSON: {exc}") from exc

    steps: list[PlanningStep] = []
    for index, raw_step in enumerate(data.get("steps", []) or [], start=1):
        if not isinstance(raw_step, dict):
            continue
        instruction = str(raw_step.get("instruction", "")).strip()
        if not instruction:
            continue
        title = str(raw_step.get("title", "")).strip() or f"Step {index}"
        expected = str(raw_step.get("expected_result", "")).strip()
        steps.append(PlanningStep(title=title, instruction=instruction, expected_result=expected))

    risk_level = str(data.get("risk_level", "low") or "low")
    requires_approval = bool(data.get("requires_approval", False))
    summary = str(data.get("summary", "") or "")
    if not steps and (requires_approval or risk_level.lower() == "high"):
        steps.append(
            PlanningStep(
                title="Approval required",
                instruction=user_instruction,
                expected_result=summary,
            )
        )
    if not steps:
        raise RuntimeError("planning response contained no executable steps")

    return Plan(
        user_instruction=user_instruction,
        steps=tuple(steps),
        risk_level=risk_level,
        requires_approval=requires_approval,
        summary=summary,
    )


@dataclass
class PlanningService:
    client: Any
    model: str
    prompt: str | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "PlanningService":
        openai_cfg = config.get("openai", {})
        api_key_file = str(openai_cfg.get("api_key_file", "/home/nama/openai-api-key.txt"))
        api_key_env = str(openai_cfg.get("api_key_env", DEFAULT_API_KEY_ENV))
        api_key = ""
        from pathlib import Path
        import os

        path = Path(api_key_file)
        if path.exists():
            api_key = path.read_text(encoding="utf-8").strip()
        if not api_key:
            api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"missing API key file: {api_key_file}")

        return cls(
            client=OpenAI(api_key=api_key, timeout=float(openai_cfg.get("api_timeout", 60.0))),
            model=str(openai_cfg.get("planning_model", openai_cfg.get("model", DEFAULT_MODEL))),
            prompt=str(openai_cfg.get("planning_prompt", "") or "").strip() or None,
        )

    def create_plan(self, user_instruction: str) -> Plan:
        response = self.client.responses.create(
            model=self.model,
            input=build_planning_input(user_instruction, prompt=self.prompt),
            text={"format": {"type": "json_schema", **PLANNING_JSON_SCHEMA}},
            reasoning={"effort": "medium"},
        )
        return parse_planning_response(response, user_instruction=user_instruction)
