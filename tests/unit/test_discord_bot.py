from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pico_hid_bridge.config import load_config
from pico_hid_bridge.discord_bot import (
    DiscordBotWorker,
    DiscordCommand,
    DiscordCommandParser,
    DiscordMessage,
    DiscordScope,
)
from pico_hid_bridge.operation_log import OperationLogStore


class FakeDiscordClient:
    def __init__(self, messages: list[DiscordMessage]) -> None:
        self.messages = messages
        self.sent_messages: list[dict[str, Any]] = []

    def fetch_recent_messages(self, channel_id: str, *, limit: int = 20) -> list[DiscordMessage]:
        return list(self.messages)

    def send_message(self, channel_id: str, content: str, *, attachment: bytes | None = None, filename: str = "") -> None:
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "content": content,
                "attachment": attachment,
                "filename": filename,
            }
        )


class FakeControlClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.screenshot = b"jpeg-bytes"

    def request(self, command: str, *, planning: bool) -> dict[str, Any]:
        self.calls.append(("request", command, planning))
        return {"ok": True, "message": "request done"}

    def manual_hid(self, command: str) -> dict[str, Any]:
        self.calls.append(("manual_hid", command))
        return {"ok": True, "message": "hid sent"}

    def emergency_stop(self) -> dict[str, Any]:
        self.calls.append(("emergency_stop", None))
        return {"ok": True, "message": "stopped"}

    def approve(self) -> dict[str, Any]:
        self.calls.append(("approve", None))
        return {"ok": True, "message": "approved"}

    def reject(self) -> dict[str, Any]:
        self.calls.append(("reject", None))
        return {"ok": True, "message": "rejected"}

    def capture_screenshot(self) -> bytes:
        self.calls.append(("capture_screenshot", None))
        return self.screenshot


def make_message(
    message_id: str,
    content: str,
    *,
    seconds_ago: int = 10,
    guild_id: str = "guild-1",
    channel_id: str = "channel-1",
    author_id: str = "user-1",
) -> DiscordMessage:
    return DiscordMessage(
        id=message_id,
        content=content,
        author_id=author_id,
        channel_id=channel_id,
        guild_id=guild_id,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=seconds_ago),
    )


def make_config(tmp_path: Path) -> dict[str, Any]:
    config = load_config(None)
    config["discord"].update(
        {
            "enabled": True,
            "bot_name": "AgentDev",
            "token_file": str(tmp_path / "discord-api-key.txt"),
            "channel_id": "channel-1",
            "allowed_guild_ids": ["guild-1"],
            "allowed_channel_ids": ["channel-1"],
            "allowed_user_ids": ["user-1"],
            "max_command_age_sec": 60,
            "rate_limit_per_hour": 20,
            "attachment_limit_mb": 1,
        }
    )
    return config


def make_worker(
    tmp_path: Path,
    messages: list[DiscordMessage],
    *,
    control: FakeControlClient | None = None,
    console: bool = False,
    skip_existing_on_startup: bool = False,
) -> tuple[DiscordBotWorker, FakeDiscordClient, FakeControlClient, OperationLogStore]:
    config = make_config(tmp_path)
    config["discord"]["skip_existing_on_startup"] = skip_existing_on_startup
    store = OperationLogStore(tmp_path / "app.db", tmp_path / "screenshots")
    discord = FakeDiscordClient(messages)
    control_client = control or FakeControlClient()
    worker = DiscordBotWorker(
        config,
        store,
        discord_client=discord,
        control_client=control_client,
        console=console,
    )
    return worker, discord, control_client, store


def test_parser_treats_bot_mention_as_planned_request() -> None:
    parser = DiscordCommandParser(bot_name="AgentDev")

    command = parser.parse("@AgentDev open browser")

    assert command == DiscordCommand(kind="request", text="open browser", planning=True)


def test_parser_treats_hid_prefix_as_manual_hid() -> None:
    parser = DiscordCommandParser(bot_name="AgentDev")

    command = parser.parse("@AgentDev hid: KEY WIN+R")

    assert command == DiscordCommand(kind="hid", text="KEY WIN+R", planning=False)


def test_worker_executes_only_latest_fresh_command(tmp_path: Path) -> None:
    older = make_message("100", "@AgentDev open notepad", seconds_ago=20)
    newer = make_message("101", "@AgentDev open browser", seconds_ago=10)
    worker, discord, control, store = make_worker(tmp_path, [newer, older])

    worker.poll_once()

    assert control.calls == [("request", "open browser", True), ("capture_screenshot", None)]
    assert discord.sent_messages[-1]["attachment"] == b"jpeg-bytes"
    operations = store.query_operations(source="discord")
    assert operations[-1]["command"] == "open browser"
    assert operations[-1]["status"] == "sent"


def test_worker_skips_existing_messages_on_initial_poll(tmp_path: Path) -> None:
    existing = make_message("100", "@AgentDev screen", seconds_ago=10)
    worker, discord, control, store = make_worker(tmp_path, [existing], skip_existing_on_startup=True)

    worker.poll_once()

    assert control.calls == []
    assert discord.sent_messages == []
    assert worker.last_seen_message_id == "100"
    assert store.query_operations(source="discord") == []

    worker.discord_client.messages = [make_message("101", "@AgentDev screen", seconds_ago=1)]
    worker.poll_once()

    assert control.calls == [("capture_screenshot", None)]
    assert discord.sent_messages[-1]["attachment"] == b"jpeg-bytes"


def test_worker_ignores_stale_backlog_after_discord_outage(tmp_path: Path) -> None:
    stale = make_message("100", "@AgentDev open browser", seconds_ago=120)
    worker, discord, control, store = make_worker(tmp_path, [stale])

    worker.poll_once()

    assert control.calls == []
    assert discord.sent_messages == []
    assert store.query_operations(source="discord")[-1]["status"] == "stale"


def test_worker_logs_unauthorized_latest_command_without_running_older_allowed(tmp_path: Path) -> None:
    allowed_old = make_message("100", "@AgentDev open browser", seconds_ago=20)
    denied_new = make_message("101", "@AgentDev hid: KEY WIN+R", seconds_ago=10, author_id="user-2")
    worker, discord, control, store = make_worker(tmp_path, [denied_new, allowed_old])

    worker.poll_once()

    assert control.calls == []
    assert discord.sent_messages == []
    operations = store.query_operations(source="discord")
    assert operations[-1]["status"] == "denied"
    assert "unauthorized" in operations[-1]["error"]


def test_worker_allows_missing_guild_id_when_channel_and_user_are_allowed(tmp_path: Path) -> None:
    message = make_message("100", "@AgentDev screen", guild_id="", seconds_ago=10)
    worker, discord, control, store = make_worker(tmp_path, [message], console=True)

    worker.poll_once()

    assert control.calls == [("capture_screenshot", None)]
    assert discord.sent_messages[-1]["attachment"] == b"jpeg-bytes"
    assert store.query_operations(source="discord")[-1]["status"] == "sent"


def test_worker_screen_command_sends_capture_only(tmp_path: Path) -> None:
    screen = make_message("100", "@AgentDev screen", seconds_ago=10)
    worker, discord, control, store = make_worker(tmp_path, [screen])

    worker.poll_once()

    assert control.calls == [("capture_screenshot", None)]
    assert discord.sent_messages[-1]["filename"] == "screenshot.jpg"
    assert store.query_notifications(channel="discord")[-1]["attachment_policy"] == "attached"


def test_worker_console_mode_prints_discord_operations(tmp_path: Path, capsys: Any) -> None:
    screen = make_message("100", "@AgentDev screen", seconds_ago=10)
    worker, _discord, _control, _store = make_worker(tmp_path, [screen], console=True)

    worker.poll_once()

    output = capsys.readouterr().out
    assert "DISCORD polling channel channel-1" in output
    assert "DISCORD command screen from user-1" in output
    assert "DISCORD send screenshot attached" in output
