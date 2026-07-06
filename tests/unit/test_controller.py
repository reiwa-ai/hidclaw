from __future__ import annotations

import argparse

from pico_hid_bridge.cli import controller


def test_controller_action_delay_for_type_scales_with_text_length() -> None:
    args = argparse.Namespace(inter_action_delay=0.25, type_action_delay_per_char=0.08)

    assert controller.action_delay_seconds({"type": "type", "text": "chrome"}, args) == 0.48


def test_controller_action_delay_uses_base_for_keypress() -> None:
    args = argparse.Namespace(inter_action_delay=0.25, type_action_delay_per_char=0.08)

    assert controller.action_delay_seconds({"type": "keypress", "keys": ["ENTER"]}, args) == 0.25


def test_cli_planning_requires_approval_for_high_risk_plan(monkeypatch, tmp_path, capsys) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(PlanningStep("Save", "Save a file.", "File saved"),),
                risk_level="high",
                requires_approval=True,
            )

    monkeypatch.setattr(controller, "PlanningService", FakePlanningService)

    config_path = tmp_path / "config.toml"
    config_path.write_text("[openai]\napi_key_env = \"OPENAI_API_KEY\"\n", encoding="utf-8")

    result = controller.main(["--planning", "--config", str(config_path), "save a file"])

    captured = capsys.readouterr()
    assert result == 3
    assert "approval required" in captured.err


def test_cli_planning_with_approval_executes_planned_steps(monkeypatch, tmp_path) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    calls: list[list[str]] = []

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(PlanningStep("Search", "Open browser."), PlanningStep("Write", "Write summary.")),
                risk_level="high",
                requires_approval=True,
            )

    monkeypatch.setattr(controller, "PlanningService", FakePlanningService)
    monkeypatch.setattr(controller, "main", lambda argv: calls.append(argv) or 0)

    config_path = tmp_path / "config.toml"
    config_path.write_text("[openai]\napi_key_env = \"OPENAI_API_KEY\"\n", encoding="utf-8")

    result = controller.run_planned_cli(["--planning", "--approve-risk", "--config", str(config_path), "do task"])

    assert result == 0
    assert [call[-1] for call in calls] == ["Open browser.", "Write summary."]
    assert all("--planning" not in call for call in calls)
    assert all("--approve-risk" not in call for call in calls)
