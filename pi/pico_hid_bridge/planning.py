"""Planning wrapper for turning user requests into executable step instructions."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from openai import OpenAI

from .computer_use import DEFAULT_API_KEY_ENV, DEFAULT_MODEL, attr
from .intent import AgentIntent, analyze_user_intent, build_intent_prompt_block, combine_risk_levels
from .prompt_assets import DEFAULT_PLANNING_PROMPT, get_prompt_text


PLANNING_JSON_SCHEMA: dict[str, Any] = {
    "name": "pc_operation_plan",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "goal": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "requires_approval": {"type": "boolean"},
            "summary": {"type": "string"},
            "success_criteria": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            "assumptions": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            "target_apps": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
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
                        "application": {"type": "string"},
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
    application: str = ""


@dataclass(frozen=True)
class Plan:
    user_instruction: str
    steps: tuple[PlanningStep, ...]
    risk_level: str = "low"
    requires_approval: bool = False
    summary: str = ""
    goal: str = ""
    success_criteria: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    target_apps: tuple[str, ...] = ()


def build_planning_input(
    user_instruction: str,
    *,
    prompt: str | None = None,
    intent: AgentIntent | None = None,
) -> str:
    base_prompt = (prompt or DEFAULT_PLANNING_PROMPT).strip()
    resolved_intent = intent or analyze_user_intent(user_instruction)
    return "\n\n".join(
        [
            base_prompt,
            (
                "Create a plan for this user instruction. Return JSON only with keys: "
                "goal, summary, risk_level, requires_approval, success_criteria, assumptions, "
                "target_apps, steps. Each step must include an instruction."
            ),
            build_intent_prompt_block(resolved_intent, heading="Interpreted request"),
            f"User instruction: {resolved_intent.user_instruction}",
        ]
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


def _normalize_text_list(raw_value: Any, *, max_items: int = 6) -> tuple[str, ...]:
    items: list[str] = []
    for raw_item in raw_value or []:
        text = str(raw_item or "").strip()
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return tuple(items)


def plan_from_intent(intent: AgentIntent) -> Plan:
    steps: list[PlanningStep] = []
    if len(intent.subgoals) > 1:
        for index, subgoal in enumerate(intent.subgoals, start=1):
            expected = intent.success_criteria[min(index - 1, len(intent.success_criteria) - 1)] if intent.success_criteria else ""
            steps.append(PlanningStep(title=f"Step {index}", instruction=subgoal, expected_result=expected))
    else:
        expected = intent.success_criteria[0] if intent.success_criteria else ""
        steps.append(PlanningStep(title="Step 1", instruction=intent.user_instruction, expected_result=expected))

    return Plan(
        user_instruction=intent.user_instruction,
        steps=tuple(steps),
        risk_level=intent.risk_level,
        requires_approval=intent.requires_approval,
        summary=intent.normalized_goal,
        goal=intent.normalized_goal,
        success_criteria=intent.success_criteria,
        target_apps=intent.target_apps,
    )


def merge_plan_with_intent(plan: Plan, intent: AgentIntent) -> Plan:
    return Plan(
        user_instruction=plan.user_instruction or intent.user_instruction,
        steps=plan.steps or plan_from_intent(intent).steps,
        risk_level=combine_risk_levels(plan.risk_level, intent.risk_level),
        requires_approval=plan.requires_approval or intent.requires_approval,
        summary=plan.summary or intent.normalized_goal,
        goal=plan.goal or intent.normalized_goal,
        success_criteria=plan.success_criteria or intent.success_criteria,
        assumptions=plan.assumptions,
        target_apps=plan.target_apps or intent.target_apps,
    )


def parse_planning_response(
    response: Any,
    *,
    user_instruction: str,
    intent: AgentIntent | None = None,
) -> Plan:
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
        application = str(raw_step.get("application", "")).strip()
        steps.append(PlanningStep(title=title, instruction=instruction, expected_result=expected, application=application))

    risk_level = str(data.get("risk_level", "low") or "low")
    requires_approval = bool(data.get("requires_approval", False))
    summary = str(data.get("summary", "") or "")
    goal = str(data.get("goal", "") or "")
    success_criteria = _normalize_text_list(data.get("success_criteria"))
    assumptions = _normalize_text_list(data.get("assumptions"))
    target_apps = _normalize_text_list(data.get("target_apps"))
    if not steps and (requires_approval or risk_level.lower() == "high"):
        steps.append(
            PlanningStep(
                title="Approval required",
                instruction=user_instruction,
                expected_result=summary,
            )
        )
    if not steps and intent is not None:
        return plan_from_intent(intent)
    if not steps:
        raise RuntimeError("planning response contained no executable steps")

    plan = Plan(
        user_instruction=user_instruction,
        steps=tuple(steps),
        risk_level=risk_level,
        requires_approval=requires_approval,
        summary=summary,
        goal=goal,
        success_criteria=success_criteria,
        assumptions=assumptions,
        target_apps=target_apps,
    )
    return merge_plan_with_intent(plan, intent) if intent is not None else plan


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
            prompt=get_prompt_text(config, "planning_prompt"),
        )

    def create_plan(self, user_instruction: str) -> Plan:
        intent = analyze_user_intent(user_instruction)
        response = self.client.responses.create(
            model=self.model,
            input=build_planning_input(user_instruction, prompt=self.prompt, intent=intent),
            text={"format": {"type": "json_schema", **PLANNING_JSON_SCHEMA}},
            reasoning={"effort": "medium"},
        )
        try:
            return parse_planning_response(response, user_instruction=user_instruction, intent=intent)
        except RuntimeError:
            return plan_from_intent(intent)
