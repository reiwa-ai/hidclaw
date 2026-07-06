"""Configuration loading for the Raspberry Pi side."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .computer_use import DEFAULT_COMPUTER_PROMPT
from .hid import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_TIMEOUT
from .planning import DEFAULT_PLANNING_PROMPT

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Raspberry Pi OS uses Python 3.11+
    tomllib = None


DEFAULT_CONFIG: dict[str, Any] = {
    "app": {
        "mode": "web",
        "bind_host": "127.0.0.1",
        "bind_port": 8080,
        "default_planning": False,
        "approval_timeout_seconds": 300.0,
        "runtime_dir": "runtime",
    },
    "capture": {
        "device": "/dev/video0",
        "width": 0,
        "height": 0,
        "fps": 0,
        "warmup_frames": 60,
        "min_brightness": 5.0,
        "ready_timeout": 5.0,
        "save_width": 1280,
        "jpeg_quality": 80,
    },
    "hid": {
        "port": DEFAULT_PORT,
        "baudrate": DEFAULT_BAUDRATE,
        "timeout": DEFAULT_TIMEOUT,
    },
    "openai": {
        "api_key_file": "/home/nama/openai-api-key.txt",
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-5.5",
        "api_timeout": 60.0,
        "max_action_turns": 5,
        "computer_prompt": DEFAULT_COMPUTER_PROMPT,
        "planning_model": "gpt-5.5",
        "planning_prompt": DEFAULT_PLANNING_PROMPT,
    },
    "logs": {
        "database": "runtime/app.db",
        "screenshot_dir": "runtime/screenshots",
        "max_memory_logs": 100,
        "max_screenshots": 5000,
        "max_storage_mb": 1024,
    },
    "token_budget": {
        "baseline_tokens_per_operation": 1000,
        "max_tokens_per_operation": 20000,
        "max_tokens_per_step": 20000,
        "max_tokens_per_plan": 100000,
        "max_tokens_per_day": 200000,
    },
    "email": {
        "enabled": False,
        "delivery": "smtp",
        "smtp_account_file": "/home/nama/mail-send-vert.txt",
        "to_addrs": [],
        "min_interval_sec": 300.0,
        "rate_limit_per_hour": 10,
        "attachment_limit_mb": 10,
    },
    "discord": {
        "enabled": False,
        "token_file": "/home/nama/discord-api-key.txt",
        "bot_name": "AgentDev",
        "bot_user_id": "",
        "guild_id": "",
        "channel_id": "",
        "allowed_guild_ids": [],
        "allowed_channel_ids": [],
        "allowed_user_ids": [],
        "poll_interval_sec": 5.0,
        "poll_limit": 20,
        "skip_existing_on_startup": True,
        "max_command_age_sec": 60.0,
        "api_timeout": 15.0,
        "rate_limit_per_hour": 20,
        "attachment_limit_mb": 8,
    },
}


def merge_config(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for section, values in overrides.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section].update(values)
        else:
            merged[section] = values
    return merged


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return deepcopy(DEFAULT_CONFIG)

    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")

    if tomllib is None:
        raise RuntimeError("TOML config requires Python 3.11+")

    with path.open("rb") as file:
        return merge_config(DEFAULT_CONFIG, tomllib.load(file))
