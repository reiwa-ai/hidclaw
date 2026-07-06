from __future__ import annotations

import importlib


def test_webui_entrypoint_reexports_create_app() -> None:
    module = importlib.import_module("app")

    assert callable(module.create_app)
    assert callable(module.main)
    assert callable(module.run_discord_mode)
    assert module.parse_args(["--mode", "discord"]).mode == "discord"


def test_controller_entrypoint_reexports_cli_helpers() -> None:
    module = importlib.import_module("controller")

    assert callable(module.action_delay_seconds)
    assert callable(module.main)


def test_e2e_entrypoints_reexport_case_and_runner_symbols() -> None:
    cases = importlib.import_module("e2e_cases")
    runner = importlib.import_module("e2e_hid_runner")
    model = importlib.import_module("e2e_model")
    suite = importlib.import_module("run_e2e_suite")

    assert "open_browser_e2e" in cases.CASES
    assert callable(runner.run_case)
    assert hasattr(model, "E2ETestCase")
    assert callable(suite.parse_args)
