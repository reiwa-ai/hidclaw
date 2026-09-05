from __future__ import annotations

from pathlib import Path
import threading
import time

from pico_hid_bridge.config import load_config
from pico_hid_bridge.operation_log import OperationLogStore

from pico_hid_bridge.web import app as app_module


class FakeCaptureService:
    def __init__(self) -> None:
        self.jpeg_calls = 0
        self.png_calls = 0

    def latest_jpeg(self):
        self.jpeg_calls += 1
        return b"jpeg-bytes", {"source_width": 640, "source_height": 480, "brightness": 42.0}

    def latest_png_base64(self) -> str:
        self.png_calls += 1
        return "ZmFrZS1wbmc="

    def stop(self) -> None:
        return None


def test_webui_initial_command_is_open_browser(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b'<textarea id="command" name="command" spellcheck="false" autocomplete="off">open browser</textarea>' in response.data
    assert b'data-tab="request">Request</button>' in response.data
    assert b'data-tab="plan">Plan</button>' in response.data
    assert b'Manual HID' in response.data
    assert b'id="approvalNotice" class="message warn" hidden' in response.data
    assert b'id="approvalControls" class="row" hidden' in response.data
    assert b'[hidden]' in response.data
    assert b'display: none !important' in response.data
    assert b'id="approveButton"' in response.data
    assert b'id="rejectButton"' in response.data
    assert b'id="operationView"' in response.data
    assert b'id="logsView"' in response.data
    assert b'<section class="panel screen-panel">' in response.data
    assert b'grid-template-rows: auto minmax(0, 1fr)' in response.data
    assert b'const screenWrap = document.querySelector(".screen-wrap")' in response.data
    assert b'fitScreenImageToFrame' in response.data
    assert b'fitScreenImageBeforeRefresh' in response.data
    assert b'screenEl.style.width = `${Math.max(1, width)}px`' in response.data
    assert b'screenEl.style.height = `${Math.max(1, height)}px`' in response.data
    assert b'fitScreenImageBeforeRefresh();\n      screenEl.src = "/api/screenshot?ts=" + Date.now();' in response.data
    assert b'window.addEventListener("resize", scheduleScreenFit)' in response.data
    assert b'new ResizeObserver(scheduleScreenFit).observe(screenWrap)' in response.data
    assert b'id="refreshLogs"' in response.data
    assert b'id="searchLogs"' in response.data
    assert b'id="tokenGraph"' in response.data
    assert b'id="tokenSummary"' in response.data
    assert b'id="tokenTotalAll"' in response.data
    assert b'id="tokenTotalMonth"' in response.data
    assert b'id="tokenRangeSummary"' in response.data
    assert b'refreshTokenSummary(from, to)' in response.data
    assert b'monthTokenParams' in response.data
    assert b'bucketTokenUsage' in response.data
    assert b'rows.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))' in response.data
    assert b'Date.parse(timelineRows[index + 1].created_at)' in response.data
    assert b'tokenTime > previousTime && tokenTime <= currentTime' in response.data
    assert b'.timeline-row, .token-row' in response.data
    assert b'height: 48px' in response.data
    assert b'text-overflow: ellipsis' in response.data
    assert b'id="planning"' not in response.data
    assert b'planning: activeCommandMode === "plan"' in response.data
    assert b'System Log' in response.data
    assert b'id="activityStatus"' in response.data
    assert b'COMMAND_POLL_MS' in response.data
    assert b'pollOperationUntilIdle' in response.data
    assert b'startBusyScreenRefresh' in response.data
    assert b'const approvalPending = !!status.approval_pending' in response.data
    assert b'sendButton.disabled = busy || approvalPending' in response.data
    assert b'suspendButton.disabled = approvalPending' in response.data
    assert b'resumeButton.disabled = approvalPending' in response.data
    assert b'approvalControls.hidden = !approvalPending' in response.data
    assert b'approvalNotice.hidden = !approvalPending' in response.data
    assert b'This plan requires approval before it can continue.' in response.data
    assert b'api("/api/approve"' in response.data
    assert b'api("/api/reject"' in response.data


def test_webui_status_reports_idle_activity(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().get("/api/status")

    assert response.status_code == 200
    assert response.json["command_running"] is False
    assert response.json["current_phase"] == "idle"
    assert response.json["current_status"] == "Ready"
    assert response.json["approval_pending"] is False
    assert response.json["approval_status"] == "idle"


def test_webui_detail_logs_and_tokens_are_loaded_from_database(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    store = OperationLogStore.from_config(config)
    store.record_user_input(
        input_text="kick browser",
        source="web",
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
    store.record_system(
        event="planning",
        status="started",
        message="Planning",
        created_at="2026-07-05T01:02:00+00:00",
    )
    store.record_token_usage(
        phase="Planning",
        model="gpt-5.5",
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
        created_at="2026-07-05T01:02:01+00:00",
    )
    store.record_token_usage(
        phase="Warmup",
        model="gpt-5.5",
        input_tokens=5,
        output_tokens=3,
        total_tokens=8,
        created_at="2026-07-05T00:30:00+00:00",
    )

    response = app.test_client().get(
        "/api/logs/detail?from=2026-07-05T01:00:30+00:00&to=2026-07-05T01:03:00+00:00"
    )
    token_response = app.test_client().get("/api/tokens")
    filtered_token_response = app.test_client().get(
        "/api/tokens?from=2026-07-05T01:00:30+00:00&to=2026-07-05T01:03:00+00:00"
    )

    assert response.status_code == 200
    assert response.json["user_logs"] == []
    assert response.json["operation_logs"][0]["normalized"] == "KEY WIN+R"
    assert response.json["system_logs"][0]["message"] == "Planning"
    assert response.json["token_usage"][0]["total_tokens"] == 18
    assert token_response.json["input_tokens"] == 16
    assert token_response.json["output_tokens"] == 10
    assert token_response.json["total_tokens"] == 26
    assert filtered_token_response.json["input_tokens"] == 11
    assert filtered_token_response.json["output_tokens"] == 7
    assert filtered_token_response.json["total_tokens"] == 18


def test_webui_token_prediction_uses_logged_usage_baseline(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    store = OperationLogStore.from_config(config)
    store.record_token_usage(phase="sample", model="test", total_tokens=80, estimated_tokens=80)
    store.record_token_usage(phase="sample", model="test", total_tokens=120, estimated_tokens=120)

    response = app.test_client().post(
        "/api/tokens/predict",
        json={"steps": ["Open browser", "Search", "Summarize"]},
    )
    status = app.test_client().get("/api/status")

    assert response.status_code == 200
    assert response.json["step_count"] == 3
    assert response.json["baseline_tokens_per_operation"] == 100
    assert response.json["estimated_tokens"] == 300
    assert response.json["plan_budget_exceeded"] is False
    assert status.json["token_prediction"]["estimated_tokens"] == 300


def test_webui_plan_mode_records_token_prediction_before_execution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(
                    PlanningStep("Open", "Open browser.", "Browser visible"),
                    PlanningStep("Summarize", "Write a summary.", "Summary visible"),
                ),
            )

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        capture_service: object | None = None,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "PlanningService", FakePlanningService)
    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    store = OperationLogStore.from_config(config)
    store.record_token_usage(phase="sample", model="test", total_tokens=100, estimated_tokens=100)

    response = app.test_client().post("/api/command", json={"command": "research", "planning": True})
    status = app.test_client().get("/api/status")
    system_rows = store.query_system()

    assert response.status_code == 200
    assert status.json["token_prediction"]["step_count"] == 2
    assert status.json["token_prediction"]["estimated_tokens"] == 200
    assert any(row["event"] == "token_budget" and row["status"] == "predicted" for row in system_rows)


def test_webui_token_budget_excess_enters_approval_pending(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    config["token_budget"]["max_tokens_per_plan"] = 250
    app = app_module.create_app(config)

    store = OperationLogStore.from_config(config)
    store.record_token_usage(phase="sample", model="test", total_tokens=100, estimated_tokens=100)

    response = app.test_client().post(
        "/api/tokens/check-budget",
        json={"steps": ["One", "Two", "Three"], "command": "large plan"},
    )
    status = app.test_client().get("/api/status")

    assert response.status_code == 200
    assert response.json["approval_pending"] is True
    assert response.json["estimated_tokens"] == 300
    assert response.json["plan_budget_exceeded"] is True
    assert status.json["approval_pending"] is True
    assert status.json["approval_command"] == "large plan"
    assert "token budget" in status.json["approval_detail"].lower()


def test_webui_missing_token_usage_records_unknown_warning_and_estimate(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    config["token_budget"]["baseline_tokens_per_operation"] = 777
    app = app_module.create_app(config)

    response = app.test_client().post("/api/tokens/missing-usage-test", json={"phase": "fixture"})

    store = OperationLogStore.from_config(config)
    token_rows = store.query_token_usage()
    system_rows = store.query_system()

    assert response.status_code == 200
    assert response.json["usage_known"] is False
    assert response.json["estimated_tokens"] == 777
    assert token_rows[-1]["total_tokens"] == 0
    assert token_rows[-1]["estimated_tokens"] == 777
    assert system_rows[-1]["event"] == "token_usage"
    assert system_rows[-1]["status"] == "unknown"
    assert "missing" in system_rows[-1]["message"].lower()


def test_response_token_usage_marks_missing_usage_as_unknown() -> None:
    usage = app_module.response_token_usage(object(), phase="initial", model="test-model")

    assert usage["usage_known"] is False
    assert usage["total_tokens"] == 0


def test_webui_screenshot_uses_shared_capture_service(tmp_path: Path, monkeypatch) -> None:
    def fail_capture_jpeg_from_config(config: dict) -> tuple[bytes, dict]:
        raise AssertionError("WebUI screenshot must use the shared capture service")

    monkeypatch.setattr(app_module, "capture_jpeg_from_config", fail_capture_jpeg_from_config)
    service = FakeCaptureService()

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config, capture_service=service)

    response = app.test_client().get("/api/screenshot")

    assert response.status_code == 200
    assert response.data == b"jpeg-bytes"
    assert service.jpeg_calls == 1


def test_webui_command_uses_computer_use_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    requests: list[str] = []

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        requests.append(instruction)
        return "computer use actions sent: 3"

    def fail_send_line(line: str, **kwargs: object) -> None:
        raise AssertionError("COMMAND request must not send raw HID directly")

    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)
    monkeypatch.setattr(app_module, "send_line", fail_send_line)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post("/api/command", json={"command": "open browser", "planning": False})

    assert response.status_code == 200
    assert requests == ["open browser"]

    store = OperationLogStore.from_config(config)
    user_rows = store.query_user_inputs(source="web")
    operation_rows = store.query_operations(source="web", status="sent")

    assert user_rows[-1]["input"] == "open browser"
    assert operation_rows[-1]["command"] == "open browser"
    assert operation_rows[-1]["normalized"] == "COMPUTER_USE"


def test_webui_command_passes_shared_capture_service_to_computer_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = FakeCaptureService()
    services: list[object | None] = []

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        capture_service: object | None = None,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        services.append(capture_service)
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config, capture_service=service)

    response = app.test_client().post("/api/command", json={"command": "open browser", "planning": False})

    assert response.status_code == 200
    assert services == [service]


def test_webui_plan_mode_executes_planned_steps_through_existing_computer_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    executed: list[str] = []

    class FakePlanningService:
        def __init__(self, *, config: dict) -> None:
            self.config = config

        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls(config=config)

        def create_plan(self, instruction: str) -> Plan:
            assert instruction == "research and summarize"
            return Plan(
                user_instruction=instruction,
                steps=(
                    PlanningStep("Search", "Open browser and search for the topic.", "Search results are visible"),
                    PlanningStep("Summarize", "Open Notepad and write a short summary.", "Summary is written"),
                ),
            )

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        capture_service: object | None = None,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        executed.append(instruction)
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "PlanningService", FakePlanningService)
    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post(
        "/api/command",
        json={"command": "research and summarize", "planning": True},
    )

    assert response.status_code == 200
    assert executed == [
        "Open browser and search for the topic.",
        "Open Notepad and write a short summary.",
    ]
    assert "planned steps executed: 2" in response.json["message"]


def test_execute_plan_steps_passes_step_completion_context_to_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    requests: list[dict[str, object]] = []

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        capture_service: object | None = None,
        progress: object | None = None,
        should_stop: object | None = None,
        success_criteria: tuple[str, ...] | None = None,
        goal: str = "",
        target_apps: tuple[str, ...] | None = None,
        **kwargs: object,
    ) -> str:
        requests.append(
            {
                "instruction": instruction,
                "success_criteria": success_criteria,
                "goal": goal,
                "target_apps": target_apps,
            }
        )
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")

    plan = Plan(
        user_instruction="research and summarize",
        goal="Gather information and leave a visible summary.",
        target_apps=("browser", "text editor"),
        success_criteria=("The final summary is visible.",),
        steps=(
            PlanningStep("Search", "Open browser and search for the topic.", "Search results are visible", "browser"),
            PlanningStep("Summarize", "Open Notepad and write a short summary.", "Summary is written", "text editor"),
        ),
    )

    result = app_module.execute_plan_steps(config, plan, event_sink=object())

    assert result == "planned steps executed: 2"
    assert requests == [
        {
            "instruction": "Open browser and search for the topic.",
            "success_criteria": ("Search results are visible",),
            "goal": "Gather information and leave a visible summary.",
            "target_apps": ("browser",),
        },
        {
            "instruction": "Open Notepad and write a short summary.",
            "success_criteria": ("Summary is written",),
            "goal": "Gather information and leave a visible summary.",
            "target_apps": ("text editor",),
        },
    ]


def test_webui_plan_mode_pauses_high_risk_plan_until_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(PlanningStep("Unsafe", "Delete files.", "Files are deleted"),),
                risk_level="high",
                requires_approval=True,
            )

    def fail_execute_computer_use_request(*args: object, **kwargs: object) -> str:
        raise AssertionError("high risk plans must wait for approval before Computer Use")

    monkeypatch.setattr(app_module, "PlanningService", FakePlanningService)
    monkeypatch.setattr(app_module, "execute_computer_use_request", fail_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post(
        "/api/command",
        json={"command": "delete all files", "planning": True},
    )

    assert response.status_code == 200
    assert response.json["approval_pending"] is True
    assert response.json["approval_status"] == "pending"

    status = app.test_client().get("/api/status")
    assert status.json["command_running"] is False
    assert status.json["approval_pending"] is True
    assert status.json["current_phase"] == "approval_pending"


def test_webui_approval_accepts_pending_plan_and_runs_existing_flow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    executed: list[str] = []

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(PlanningStep("Save", "Save a file named approved.txt.", "File saved"),),
                risk_level="high",
                requires_approval=True,
            )

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        capture_service: object | None = None,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        executed.append(instruction)
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "PlanningService", FakePlanningService)
    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)
    client = app.test_client()

    pending = client.post("/api/command", json={"command": "save a file", "planning": True})
    assert pending.status_code == 200

    suspend = client.post("/api/suspend")
    resume = client.post("/api/resume")
    assert suspend.status_code == 409
    assert resume.status_code == 409

    approved = client.post("/api/approve")

    assert approved.status_code == 200
    assert approved.json["approval_status"] == "approved"
    assert executed == ["Save a file named approved.txt."]
    status = client.get("/api/status")
    assert status.json["approval_pending"] is False
    assert status.json["current_phase"] == "idle"


def test_webui_reject_discards_pending_plan_without_computer_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from pico_hid_bridge.planning import Plan, PlanningStep

    class FakePlanningService:
        @classmethod
        def from_config(cls, config: dict) -> "FakePlanningService":
            return cls()

        def create_plan(self, instruction: str) -> Plan:
            return Plan(
                user_instruction=instruction,
                steps=(PlanningStep("Unsafe", "Delete files.", "Files deleted"),),
                risk_level="high",
                requires_approval=True,
            )

    def fail_execute_computer_use_request(*args: object, **kwargs: object) -> str:
        raise AssertionError("rejected plan must not reach Computer Use")

    monkeypatch.setattr(app_module, "PlanningService", FakePlanningService)
    monkeypatch.setattr(app_module, "execute_computer_use_request", fail_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)
    client = app.test_client()

    pending = client.post("/api/command", json={"command": "delete files", "planning": True})
    assert pending.status_code == 200

    rejected = client.post("/api/reject")

    assert rejected.status_code == 200
    assert rejected.json["approval_status"] == "rejected"
    status = client.get("/api/status")
    assert status.json["approval_pending"] is False
    assert status.json["current_phase"] == "idle"


def test_webui_pending_approval_expires_before_approval(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["app"]["approval_timeout_seconds"] = 0.01
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)
    client = app.test_client()

    pending = client.post("/api/approval-test", json={"reason": "expires soon"})
    assert pending.status_code == 200

    time.sleep(0.02)
    status = client.get("/api/status")
    approval = client.post("/api/approve")

    assert status.json["approval_status"] == "expired"
    assert status.json["approval_pending"] is False
    assert approval.status_code == 409


def test_computer_use_retries_once_when_model_returns_text_instead_of_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_calls: list[dict[str, object]] = []
    executed: list[object] = []
    service = FakeCaptureService()

    class FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> dict[str, object]:
            self.calls += 1
            retry_calls.append(kwargs)
            if self.calls > 1:
                return {"id": "verify-response", "output_text": "True"}
            return {
                "id": "retry-response",
                "output": [
                    {
                        "type": "computer_call",
                        "call_id": "call-1",
                        "actions": [{"type": "type", "text": "Short summary"}],
                    }
                ],
            }

    class FakeClient:
        responses = FakeResponses()

    class FakeExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return

        def execute_supported_action(self, action: object) -> bool:
            executed.append(action)
            return True

    class FakeEventSink:
        def emit(self, event: object) -> None:
            return

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setattr(app_module, "read_openai_api_key", lambda config: "test-key")
    monkeypatch.setattr(
        app_module,
        "create_initial_response",
        lambda *args, **kwargs: {"id": "text-response", "output_text": "A summary that should be typed."},
    )
    monkeypatch.setattr(
        app_module,
        "send_screenshot_response",
        lambda *args, **kwargs: {"id": "done-response", "output_text": "done"},
    )
    monkeypatch.setattr(app_module, "ActionExecutor", FakeExecutor)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")

    result = app_module.execute_computer_use_request(
        config,
        "write summary",
        event_sink=FakeEventSink(),
        capture_service=service,
    )

    assert result == "computer use actions sent: 1"
    assert executed == [{"type": "type", "text": "Short summary"}]
    assert retry_calls
    assert "Never answer" in str(retry_calls[0]["input"])


def test_computer_use_retries_once_when_model_returns_empty_response(
    tmp_path: Path,
    monkeypatch,
) -> None:
    retry_calls: list[dict[str, object]] = []
    executed: list[object] = []
    service = FakeCaptureService()

    class FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> dict[str, object]:
            self.calls += 1
            retry_calls.append(kwargs)
            if self.calls > 1:
                return {"id": "verify-response", "output_text": "True"}
            return {
                "id": "retry-response",
                "output": [
                    {
                        "type": "computer_call",
                        "call_id": "call-1",
                        "actions": [{"type": "keypress", "keys": ["ESC"]}],
                    }
                ],
            }

    class FakeClient:
        responses = FakeResponses()

    class FakeExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return

        def execute_supported_action(self, action: object) -> bool:
            executed.append(action)
            return True

    class FakeEventSink:
        def emit(self, event: object) -> None:
            return

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setattr(app_module, "read_openai_api_key", lambda config: "test-key")
    monkeypatch.setattr(
        app_module,
        "create_initial_response",
        lambda *args, **kwargs: {"id": "empty-response", "output": [], "output_text": ""},
    )
    monkeypatch.setattr(
        app_module,
        "send_screenshot_response",
        lambda *args, **kwargs: {"id": "done-response", "output_text": "done"},
    )
    monkeypatch.setattr(app_module, "ActionExecutor", FakeExecutor)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")

    result = app_module.execute_computer_use_request(
        config,
        "recover empty response",
        event_sink=FakeEventSink(),
        capture_service=service,
    )

    assert result == "computer use actions sent: 1"
    assert executed == [{"type": "keypress", "keys": ["ESC"]}]
    assert retry_calls
    assert "(empty response)" in str(retry_calls[0]["input"])


def test_computer_use_retries_action_round_when_completion_is_not_yet_visible(
    tmp_path: Path,
    monkeypatch,
) -> None:
    action_requests: list[str] = []
    verification_requests: list[object] = []
    executed: list[object] = []
    service = FakeCaptureService()

    class FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> dict[str, object]:
            self.calls += 1
            verification_requests.append(kwargs.get("input"))
            if self.calls == 1:
                return {
                    "id": "verify-1",
                    "output": [
                        {
                            "type": "computer_call",
                            "call_id": "verify-call-1",
                            "actions": [{"type": "screenshot"}],
                        }
                    ],
                }
            if self.calls == 2:
                return {"id": "verify-1-result", "output_text": "False"}
            if self.calls == 3:
                return {
                    "id": "verify-2",
                    "output": [
                        {
                            "type": "computer_call",
                            "call_id": "verify-call-2",
                            "actions": [{"type": "screenshot"}],
                        }
                    ],
                }
            if self.calls == 4:
                return {"id": "verify-2-result", "output_text": "True"}
            raise AssertionError(f"unexpected verification call: {kwargs!r}")

    class FakeClient:
        responses = FakeResponses()

    class FakeExecutor:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return

        def execute_supported_action(self, action: object) -> bool:
            executed.append(action)
            return True

    class FakeEventSink:
        def emit(self, event: object) -> None:
            return

    responses = iter(
        [
            {
                "id": "round-1",
                "output": [
                    {
                        "type": "computer_call",
                        "call_id": "call-1",
                        "actions": [{"type": "keypress", "keys": ["ESC"]}],
                    }
                ],
            },
            {
                "id": "round-2",
                "output": [
                    {
                        "type": "computer_call",
                        "call_id": "call-2",
                        "actions": [{"type": "keypress", "keys": ["ENTER"]}],
                    }
                ],
            },
        ]
    )

    def fake_create_initial_response(*args: object, **kwargs: object) -> dict[str, object]:
        action_requests.append(str(kwargs["task"]))
        return next(responses)

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setattr(app_module, "read_openai_api_key", lambda config: "test-key")
    monkeypatch.setattr(app_module, "create_initial_response", fake_create_initial_response)

    def fake_send_screenshot_response(*args: object, **kwargs: object) -> dict[str, object]:
        if str(kwargs["call_id"]).startswith("verify-call"):
            return args[0].responses.create(input=[{"type": "computer_call_output"}])
        return {"id": "after-action", "output_text": "done"}

    monkeypatch.setattr(
        app_module,
        "send_screenshot_response",
        fake_send_screenshot_response,
    )
    monkeypatch.setattr(app_module, "ActionExecutor", FakeExecutor)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    config["openai"]["max_completion_rounds"] = 2
    config["openai"]["max_verify_turns"] = 3

    result = app_module.execute_computer_use_request(
        config,
        "open browser",
        event_sink=FakeEventSink(),
        capture_service=service,
    )

    assert result == "computer use actions sent: 2"
    assert executed == [
        {"type": "keypress", "keys": ["ESC"]},
        {"type": "keypress", "keys": ["ENTER"]},
    ]
    assert len(action_requests) == 2
    assert "Continue from the current PC state." in action_requests[1]
    assert "not yet satisfy the visible completion check" in action_requests[1]
    assert len(verification_requests) == 4
    assert service.png_calls == 4


def test_computer_use_accepts_already_complete_screen_without_extra_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model_calls: list[object] = []
    service = FakeCaptureService()

    class FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> dict[str, object]:
            self.calls += 1
            model_calls.append(kwargs.get("input"))
            if self.calls == 1:
                return {"id": "text-retry-1", "output_text": "already visible"}
            if self.calls == 2:
                return {"id": "text-retry-2", "output_text": "already visible"}
            if self.calls == 3:
                return {
                    "id": "verify-1",
                    "output": [
                        {
                            "type": "computer_call",
                            "call_id": "verify-call-1",
                            "actions": [{"type": "screenshot"}],
                        }
                    ],
                }
            if self.calls == 4:
                return {"id": "verify-1-result", "output_text": "True"}
            raise AssertionError(f"unexpected verification call: {kwargs!r}")

    class FakeClient:
        responses = FakeResponses()

    class FakeEventSink:
        def emit(self, event: object) -> None:
            return

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setattr(app_module, "read_openai_api_key", lambda config: "test-key")
    monkeypatch.setattr(
        app_module,
        "create_initial_response",
        lambda *args, **kwargs: {"id": "done-response", "output_text": "already visible"},
    )

    def fake_send_screenshot_response(*args: object, **kwargs: object) -> dict[str, object]:
        if str(kwargs["call_id"]).startswith("verify-call"):
            return args[0].responses.create(input=[{"type": "computer_call_output"}])
        raise AssertionError("action screenshot loop should not run")

    monkeypatch.setattr(
        app_module,
        "send_screenshot_response",
        fake_send_screenshot_response,
    )

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    config["openai"]["max_verify_turns"] = 2

    result = app_module.execute_computer_use_request(
        config,
        "open browser",
        event_sink=FakeEventSink(),
        capture_service=service,
    )

    assert result == "computer use actions sent: 0"
    assert len(model_calls) == 4
    assert service.png_calls == 1


def test_webui_rejects_second_command_while_request_is_running(
    tmp_path: Path,
    monkeypatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    first_response: dict[str, object] = {}

    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        if progress is not None:
            progress("computer_use", "Computer Use API calling")
        started.set()
        assert release.wait(3), "test timed out waiting to finish fake request"
        return "computer use actions sent: 1"

    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    def post_first() -> None:
        with app.test_client() as client:
            first_response["response"] = client.post(
                "/api/command",
                json={"command": "open browser", "planning": False},
            )

    thread = threading.Thread(target=post_first)
    thread.start()
    assert started.wait(3), "first request did not start"

    status_response = app.test_client().get("/api/status")
    second_response = app.test_client().post(
        "/api/command",
        json={"command": "open browser", "planning": False},
    )

    release.set()
    thread.join(3)

    assert status_response.json["command_running"] is True
    assert status_response.json["current_phase"] == "computer_use"
    assert second_response.status_code == 409
    assert "already running" in second_response.json["error"]
    assert first_response["response"].status_code == 200
    assert app.test_client().get("/api/status").json["command_running"] is False


def test_webui_manual_hid_persists_user_and_operation_logs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    sent: list[str] = []

    def fake_send_line(line: str, **kwargs: object) -> None:
        sent.append(line)

    monkeypatch.setattr(app_module, "send_line", fake_send_line)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post("/api/manual-hid", json={"command": "KEY ENTER"})

    assert response.status_code == 200
    assert sent == ["KEY ENTER"]

    store = OperationLogStore.from_config(config)
    user_rows = store.query_user_inputs(source="web_manual")
    operation_rows = store.query_operations(source="web_manual", status="sent")

    assert user_rows[-1]["input"] == "KEY ENTER"
    assert operation_rows[-1]["command"] == "KEY ENTER"
    assert operation_rows[-1]["normalized"] == "KEY ENTER"


def test_webui_command_ack_timeout_is_logged_as_pico_uart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_execute_computer_use_request(
        config: dict,
        instruction: str,
        *,
        event_sink: object,
        progress: object | None = None,
        should_stop: object | None = None,
        **kwargs: object,
    ) -> str:
        raise TimeoutError("Pico did not acknowledge command completion")

    monkeypatch.setattr(app_module, "execute_computer_use_request", fake_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post("/api/command", json={"command": "open browser", "planning": False})

    assert response.status_code == 400

    store = OperationLogStore.from_config(config)
    error_rows = store.query_errors()

    assert error_rows[-1]["message"] == "Pico did not acknowledge command completion"
    assert error_rows[-1]["domain"] == "pico_uart"


def test_webui_command_blocks_unsupported_drag_request(tmp_path: Path, monkeypatch) -> None:
    def fail_execute_computer_use_request(*args: object, **kwargs: object) -> str:
        raise AssertionError("unsupported drag requests should be blocked before Computer Use")

    monkeypatch.setattr(app_module, "execute_computer_use_request", fail_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post(
        "/api/command",
        json={"command": "draw a freehand line using a mouse drag", "planning": False},
    )

    assert response.status_code == 400
    assert "unsupported" in response.json["error"]


def test_webui_command_blocks_unsupported_freehand_mouse_movement(tmp_path: Path, monkeypatch) -> None:
    def fail_execute_planned_request(*args: object, **kwargs: object) -> str:
        raise AssertionError("planning layer was reached")

    monkeypatch.setattr(app_module, "execute_planned_request", fail_execute_planned_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post(
        "/api/command",
        json={"command": "open Paint and draw a spiral with freehand mouse movement", "planning": True},
    )

    assert response.status_code == 400
    assert response.json["error"] == "unsupported action for current Pico firmware: mouse drag"


def test_webui_command_blocks_known_nonexistent_app_fixture(tmp_path: Path, monkeypatch) -> None:
    def fail_execute_computer_use_request(*args: object, **kwargs: object) -> str:
        raise AssertionError("known nonexistent app fixture should be blocked before Computer Use")

    monkeypatch.setattr(app_module, "execute_computer_use_request", fail_execute_computer_use_request)

    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post(
        "/api/command",
        json={"command": "open DefinitelyNotARealApp12345", "planning": False},
    )

    assert response.status_code == 400
    assert "not found" in response.json["error"]


def test_webui_invalid_command_persists_error_log(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().post("/api/manual-hid", json={"command": "TEXT café"})

    assert response.status_code == 400

    store = OperationLogStore.from_config(config)
    operation_rows = store.query_operations(source="web_manual", status="failed")
    error_rows = store.query_errors()

    assert operation_rows[-1]["command"] == "TEXT café"
    assert "ASCII" in error_rows[-1]["message"]


def test_webui_system_log_endpoint_returns_system_events(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    response = app.test_client().get("/api/logs/system")

    assert response.status_code == 200
    assert response.json["items"][-1]["event"] == "started"


def test_webui_emergency_stop_cancels_pending_approval(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    app = app_module.create_app(config)

    approval_response = app.test_client().post("/api/approval-test", json={"reason": "stage03"})
    stop_response = app.test_client().post("/api/emergency-stop", json={})
    status_response = app.test_client().get("/api/status")

    assert approval_response.status_code == 200
    assert stop_response.status_code == 200
    assert status_response.json["approval_pending"] is False
    assert status_response.json["approval_status"] == "cancelled_by_emergency_stop"
    assert status_response.json["emergency_stopped"] is True


def test_webui_long_operation_progress_suspend_resume_and_cancel(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    client = app_module.create_app(config).test_client()

    started = client.post(
        "/api/long-operation-test",
        json={"total_steps": 4, "completed_steps": 1, "current_step": "Research", "warning": True},
    )
    suspended = client.post("/api/suspend", json={})
    resumed = client.post("/api/resume", json={})
    cancelled = client.post("/api/cancel", json={})
    status = client.get("/api/status").json

    assert started.status_code == 200
    assert suspended.status_code == 200
    assert resumed.status_code == 200
    assert cancelled.status_code == 200
    assert status["long_operation"]["active"] is False
    assert status["long_operation"]["cancelled"] is True
    assert status["long_operation"]["completed_steps"] == 1
    assert status["long_operation"]["total_steps"] == 4
    assert status["long_operation"]["estimated_percent"] == 25
    assert status["long_operation"]["warning"] is True


def test_webui_resume_after_screen_drift_requires_approval(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    client = app_module.create_app(config).test_client()

    client.post("/api/long-operation-test", json={"total_steps": 3, "completed_steps": 1})
    client.post("/api/suspend", json={})
    response = client.post("/api/resume", json={"screen_drift": True})
    status = client.get("/api/status").json

    assert response.status_code == 409
    assert status["approval_pending"] is True
    assert status["approval_status"] == "pending"
    assert status["long_operation"]["screen_drift"] is True
    assert status["long_operation"]["resume_requires_verification"] is True


def test_webui_long_operation_suspend_state_survives_app_restart(tmp_path: Path) -> None:
    config = load_config(None)
    config["app"]["runtime_dir"] = str(tmp_path / "runtime")
    config["logs"]["database"] = str(tmp_path / "runtime" / "app.db")
    config["logs"]["screenshot_dir"] = str(tmp_path / "runtime" / "screenshots")
    first_client = app_module.create_app(config).test_client()

    first_client.post("/api/long-operation-test", json={"total_steps": 5, "completed_steps": 2})
    first_client.post("/api/suspend", json={})

    restarted_client = app_module.create_app(config).test_client()
    status = restarted_client.get("/api/status").json

    assert status["suspended"] is True
    assert status["long_operation"]["active"] is True
    assert status["long_operation"]["completed_steps"] == 2
    assert status["long_operation"]["resume_requires_verification"] is True
