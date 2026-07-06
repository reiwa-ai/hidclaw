from __future__ import annotations

from pathlib import Path

from pico_hid_bridge.config import DEFAULT_CONFIG, load_config


def test_example_config_has_no_secret_values() -> None:
    text = Path("config/example.toml").read_text(encoding="utf-8").lower()
    forbidden = ("sk-", "xoxb-", "password", "secret", "token =")
    assert not any(value in text for value in forbidden)


def test_email_config_defaults_disabled() -> None:
    assert DEFAULT_CONFIG["email"]["enabled"] is False
    assert DEFAULT_CONFIG["email"]["delivery"] == "smtp"
    assert DEFAULT_CONFIG["email"]["smtp_account_file"] == "/home/nama/mail-send-vert.txt"
    assert DEFAULT_CONFIG["email"]["to_addrs"] == []
    assert DEFAULT_CONFIG["email"]["min_interval_sec"] > 0


def test_discord_config_defaults_disabled() -> None:
    discord = DEFAULT_CONFIG["discord"]

    assert discord["enabled"] is False
    assert discord["token_file"] == "/home/nama/discord-api-key.txt"
    assert discord["bot_name"] == "AgentDev"
    assert discord["max_command_age_sec"] <= 60
    assert discord["skip_existing_on_startup"] is True
    assert discord["allowed_guild_ids"] == []
    assert discord["allowed_channel_ids"] == []
    assert discord["allowed_user_ids"] == []


def test_storage_limit_config_is_present() -> None:
    assert DEFAULT_CONFIG["logs"]["max_storage_mb"] > 0


def test_approval_timeout_config_is_present() -> None:
    assert DEFAULT_CONFIG["app"]["approval_timeout_seconds"] > 0


def test_token_budget_config_is_present() -> None:
    token_budget = DEFAULT_CONFIG["token_budget"]

    assert token_budget["baseline_tokens_per_operation"] > 0
    assert token_budget["max_tokens_per_operation"] > 0
    assert token_budget["max_tokens_per_step"] > 0
    assert token_budget["max_tokens_per_plan"] > 0
    assert token_budget["max_tokens_per_day"] > 0


def test_default_openai_prompt_prefers_keyboard_shortcuts() -> None:
    prompt = DEFAULT_CONFIG["openai"]["computer_prompt"]
    assert "keyboard-first" in prompt
    assert "WIN+R" in prompt
    assert "ALT+TAB" in prompt
    assert "Do not use PAGEUP, PAGEDOWN, HOME, END, or arrow keys" in prompt
    assert "Never answer the task in natural language" in prompt
    assert "Do not use drag or scroll actions" in prompt


def test_default_openai_planning_settings_are_present() -> None:
    openai = DEFAULT_CONFIG["openai"]
    assert openai["planning_model"]
    assert "Return JSON only" in openai["planning_prompt"]
    assert "Do not specialize for test scenarios" in openai["planning_prompt"]


def test_runtime_dir_can_be_overridden_for_tests(tmp_path: Path) -> None:
    config_path = tmp_path / "test.toml"
    config_path.write_text('[app]\nruntime_dir = "runtime/test"\n', encoding="utf-8")
    config = load_config(config_path)
    assert config["app"]["runtime_dir"] == "runtime/test"
