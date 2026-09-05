from __future__ import annotations

from pathlib import Path

from pico_hid_bridge.prompt_assets import DEFAULT_COMPUTER_PROMPT, get_prompt_text, parse_prompt_yaml


def test_parse_prompt_yaml_reads_block_scalars() -> None:
    text = (
        "computer_use_system: |-\n"
        "  line one\n"
        "  line two\n"
        "planning_system: |-\n"
        "  step one\n"
    )

    parsed = parse_prompt_yaml(text)

    assert parsed["computer_use_system"] == "line one\nline two"
    assert parsed["planning_system"] == "step one"


def test_get_prompt_text_prefers_prompts_file_when_inline_prompt_is_missing(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts.yaml"
    prompt_path.write_text(
        "computer_use_system: |-\n"
        "  custom computer prompt\n"
        "planning_system: |-\n"
        "  custom planning prompt\n"
        "intent_system: |-\n"
        "  custom intent prompt\n",
        encoding="utf-8",
    )
    config = {"openai": {"prompts_file": str(prompt_path)}}

    assert get_prompt_text(config, "computer_prompt") == "custom computer prompt"
    assert get_prompt_text(config, "planning_prompt") == "custom planning prompt"


def test_get_prompt_text_prefers_prompts_file_over_default_inline_prompt(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts.yaml"
    prompt_path.write_text(
        "computer_use_system: |-\n"
        "  prompt from file\n",
        encoding="utf-8",
    )
    config = {
        "openai": {
            "prompts_file": str(prompt_path),
            "computer_prompt": DEFAULT_COMPUTER_PROMPT,
        }
    }

    assert get_prompt_text(config, "computer_prompt") == "prompt from file"


def test_get_prompt_text_keeps_explicit_inline_override(tmp_path: Path) -> None:
    prompt_path = tmp_path / "prompts.yaml"
    prompt_path.write_text(
        "computer_use_system: |-\n"
        "  prompt from file\n",
        encoding="utf-8",
    )
    config = {
        "openai": {
            "prompts_file": str(prompt_path),
            "computer_prompt": "prompt from inline override",
        }
    }

    assert get_prompt_text(config, "computer_prompt") == "prompt from inline override"
