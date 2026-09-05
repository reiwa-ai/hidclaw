"""Deterministic intent analysis for the Pi-side PC control agent."""

from __future__ import annotations

from dataclasses import dataclass
import re


RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}

_TARGET_APP_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("browser", ("browser", "chrome", "edge", "firefox", "search", "research", "google", "wikipedia", "arxiv", "web")),
    ("text editor", ("notepad", "text editor", "editor", "memo", "note", "notes")),
    ("calculator", ("calculator", "calculate", "calc")),
    ("paint", ("paint", "draw", "image")),
    ("file explorer", ("explorer", "folder", "directory", "file picker")),
    ("settings", ("open settings", "windows settings", "system settings", "control panel", "preferences", "options")),
    ("terminal", ("command prompt", "cmd", "powershell", "terminal", "shell")),
)

_HIGH_RISK_PATTERNS = (
    "delete",
    "remove",
    "erase",
    "format",
    "install",
    "uninstall",
    "sign in",
    "login",
    "log in",
    "password",
    "credential",
    "secret",
    "2fa",
    "payment",
    "pay",
    "purchase",
    "buy",
    "checkout",
    "send",
    "post",
    "publish",
    "submit",
    "upload",
    "save",
    "overwrite",
    "replace",
    "change settings",
)

_MEDIUM_RISK_PATTERNS = (
    "download",
    "edit file",
    "modify file",
    "rename",
    "move file",
    "copy file",
)

_UNSUPPORTED_PATTERNS = (
    ("mouse drag", ("drag", "freehand", "scroll wheel")),
    ("absolute pointer control", ("absolute coordinates", "move the mouse to x", "cursor to x")),
)

_SEQUENCE_SPLIT_RE = re.compile(
    r"\b(?:and then|then|after that|next|finally|before that|afterward)\b|[.;]\s+",
    re.IGNORECASE,
)

_LOOPBACK_RE = re.compile(r"\b(?:localhost|127(?:\.\d{1,3}){3})\b", re.IGNORECASE)
_RUNNING_LOCAL_SERVICE_RE = re.compile(
    r"\b(?:service|server|app|site)\b.*\b(?:is|already)\s+running\b|\brunning on localhost\b|\brunning on 127(?:\.\d{1,3}){3}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentIntent:
    user_instruction: str
    normalized_goal: str
    target_apps: tuple[str, ...] = ()
    subgoals: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    execution_notes: tuple[str, ...] = ()
    safety_flags: tuple[str, ...] = ()
    requires_planning: bool = False
    risk_level: str = "low"
    requires_approval: bool = False


def combine_risk_levels(left: str, right: str) -> str:
    left_rank = RISK_LEVEL_ORDER.get(left.lower(), 0)
    right_rank = RISK_LEVEL_ORDER.get(right.lower(), 0)
    return left if left_rank >= right_rank else right


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE) is not None


def analyze_user_intent(instruction: str) -> AgentIntent:
    normalized = " ".join(instruction.strip().split())
    lowered = normalized.lower()
    target_apps = detect_target_apps(lowered)
    subgoals = infer_subgoals(normalized, lowered, target_apps)
    risk_level, requires_approval, safety_flags = infer_risk(lowered)
    execution_notes = infer_execution_notes(lowered, target_apps, subgoals, safety_flags)
    success_criteria = infer_success_criteria(lowered, target_apps, subgoals)
    requires_planning = infer_requires_planning(lowered, target_apps, subgoals, risk_level)
    normalized_goal = infer_normalized_goal(normalized, lowered, target_apps, subgoals)

    return AgentIntent(
        user_instruction=normalized,
        normalized_goal=normalized_goal,
        target_apps=target_apps,
        subgoals=subgoals,
        success_criteria=success_criteria,
        execution_notes=execution_notes,
        safety_flags=safety_flags,
        requires_planning=requires_planning,
        risk_level=risk_level,
        requires_approval=requires_approval,
    )


def build_intent_prompt_block(intent: AgentIntent, *, heading: str) -> str:
    lines = [f"{heading}:", f"- Goal: {intent.normalized_goal}"]
    if intent.target_apps:
        lines.append(f"- Likely target apps: {', '.join(intent.target_apps)}")
    if intent.subgoals:
        lines.append(f"- Suggested milestones: {'; '.join(intent.subgoals)}")
    if intent.success_criteria:
        lines.append(f"- Visible success criteria: {'; '.join(intent.success_criteria)}")
    if intent.execution_notes:
        lines.append(f"- Execution notes: {'; '.join(intent.execution_notes)}")
    if intent.safety_flags:
        lines.append(f"- Safety notes: {'; '.join(intent.safety_flags)}")
    lines.append(f"- Planning mode: {'recommended' if intent.requires_planning else 'optional'}")
    lines.append(f"- Risk: {intent.risk_level}")
    return "\n".join(lines)


def detect_target_apps(lowered: str) -> tuple[str, ...]:
    apps: list[str] = []
    for app_name, keywords in _TARGET_APP_PATTERNS:
        if any(_contains_term(lowered, keyword) for keyword in keywords):
            apps.append(app_name)
    return tuple(apps)


def infer_subgoals(normalized: str, lowered: str, target_apps: tuple[str, ...]) -> tuple[str, ...]:
    if any(word in lowered for word in ("research", "search", "look up", "find")) and any(
        word in lowered for word in ("summarize", "summary", "write a summary", "write summary")
    ):
        return (
            "Open a browser and gather the requested information.",
            "Open a text editor and write a short ASCII summary.",
        )

    parts = [part.strip(" ,") for part in _SEQUENCE_SPLIT_RE.split(normalized) if part.strip(" ,")]
    if len(parts) > 1:
        return tuple(parts[:4])

    if "browser" in target_apps and any(word in lowered for word in ("search", "research", "look up", "find")):
        return ("Open a browser.", "Search for the requested topic.")

    return (normalized,) if normalized else ("Complete the requested task safely.",)


def infer_risk(lowered: str) -> tuple[str, bool, tuple[str, ...]]:
    flags: list[str] = []
    risk_level = "low"
    requires_approval = False

    if any(_contains_term(lowered, pattern) for pattern in _HIGH_RISK_PATTERNS):
        risk_level = "high"
        requires_approval = True
        flags.append("Request includes state-changing or sensitive operations.")
    elif any(_contains_term(lowered, pattern) for pattern in _MEDIUM_RISK_PATTERNS):
        risk_level = "medium"

    for label, patterns in _UNSUPPORTED_PATTERNS:
        if any(_contains_term(lowered, pattern) for pattern in patterns):
            risk_level = combine_risk_levels(risk_level, "high")
            flags.append(f"Request may require unsupported {label}.")

    if _LOOPBACK_RE.search(lowered) and not _RUNNING_LOCAL_SERVICE_RE.search(lowered):
        risk_level = combine_risk_levels(risk_level, "medium")
        flags.append("Loopback or localhost targets are not assumed reachable without an explicit running service.")

    if not flags:
        flags.append("Keep execution within keyboard-first HID limits.")

    return risk_level, requires_approval, tuple(flags)


def infer_execution_notes(
    lowered: str,
    target_apps: tuple[str, ...],
    subgoals: tuple[str, ...],
    safety_flags: tuple[str, ...],
) -> tuple[str, ...]:
    notes: list[str] = ["Use visible milestones and re-check the screen after each step."]
    if len(subgoals) > 1:
        notes.append("The request is multi-step; complete one milestone at a time.")
    if target_apps and any(app in target_apps for app in ("browser", "text editor", "calculator", "paint")):
        notes.append("Prefer keyboard shortcuts and WIN+R when launching applications.")
    if "browser" in target_apps and any(term in lowered for term in ("search", "research", "look up", "find")):
        notes.append("Use a browser search flow before attempting summary or follow-up editing.")
    if any("unsupported" in flag.lower() for flag in safety_flags):
        notes.append("Choose an alternative keyboard-safe path if the original request implies unsupported mouse behavior.")
    notes.append("Typed text must remain short ASCII English.")
    return tuple(notes)


def infer_success_criteria(
    lowered: str,
    target_apps: tuple[str, ...],
    subgoals: tuple[str, ...],
) -> tuple[str, ...]:
    criteria: list[str] = []
    if "browser" in target_apps and _LOOPBACK_RE.search(lowered):
        criteria.append("The browser clearly shows either the requested local page or a reachability error.")
    elif "browser" in target_apps and any(term in lowered for term in ("search", "research", "look up", "find")):
        criteria.append("Search results or the requested web page are visible in a browser.")
    elif "browser" in target_apps:
        criteria.append("The requested browser window is visible.")
    if "text editor" in target_apps and any(term in lowered for term in ("summary", "summarize", "write", "note")):
        criteria.append("A short ASCII note or summary is visible in a text editor.")
    if "calculator" in target_apps:
        criteria.append("Calculator shows the requested result.")
    if "paint" in target_apps:
        criteria.append("Paint is open and the requested visible change is present.")
    if "file explorer" in target_apps:
        criteria.append("The requested file or folder view is visible.")
    if not criteria and subgoals:
        criteria.append("The next visible milestone from the request is achieved.")
    return tuple(criteria[:4])


def infer_requires_planning(
    lowered: str,
    target_apps: tuple[str, ...],
    subgoals: tuple[str, ...],
    risk_level: str,
) -> bool:
    if _LOOPBACK_RE.search(lowered):
        return True
    if len(subgoals) > 1:
        return True
    if risk_level in {"medium", "high"}:
        return True
    if len(target_apps) > 1:
        return True
    if any(term in lowered for term in ("summarize", "compare", "research", "search for", "look up")):
        return True
    return False


def infer_normalized_goal(
    normalized: str,
    lowered: str,
    target_apps: tuple[str, ...],
    subgoals: tuple[str, ...],
) -> str:
    if not normalized:
        return "Complete the requested PC task safely."
    if len(subgoals) > 1:
        return f"Complete the request through visible milestones: {'; '.join(subgoals)}"
    if "browser" in target_apps and _LOOPBACK_RE.search(lowered):
        return "Open a browser and verify whether the specified localhost or loopback page is reachable."
    if "browser" in target_apps and any(term in lowered for term in ("search", "research", "look up", "find")):
        return "Open a browser and reach visible search results or the requested web page."
    if "text editor" in target_apps and any(term in lowered for term in ("summary", "summarize", "write", "note")):
        return "Open a text editor and enter the requested short ASCII text."
    if "calculator" in target_apps:
        return "Open Calculator and display the requested result."
    return normalized[0].upper() + normalized[1:]
