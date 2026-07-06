from __future__ import annotations

from pathlib import Path

from tools import run_e2e_suite


def test_include_pending_stage_accepts_common_runner_args() -> None:
    args = run_e2e_suite.parse_args(
        [
            "--stage",
            "stage03_runtime_safety",
            "--include-pending",
            "--api-key-file",
            "/home/nama/openai-api-key.txt",
        ]
    )

    assert args.include_pending is True
    assert args.stages == ["stage03_runtime_safety"]
    assert args.api_key_file == Path("/home/nama/openai-api-key.txt")
