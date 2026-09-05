from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pico_hid_bridge.planning import (
    DEFAULT_PLANNING_PROMPT,
    PlanningStep,
    build_planning_input,
    plan_from_intent,
    parse_planning_response,
)
from pico_hid_bridge.intent import analyze_user_intent


def test_planning_prompt_requests_generic_json_steps() -> None:
    prompt = build_planning_input("Research HTTP status codes and summarize them.")

    assert DEFAULT_PLANNING_PROMPT in prompt
    assert "Return JSON only" in prompt
    assert "steps" in prompt
    assert "instruction" in prompt
    assert "Do not specialize for test scenarios" in prompt
    assert "Interpreted request:" in prompt
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
            '{"goal": "Open browser and search.", "success_criteria": ["Browser is open"], "target_apps": ["browser"], "steps": ['
            '{"title": "Open browser", "instruction": "Open a browser.", "expected_result": "Browser is open"},'
            '{"title": "Search", "instruction": "Search for HTTP status codes.", "expected_result": "Results are visible"}'
            "], \"risk_level\": \"low\", \"requires_approval\": false}"
        )
    }

    intent = analyze_user_intent("Research HTTP status codes.")
    plan = parse_planning_response(response, user_instruction="Research HTTP status codes.", intent=intent)

    assert plan.user_instruction == "Research HTTP status codes."
    assert plan.risk_level == "low"
    assert plan.requires_approval is False
    assert plan.goal == "Open browser and search."
    assert plan.target_apps == ("browser",)
    assert plan.steps == (
        PlanningStep("Open browser", "Open a browser.", "Browser is open", ""),
        PlanningStep("Search", "Search for HTTP status codes.", "Results are visible", ""),
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


def test_parse_planning_response_falls_back_to_intent_when_steps_missing() -> None:
    intent = analyze_user_intent("Open browser and search for HTTP status codes.")
    response = {"output_text": '{"steps": [], "risk_level": "low", "requires_approval": false}'}

    plan = parse_planning_response(response, user_instruction=intent.user_instruction, intent=intent)

    assert plan.steps
    assert plan.goal


def test_plan_from_intent_builds_fallback_steps() -> None:
    intent = analyze_user_intent("Research Raspberry Pi Pico and summarize it in Notepad.")

    plan = plan_from_intent(intent)

    assert len(plan.steps) >= 2
    assert plan.summary == intent.normalized_goal


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


def test_planning_service_falls_back_to_intent_when_json_is_invalid() -> None:
    from pico_hid_bridge.planning import PlanningService

    class InvalidJsonResponses:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def create(self, **kwargs: Any) -> dict[str, object]:
            self.calls.append(kwargs)
            return {"output_text": "not json"}

    client = type("FakeClient", (), {"responses": InvalidJsonResponses()})()
    service = PlanningService(client=client, model="planner-model")

    plan = service.create_plan("Open browser and search for HTTP status codes.")

    assert plan.steps
    assert plan.goal


def test_parse_planning_response_upgrades_model_output_for_sensitive_save_request() -> None:
    response = {
        "output_text": (
            '{"goal": "Save a file.", "risk_level": "low", "requires_approval": false, '
            '"steps": [{"title": "Write", "instruction": "Write hello in a text editor.", '
            '"expected_result": "hello is visible", "application": "text editor"}]}'
        )
    }

    intent = analyze_user_intent("Open a text editor, write hello, and save the file.")
    plan = parse_planning_response(
        response,
        user_instruction=intent.user_instruction,
        intent=intent,
    )

    assert plan.risk_level == "high"
    assert plan.requires_approval is True
    assert plan.target_apps == ("text editor",)
    assert plan.steps[0].application == "text editor"


def test_planning_service_fallback_keeps_loopback_warning_context() -> None:
    from pico_hid_bridge.planning import PlanningService

    class InvalidJsonResponses:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def create(self, **kwargs: Any) -> dict[str, object]:
            self.calls.append(kwargs)
            return {"output_text": "not json"}

    client = type("FakeClient", (), {"responses": InvalidJsonResponses()})()
    service = PlanningService(client=client, model="planner-model")

    plan = service.create_plan("Open a browser and navigate to http://127.0.0.1:9/expected-failure-test.")

    assert plan.risk_level == "medium"
    assert plan.requires_approval is False
    assert any("reachability error" in step.expected_result.lower() for step in plan.steps)
