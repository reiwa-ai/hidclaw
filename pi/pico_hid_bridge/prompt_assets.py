"""Editable prompt assets for the Raspberry Pi side agent."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .paths import resolve_path


DEFAULT_PROMPTS_FILE = Path("pi/prompts.yaml")

DEFAULT_PROMPTS: dict[str, str] = {
    "computer_use_system": (
        "You are controlling a physical Windows PC through an HDMI capture and a limited "
        "USB HID keyboard/mouse bridge. Complete the user's goal by making the smallest safe "
        "visible progress on each turn. Interpret the request before acting: identify the target "
        "application, the next visible milestone, and the success condition. Use a keyboard-first "
        "strategy. Prefer screenshot, keypress, type, or wait. Avoid mouse move, click, and "
        "double_click unless keyboard operation is clearly impossible. Do not use drag or scroll "
        "actions. When opening an application, prefer WIN+R, type the program name, and press "
        "ENTER. When switching windows, prefer ALT+TAB or other keyboard shortcuts. Use only "
        "supported keypress names: ENTER, ESC, BACKSPACE, TAB, SPACE, DELETE, F1-F12, letters, "
        "digits, and WIN/CTRL/SHIFT/ALT combinations. Do not use PAGEUP, PAGEDOWN, HOME, END, "
        "or arrow keys. Keep type actions short ASCII and avoid multiline type actions when "
        "possible. Use ASCII English input for typed text. Never answer the task in natural "
        "language; use computer tool actions until the requested PC state is achieved."
    ),
    "planning_system": (
        "You are a planning layer for a physical Windows PC controlled through a Computer Use API. "
        "Convert one user request into a short ordered list of concrete observable instructions for "
        "a separate executor. First infer the user's real goal, target applications, and visible "
        "success criteria. Do not produce low-level HID commands. Do not mention tests, scenarios, "
        "or implementation internals. Do not specialize for test scenarios. Keep steps generic, "
        "observable, and safe. Prefer keyboard-friendly Windows workflows and use WIN+R to open "
        "apps when appropriate. Split multi-goal requests into short milestones. Each step should "
        "achieve one visible state change. Avoid steps that depend on drag, scroll, PAGEUP, "
        "PAGEDOWN, HOME, END, or arrow keys when another path exists. When a step asks to write "
        "or summarize text, keep it to one short ASCII sentence unless the user explicitly asks for "
        "more. Mathematically undefined operations such as division by zero are impossible. Do not "
        "plan navigation to localhost or loopback URLs unless the user explicitly states that a "
        "reachable service is running. Do not save, delete, send, post, purchase, install, change "
        "settings, enter passwords, or enter personal data without marking the plan high risk. If "
        "the request is unsafe, impossible, or likely unsupported by the current HID bridge, set "
        "requires_approval=true or risk_level=high. Return JSON only."
    ),
    "intent_system": (
        "Interpret the user's PC-operation request into a normalized goal, likely applications, "
        "visible success criteria, and safety notes. Favor concise structured summaries over free-"
        "form prose."
    ),
}

DEFAULT_COMPUTER_PROMPT = DEFAULT_PROMPTS["computer_use_system"]
DEFAULT_PLANNING_PROMPT = DEFAULT_PROMPTS["planning_system"]
DEFAULT_INTENT_PROMPT = DEFAULT_PROMPTS["intent_system"]

_PROMPT_NAME_TO_ASSET_KEY = {
    "computer_prompt": "computer_use_system",
    "planning_prompt": "planning_system",
    "intent_prompt": "intent_system",
}


def parse_prompt_yaml(text: str) -> dict[str, str]:
    """Parse a tiny top-level YAML subset used by prompts.yaml."""

    prompts: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key is not None:
            prompts[current_key] = "\n".join(current_lines).strip()
        current_key = None
        current_lines = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if current_key is None:
            if not stripped or stripped.startswith("#"):
                continue
            if raw_line[:1].isspace():
                raise ValueError("prompt YAML only supports top-level keys")
            key, separator, rest = raw_line.partition(":")
            if not separator:
                raise ValueError(f"invalid prompt YAML line: {raw_line!r}")
            if rest.strip() not in {"|", "|-"}:
                raise ValueError("prompt YAML values must use block scalars")
            current_key = key.strip()
            current_lines = []
            continue

        if raw_line.startswith("  "):
            current_lines.append(raw_line[2:])
            continue
        if not stripped:
            flush()
            continue

        flush()
        key, separator, rest = raw_line.partition(":")
        if not separator:
            raise ValueError(f"invalid prompt YAML line: {raw_line!r}")
        if rest.strip() not in {"|", "|-"}:
            raise ValueError("prompt YAML values must use block scalars")
        current_key = key.strip()
        current_lines = []

    flush()
    return prompts


def load_prompt_assets(path: str | Path | None = None) -> dict[str, str]:
    prompt_path = resolve_path(path or DEFAULT_PROMPTS_FILE)
    if not prompt_path.exists():
        return dict(DEFAULT_PROMPTS)

    prompts = dict(DEFAULT_PROMPTS)
    loaded = parse_prompt_yaml(prompt_path.read_text(encoding="utf-8"))
    for key, value in loaded.items():
        if key in prompts and value.strip():
            prompts[key] = value.strip()
    return prompts


@lru_cache(maxsize=8)
def _cached_prompt_assets(path: str) -> dict[str, str]:
    return load_prompt_assets(Path(path))


def get_prompt_text(config: dict[str, object], prompt_name: str) -> str:
    openai_cfg = config.get("openai", {}) if isinstance(config, dict) else {}
    asset_key = _PROMPT_NAME_TO_ASSET_KEY[prompt_name]
    default_prompt = DEFAULT_PROMPTS[asset_key].strip()
    inline = ""
    if isinstance(openai_cfg, dict):
        inline = str(openai_cfg.get(prompt_name, "") or "").strip()
        prompt_file = openai_cfg.get("prompts_file", DEFAULT_PROMPTS_FILE)
    else:
        prompt_file = DEFAULT_PROMPTS_FILE

    resolved = resolve_path(Path(str(prompt_file)))
    if resolved.exists():
        prompts = _cached_prompt_assets(str(resolved))
        file_prompt = str(prompts.get(asset_key, "")).strip()
        if file_prompt and (not inline or inline == default_prompt):
            return file_prompt

    if inline:
        return inline
    return DEFAULT_PROMPTS[asset_key]
