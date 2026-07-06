"""Project path helpers."""

from __future__ import annotations

from pathlib import Path


PI_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = PI_DIR.parent


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path

