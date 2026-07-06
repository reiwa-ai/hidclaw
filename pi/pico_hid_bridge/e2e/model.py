"""Lightweight E2E scenario model definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class E2EStep:
    """One observable step in an E2E scenario."""

    name: str
    verify_task: str
    success_message: str
    failure_message: str
    action_task: str | None = None
    settle_sec: float | None = None


@dataclass(frozen=True)
class E2ETestCase:
    """A stage test case made from one or more observable E2E steps."""

    name: str
    steps: tuple[E2EStep, ...]
    stage: str
    description: str
    implemented: bool = True
    pending_reason: str = ""
    requires: tuple[str, ...] = field(default_factory=tuple)
