from __future__ import annotations

from pathlib import Path

from pico_hid_bridge.operation_log import OperationLogStore


def make_store(tmp_path: Path, *, max_screenshots: int = 10) -> OperationLogStore:
    return OperationLogStore(
        database_path=tmp_path / "runtime" / "app.db",
        screenshot_dir=tmp_path / "runtime" / "screenshots",
        max_screenshots=max_screenshots,
    )


def test_user_input_log_insert_and_query(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_user_input(
        input_text="Open Browser",
        source="e2e",
        planning=False,
        case_name="stage02_scenario01_user_input_log",
    )

    rows = store.query_user_inputs(source="e2e")
    assert len(rows) == 1
    assert rows[0]["input"] == "Open Browser"
    assert rows[0]["source"] == "e2e"
    assert rows[0]["planning"] == 0
    assert rows[0]["case_name"] == "stage02_scenario01_user_input_log"


def test_operation_log_insert_and_query_by_status(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_operation(
        command="KEY WIN+R",
        normalized="KEY WIN+R",
        status="sent",
        source="e2e",
        case_name="stage02_scenario02_operation_log",
    )
    store.record_operation(
        command="DefinitelyNotARealApp12345",
        normalized="TEXT DefinitelyNotARealApp12345",
        status="failed",
        source="e2e",
        case_name="stage02_scenario05_error_log",
        error="not found",
    )

    sent = store.query_operations(status="sent")
    failed = store.query_operations(status="failed")

    assert [row["normalized"] for row in sent] == ["KEY WIN+R"]
    assert [row["error"] for row in failed] == ["not found"]


def test_screenshot_log_rotation_removes_old_rows_and_files(tmp_path: Path) -> None:
    store = make_store(tmp_path, max_screenshots=2)

    paths = []
    for index in range(3):
        path = tmp_path / "runtime" / "screenshots" / f"shot{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        paths.append(path)
        store.record_screenshot(
            path=path,
            event="after",
            case_name="stage02_scenario03_screenshot_log",
            step_name=f"step{index}",
            width=640,
            height=480,
            mean_brightness=42.0,
        )

    rows = store.query_screenshots()

    assert [Path(row["path"]).name for row in rows] == ["shot1.png", "shot2.png"]
    assert not paths[0].exists()
    assert paths[1].exists()
    assert paths[2].exists()


def test_error_log_insert_and_query(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_error(
        message="missing app failed cleanly",
        domain="implementation",
        case_name="stage02_scenario05_error_log",
    )

    rows = store.query_errors(case_name="stage02_scenario05_error_log")
    assert len(rows) == 1
    assert rows[0]["message"] == "missing app failed cleanly"
    assert rows[0]["domain"] == "implementation"


def test_notification_log_insert_and_query(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_notification(
        channel="email",
        event="completion",
        status="sent",
        recipient="operator@example.test",
        subject="Done",
        message="SMTP send succeeded",
        source="web",
        case_name="stage07_scenario01_completion_email_log",
    )

    rows = store.query_notifications(channel="email", event="completion")
    assert len(rows) == 1
    assert rows[0]["status"] == "sent"
    assert rows[0]["recipient"] == "operator@example.test"


def test_system_and_token_logs_are_queryable_by_time_range(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_system(
        event="started",
        status="ready",
        message="webui started",
        created_at="2026-07-05T01:00:00+00:00",
    )
    store.record_operation(
        command="KEY WIN+R",
        normalized="KEY WIN+R",
        status="sent",
        source="web",
        action_type="KEY",
        created_at="2026-07-05T01:01:00+00:00",
    )
    store.record_token_usage(
        phase="computer_use",
        model="gpt-5.5",
        response_id="resp_1",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        created_at="2026-07-05T01:02:00+00:00",
    )

    rows = store.query_detail_logs(
        start_at="2026-07-05T01:00:30+00:00",
        end_at="2026-07-05T01:03:00+00:00",
    )

    assert rows["system_logs"] == []
    assert rows["operation_logs"][0]["command"] == "KEY WIN+R"
    assert rows["token_usage"][0]["total_tokens"] == 15


def test_token_totals_can_be_limited_by_time_range(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_token_usage(
        phase="before",
        input_tokens=3,
        output_tokens=2,
        total_tokens=5,
        created_at="2026-07-05T00:59:59+00:00",
    )
    store.record_token_usage(
        phase="inside",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        created_at="2026-07-05T01:02:00+00:00",
    )

    all_totals = store.query_token_totals()
    filtered_totals = store.query_token_totals(
        start_at="2026-07-05T01:00:00+00:00",
        end_at="2026-07-05T01:03:00+00:00",
    )

    assert all_totals["input_tokens"] == 13
    assert all_totals["output_tokens"] == 7
    assert all_totals["total_tokens"] == 20
    assert filtered_totals["input_tokens"] == 10
    assert filtered_totals["output_tokens"] == 5
    assert filtered_totals["total_tokens"] == 15


def test_corrupt_database_is_moved_aside(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"this is not sqlite")

    store = OperationLogStore(
        database_path=db_path,
        screenshot_dir=tmp_path / "runtime" / "screenshots",
    )
    store.record_user_input(input_text="after recovery", source="test")

    assert store.recovery_performed is True
    assert store.query_user_inputs()[0]["input"] == "after recovery"
    assert list(db_path.parent.glob("app.db.corrupt-*"))
