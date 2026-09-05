from __future__ import annotations

import pytest

from pico_hid_bridge.intent import analyze_user_intent, build_intent_prompt_block, combine_risk_levels


def test_intent_analysis_detects_research_then_summary_flow() -> None:
    intent = analyze_user_intent("Research Raspberry Pi Pico HID keyboard emulation and summarize it in Notepad.")

    assert intent.requires_planning is True
    assert "browser" in intent.target_apps
    assert "text editor" in intent.target_apps
    assert len(intent.subgoals) >= 2
    assert any("summary" in criterion.lower() for criterion in intent.success_criteria)


def test_intent_analysis_marks_sensitive_mutation_as_high_risk() -> None:
    intent = analyze_user_intent("Open a text editor, write hello, and save the file.")

    assert intent.risk_level == "high"
    assert intent.requires_approval is True
    assert any("state-changing" in flag.lower() for flag in intent.safety_flags)


def test_build_intent_prompt_block_contains_goal_apps_and_risk() -> None:
    intent = analyze_user_intent("Open Calculator and calculate 2+2.")

    block = build_intent_prompt_block(intent, heading="Execution context")

    assert "Execution context:" in block
    assert "Goal:" in block
    assert "Likely target apps:" in block
    assert "Risk:" in block


def test_combine_risk_levels_returns_higher_risk() -> None:
    assert combine_risk_levels("low", "high") == "high"
    assert combine_risk_levels("medium", "low") == "medium"


@pytest.mark.parametrize(
    ("instruction", "expected_apps", "requires_planning", "risk_level", "requires_approval"),
    [
        (
            "Open Calculator and read the visible result without saving or changing settings.",
            ("calculator",),
            False,
            "low",
            False,
        ),
        (
            "Calculate 42 times 17, then open a text editor and write Result: 714.",
            ("text editor", "calculator"),
            True,
            "low",
            False,
        ),
        (
            "Open a browser and navigate to http://127.0.0.1:9/expected-failure-test.",
            ("browser",),
            True,
            "medium",
            False,
        ),
    ],
)
def test_intent_analysis_covers_safe_multistep_and_loopback_cases(
    instruction: str,
    expected_apps: tuple[str, ...],
    requires_planning: bool,
    risk_level: str,
    requires_approval: bool,
) -> None:
    intent = analyze_user_intent(instruction)

    assert intent.target_apps == expected_apps
    assert intent.requires_planning is requires_planning
    assert intent.risk_level == risk_level
    assert intent.requires_approval is requires_approval


def test_intent_analysis_marks_loopback_targets_as_unverified() -> None:
    intent = analyze_user_intent("Open a browser and navigate to http://127.0.0.1:9/expected-failure-test.")

    assert any("loopback" in flag.lower() or "localhost" in flag.lower() for flag in intent.safety_flags)
    assert any("reachability error" in criterion.lower() for criterion in intent.success_criteria)
