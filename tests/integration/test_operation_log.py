from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tests.helpers.environment import TestEnvironment, is_call_only
from tests.helpers.remote import run_local, run_ssh


pytestmark = pytest.mark.pi_integration


def _run_operation_log_probe(env: TestEnvironment, script: str) -> str:
    script_text = textwrap.dedent(script).strip()
    command = f"cd {env.remote_pi_dir}; python3 - <<'PY'\n{script_text}\nPY"
    if is_call_only():
        return "call-only: operation log probe"

    if Path.cwd().as_posix() == env.remote_pi_dir:
        result = run_local(["python3", "-c", script_text], cwd=Path.cwd(), timeout_sec=30)
        assert result.ok, result.stderr or result.stdout
        return result.stdout

    result = run_ssh(env, command, timeout_sec=30)
    assert result.ok, result.stderr or result.stdout
    return result.stdout


def test_user_input_log_insert_and_query(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_user"
        store = OperationLogStore(root / "app.db", root / "screenshots")
        store.record_user_input(input_text="Stage02 user input", source="integration", planning=False)
        rows = store.query_user_inputs(source="integration")
        assert rows[-1]["input"] == "Stage02 user input"
        print("USER_INPUT_OK")
        """,
    )
    assert "USER_INPUT_OK" in output or "call-only" in output


def test_operation_log_insert_and_query(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_operation"
        store = OperationLogStore(root / "app.db", root / "screenshots")
        store.record_operation(command="KEY WIN+R", normalized="KEY WIN+R", status="sent", source="integration")
        rows = store.query_operations(source="integration", status="sent")
        assert rows[-1]["normalized"] == "KEY WIN+R"
        print("OPERATION_OK")
        """,
    )
    assert "OPERATION_OK" in output or "call-only" in output


def test_screenshot_log_insert_and_query(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_screenshot"
        store = OperationLogStore(root / "app.db", root / "screenshots")
        shot = root / "screenshots" / "before.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        shot.write_bytes(b"png")
        store.record_screenshot(path=shot, event="before", case_name="integration", width=640, height=480)
        rows = store.query_screenshots(case_name="integration")
        assert rows[-1]["event"] == "before"
        print("SCREENSHOT_OK")
        """,
    )
    assert "SCREENSHOT_OK" in output or "call-only" in output


def test_error_log_insert_and_query(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_error"
        store = OperationLogStore(root / "app.db", root / "screenshots")
        op_id = store.record_operation(command="missing app", status="failed", source="integration", error="not found")
        store.record_error(message="not found", domain="implementation", case_name="integration", operation_id=op_id)
        assert store.query_operations(status="failed")[-1]["error"] == "not found"
        assert store.query_errors(case_name="integration")[-1]["message"] == "not found"
        print("ERROR_OK")
        """,
    )
    assert "ERROR_OK" in output or "call-only" in output


def test_log_storage_limit_rotation(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_rotation"
        store = OperationLogStore(root / "app.db", root / "screenshots", max_screenshots=2)
        paths = []
        for index in range(3):
            shot = root / "screenshots" / f"shot{{index}}.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            shot.write_bytes(b"png")
            paths.append(shot)
            store.record_screenshot(path=shot, event="rotation", case_name="integration")
        rows = store.query_screenshots(case_name="integration")
        assert len(rows) == 2
        assert not paths[0].exists()
        assert paths[1].exists() and paths[2].exists()
        print("ROTATION_OK")
        """,
    )
    assert "ROTATION_OK" in output or "call-only" in output


def test_corrupt_database_recovery(env: TestEnvironment) -> None:
    output = _run_operation_log_probe(
        env,
        f"""
        from pathlib import Path
        from pico_hid_bridge.operation_log import OperationLogStore

        root = Path({env.runtime_dir!r}) / "operation_log_corrupt"
        db = root / "app.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"not sqlite")
        store = OperationLogStore(db, root / "screenshots")
        store.record_user_input(input_text="after recovery", source="integration")
        assert store.recovery_performed
        assert list(root.glob("app.db.corrupt-*"))
        print("CORRUPT_OK")
        """,
    )
    assert "CORRUPT_OK" in output or "call-only" in output
