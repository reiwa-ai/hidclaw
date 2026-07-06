from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pico_hid_bridge.planning import (
    DEFAULT_PLANNING_PROMPT,
    PlanningStep,
    build_planning_input,
    parse_planning_response,
)


def test_planning_prompt_requests_generic_json_steps() -> None:
    prompt = build_planning_input("Research HTTP status codes and summarize them.")

    assert DEFAULT_PLANNING_PROMPT in prompt
    assert "Return JSON only" in prompt
    assert "steps" in prompt
    assert "instruction" in prompt
    assert "Do not specialize for test scenarios" in prompt
    assert "Research HTTP status codes" in prompt


def test_planning_prompt_handles_generic_impossible_and_unreachable_requests() -> None:
    prompt = DEFAULT_PLANNING_PROMPT

    assert "division by zero" in prompt
    assert "localhost" in prompt
    assert "loopback" in prompt
    assert "short ASCII" in prompt


def test_parse_planning_response_accepts_json_output_text() -> None:
    response = {
        "output_text": (
            '{"steps": ['
            '{"title": "Open browser", "instruction": "Open a browser.", "expected_result": "Browser is open"},'
            '{"title": "Search", "instruction": "Search for HTTP status codes.", "expected_result": "Results are visible"}'
            "], \"risk_level\": \"low\", \"requires_approval\": false}"
        )
    }

    plan = parse_planning_response(response, user_instruction="Research HTTP status codes.")

    assert plan.user_instruction == "Research HTTP status codes."
    assert plan.risk_level == "low"
    assert plan.requires_approval is False
    assert plan.steps == (
        PlanningStep("Open browser", "Open a browser.", "Browser is open"),
        PlanningStep("Search", "Search for HTTP status codes.", "Results are visible"),
    )


def test_parse_planning_response_accepts_high_risk_plan_without_steps() -> None:
    response = {
        "output_text": (
            '{"steps": [], "risk_level": "high", "requires_approval": true, '
            '"summary": "Installing applications requires approval."}'
        )
    }

    plan = parse_planning_response(response, user_instruction="Install an application.")

    assert plan.requires_approval is True
    assert plan.risk_level == "high"
    assert plan.steps == (
        PlanningStep(
            "Approval required",
            "Install an application.",
            "Installing applications requires approval.",
        ),
    )


@dataclass
class FakeResponses:
    calls: list[dict[str, Any]]

    def create(self, **kwargs: Any) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"output_text": '{"steps": [{"instruction": "Open Calculator."}]}'}


def test_planning_service_uses_json_schema_and_thinking_when_available() -> None:
    from pico_hid_bridge.planning import PlanningService

    responses = FakeResponses([])
    client = type("FakeClient", (), {"responses": responses})()
    service = PlanningService(client=client, model="planner-model")

    plan = service.create_plan("Open Calculator and calculate 2+2.")

    call = responses.calls[-1]
    assert call["model"] == "planner-model"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["name"] == "pc_operation_plan"
    assert "schema" in call["text"]["format"]
    assert "json_schema" not in call["text"]["format"]
    assert call["reasoning"]["effort"] == "medium"
    assert plan.steps[0].instruction == "Open Calculator."
