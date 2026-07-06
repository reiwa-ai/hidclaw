"""Discord polling layer for Pico HID Bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable
from urllib import error, parse, request

from .operation_log import OperationLogStore


DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordApiError(RuntimeError):
    pass


class DiscordRateLimitError(DiscordApiError):
    def __init__(self, retry_after: float, message: str = "Discord rate limited") -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class DiscordMessage:
    id: str
    content: str
    author_id: str
    channel_id: str
    guild_id: str
    timestamp: datetime
    author_is_bot: bool = False


@dataclass(frozen=True)
class DiscordCommand:
    kind: str
    text: str = ""
    planning: bool = True


@dataclass(frozen=True)
class DiscordScope:
    guild_id: str
    channel_id: str
    user_id: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_discord_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _message_sort_key(message: DiscordMessage) -> tuple[datetime, int]:
    try:
        numeric_id = int(message.id)
    except ValueError:
        numeric_id = 0
    return (message.timestamp, numeric_id)


def command_age_seconds(message: DiscordMessage, now: datetime | None = None) -> float:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current.astimezone(timezone.utc) - message.timestamp).total_seconds())


class DiscordCommandParser:
    def __init__(self, *, bot_name: str, bot_user_id: str = "") -> None:
        self.bot_name = bot_name.strip()
        self.bot_user_id = bot_user_id.strip()

    def parse(self, content: str) -> DiscordCommand | None:
        text = self._strip_addressing(content)
        if text is None:
            return None
        if not text:
            return None

        lowered = text.lower()
        if lowered in {"screen", "screenshot", "/screen", "/screenshot"}:
            return DiscordCommand(kind="screen", text="", planning=False)
        if lowered in {"stop", "emergency", "emergency stop", "/stop"}:
            return DiscordCommand(kind="stop", text="", planning=False)
        if lowered in {"approve", "/approve"}:
            return DiscordCommand(kind="approve", text="", planning=False)
        if lowered in {"reject", "/reject"}:
            return DiscordCommand(kind="reject", text="", planning=False)

        for prefix in ("hid:", "hid ", "/hid ", "!hid "):
            if lowered.startswith(prefix):
                return DiscordCommand(kind="hid", text=text[len(prefix) :].strip(), planning=False)

        for prefix in ("request:", "request ", "/request "):
            if lowered.startswith(prefix):
                return DiscordCommand(kind="request", text=text[len(prefix) :].strip(), planning=True)

        return DiscordCommand(kind="request", text=text, planning=True)

    def _strip_addressing(self, content: str) -> str | None:
        stripped = content.strip()
        if not stripped:
            return None
        lowered = stripped.lower()

        if stripped.startswith("/"):
            return stripped

        mention_forms = []
        if self.bot_user_id:
            mention_forms.extend([f"<@{self.bot_user_id}>", f"<@!{self.bot_user_id}>"])
        mention_forms.append(f"@{self.bot_name}")

        for mention in mention_forms:
            if lowered.startswith(mention.lower()):
                return stripped[len(mention) :].strip(" \t:,-")
        return None


class DiscordRestClient:
    def __init__(
        self,
        *,
        token_file: str | Path,
        api_base: str = DISCORD_API_BASE,
        timeout: float = 15.0,
        debug: Callable[[str], None] | None = None,
    ) -> None:
        self.token_file = Path(token_file)
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.debug = debug

    def fetch_recent_messages(self, channel_id: str, *, limit: int = 20) -> list[DiscordMessage]:
        query = parse.urlencode({"limit": max(1, min(int(limit), 100))})
        self._debug(f"DISCORD REST fetch messages channel={channel_id} limit={limit}")
        data = self._request_json("GET", f"/channels/{channel_id}/messages?{query}")
        if not isinstance(data, list):
            raise DiscordApiError("Discord messages response was not a list")
        return [self._message_from_payload(item, channel_id=channel_id) for item in data if isinstance(item, dict)]

    def send_message(
        self,
        channel_id: str,
        content: str,
        *,
        attachment: bytes | None = None,
        filename: str = "screenshot.jpg",
    ) -> None:
        self._debug(
            "DISCORD REST send message "
            f"channel={channel_id} content_len={len(content)} "
            f"attachment_bytes={len(attachment or b'')} filename={filename!r}"
        )
        if attachment:
            self._send_multipart(channel_id, content, attachment=attachment, filename=filename)
            return
        self._request_json("POST", f"/channels/{channel_id}/messages", payload={"content": content})

    def _token(self) -> str:
        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise DiscordApiError(f"Discord token file is empty: {self.token_file}")
        self._debug(f"DISCORD REST token file read path={self.token_file} chars={len(token)}")
        return token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._token()}",
            "User-Agent": "AgentDev Pico HID Bridge",
            "Accept": "application/json",
        }

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None
        headers = self._headers()
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        self._debug(
            f"DISCORD REST request {method} {path} "
            f"json_bytes={len(body or b'')} timeout={self.timeout}"
        )
        req = request.Request(self.api_base + path, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                content = response.read()
                status = getattr(response, "status", response.getcode())
                self._debug(f"DISCORD REST response {method} {path} status={status} bytes={len(content)}")
        except error.HTTPError as exc:
            self._debug(f"DISCORD REST HTTPError {method} {path} status={exc.code}")
            self._raise_http_error(exc)
        except OSError as exc:
            self._debug(f"DISCORD REST OSError {method} {path}: {exc}")
            raise DiscordApiError(str(exc)) from exc
        return json.loads(content.decode("utf-8")) if content else {}

    def _send_multipart(self, channel_id: str, content: str, *, attachment: bytes, filename: str) -> None:
        boundary = f"agentdev-{int(time.time() * 1000)}"
        payload_json = json.dumps(
            {
                "content": content,
                "attachments": [{"id": 0, "filename": filename}],
            }
        )
        parts = [
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="payload_json"\r\n'
                "Content-Type: application/json\r\n\r\n"
            ).encode("utf-8")
            + payload_json.encode("utf-8")
            + b"\r\n",
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'
                "Content-Type: image/jpeg\r\n\r\n"
            ).encode("utf-8")
            + attachment
            + b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        headers = self._headers()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        multipart_body = b"".join(parts)
        self._debug(
            "DISCORD REST multipart request "
            f"channel={channel_id} content_len={len(content)} "
            f"attachment_bytes={len(attachment)} body_bytes={len(multipart_body)} filename={filename!r}"
        )
        req = request.Request(
            self.api_base + f"/channels/{channel_id}/messages",
            data=multipart_body,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                content = response.read()
                status = getattr(response, "status", response.getcode())
                self._debug(f"DISCORD REST multipart response status={status} bytes={len(content)}")
        except error.HTTPError as exc:
            self._debug(f"DISCORD REST multipart HTTPError status={exc.code}")
            self._raise_http_error(exc)
        except OSError as exc:
            self._debug(f"DISCORD REST multipart OSError: {exc}")
            raise DiscordApiError(str(exc)) from exc

    def _raise_http_error(self, exc: error.HTTPError) -> None:
        body = exc.read().decode("utf-8", errors="replace")
        self._debug(f"DISCORD REST error body: {body}")
        if exc.code == 429:
            retry_after = float(exc.headers.get("Retry-After", "0") or 0)
            try:
                retry_after = float(json.loads(body).get("retry_after", retry_after))
            except (ValueError, json.JSONDecodeError, AttributeError):
                pass
            raise DiscordRateLimitError(retry_after) from exc
        raise DiscordApiError(f"Discord API HTTP {exc.code}: {body}") from exc

    def _debug(self, message: str) -> None:
        if self.debug is not None:
            self.debug(message)

    def _message_from_payload(self, payload: dict[str, Any], *, channel_id: str) -> DiscordMessage:
        author = payload.get("author", {}) if isinstance(payload.get("author"), dict) else {}
        return DiscordMessage(
            id=str(payload.get("id", "")),
            content=str(payload.get("content", "")),
            author_id=str(author.get("id", "")),
            channel_id=str(payload.get("channel_id", channel_id)),
            guild_id=str(payload.get("guild_id", "")),
            timestamp=_parse_discord_timestamp(str(payload.get("timestamp", _utc_now().isoformat()))),
            author_is_bot=bool(author.get("bot", False)),
        )


class FlaskControlClient:
    def __init__(self, app: Any) -> None:
        self.app = app

    def request(self, command: str, *, planning: bool) -> dict[str, Any]:
        with self.app.test_client() as client:
            response = client.post("/api/command", json={"command": command, "planning": planning})
            return self._json_or_error(response)

    def manual_hid(self, command: str) -> dict[str, Any]:
        with self.app.test_client() as client:
            response = client.post("/api/manual-hid", json={"command": command})
            return self._json_or_error(response)

    def emergency_stop(self) -> dict[str, Any]:
        with self.app.test_client() as client:
            return self._json_or_error(client.post("/api/emergency-stop", json={}))

    def approve(self) -> dict[str, Any]:
        with self.app.test_client() as client:
            return self._json_or_error(client.post("/api/approve", json={}))

    def reject(self) -> dict[str, Any]:
        with self.app.test_client() as client:
            return self._json_or_error(client.post("/api/reject", json={}))

    def capture_screenshot(self) -> bytes:
        with self.app.test_client() as client:
            response = client.get("/api/screenshot")
            if response.status_code >= 400:
                raise RuntimeError(response.get_data(as_text=True))
            return bytes(response.data)

    def _json_or_error(self, response: Any) -> dict[str, Any]:
        data = response.get_json(silent=True) or {}
        if response.status_code >= 400:
            raise RuntimeError(str(data.get("error") or data or response.status))
        return dict(data)


class DiscordBotWorker:
    def __init__(
        self,
        config: dict[str, Any],
        store: OperationLogStore,
        *,
        discord_client: Any | None = None,
        control_client: Any | None = None,
        now: Any = _utc_now,
        console: bool = False,
    ) -> None:
        self.config = config
        self.discord_config = dict(config.get("discord", {}) or {})
        self.console = console
        self.store = store
        self.channel_id = str(self.discord_config.get("channel_id", "") or "")
        self.bot_name = str(self.discord_config.get("bot_name", "AgentDev") or "AgentDev")
        self.bot_user_id = str(self.discord_config.get("bot_user_id", "") or "")
        self.parser = DiscordCommandParser(bot_name=self.bot_name, bot_user_id=self.bot_user_id)
        self.discord_client = discord_client or DiscordRestClient(
            token_file=str(self.discord_config.get("token_file", "/home/nama/discord-api-key.txt")),
            timeout=float(self.discord_config.get("api_timeout", 15.0)),
            debug=self._console if console else None,
        )
        if control_client is None:
            raise ValueError("control_client is required unless a test double is provided")
        self.control_client = control_client
        self.now = now
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_seen_message_id = str(self.discord_config.get("last_seen_message_id", "") or "")
        self.last_seen_timestamp: datetime | None = None
        self.skip_existing_on_startup = bool(self.discord_config.get("skip_existing_on_startup", True))
        self._startup_poll_completed = bool(self.last_seen_message_id)
        self._recent_command_times: list[float] = []

    @property
    def enabled(self) -> bool:
        return bool(self.discord_config.get("enabled", False))

    def start(self) -> None:
        if not self.enabled or self.thread is not None:
            return
        self._console("DISCORD worker starting")
        self.thread = threading.Thread(target=self.run, name="discord-bot-worker", daemon=True)
        self.thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._console("DISCORD worker stopping")
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=timeout)

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.poll_once()
            except Exception as exc:
                self._record_notification("poll", "failed", message="discord polling failed", error=str(exc))
            self.stop_event.wait(float(self.discord_config.get("poll_interval_sec", 5.0)))

    def poll_once(self) -> None:
        if not self.enabled:
            self._console("DISCORD disabled")
            return
        if not self.channel_id:
            self._console("DISCORD configuration error: channel_id is not configured")
            self._record_notification("poll", "failed", message="discord channel_id is not configured")
            return

        try:
            self._console(f"DISCORD polling channel {self.channel_id}")
            messages = self.discord_client.fetch_recent_messages(
                self.channel_id,
                limit=int(self.discord_config.get("poll_limit", 20)),
            )
        except DiscordRateLimitError as exc:
            self._console(f"DISCORD rate limited: retry after {exc.retry_after}")
            self._record_notification("poll", "rate_limited", message=f"retry after {exc.retry_after}", error=str(exc))
            return
        except Exception as exc:
            self._console(f"DISCORD fetch failed: {exc}")
            self._record_notification("poll", "failed", message="discord fetch failed", error=str(exc))
            return

        if not messages:
            self._startup_poll_completed = True
            self._console("DISCORD no messages")
            return

        newest_seen = max(messages, key=_message_sort_key)
        if self.skip_existing_on_startup and not self._startup_poll_completed and not self.last_seen_message_id:
            self._mark_seen(newest_seen)
            self._startup_poll_completed = True
            self._console(f"DISCORD startup baseline set to message {newest_seen.id}; existing messages ignored")
            return

        fresh_messages = [message for message in messages if self._is_new_message(message)]
        self._mark_seen(newest_seen)
        self._startup_poll_completed = True
        if not fresh_messages:
            self._console("DISCORD no fresh messages")
            return

        latest = max(fresh_messages, key=_message_sort_key)
        self._console(
            "DISCORD latest message "
            f"id={latest.id} guild={latest.guild_id} channel={latest.channel_id} "
            f"author={latest.author_id} age_sec={command_age_seconds(latest, self.now()):.1f}"
        )
        command = self.parser.parse(latest.content)
        if command is None:
            self._console(f"DISCORD ignored non-command message {latest.id}")
            return
        scope = DiscordScope(guild_id=latest.guild_id, channel_id=latest.channel_id, user_id=latest.author_id)
        if latest.author_is_bot:
            self._console(f"DISCORD ignored bot message {latest.id}")
            return
        authorized, auth_reason = self._authorization_result(scope)
        self._console(f"DISCORD authorization {auth_reason}")
        if not authorized:
            self._console(
                f"DISCORD denied message {latest.id} from {latest.author_id}; "
                f"scope guild={scope.guild_id} channel={scope.channel_id} user={scope.user_id}; "
                f"allow guilds={_as_list(self.discord_config.get('allowed_guild_ids') or self.discord_config.get('guild_id'))} "
                f"channels={_as_list(self.discord_config.get('allowed_channel_ids') or self.discord_config.get('channel_id'))} "
                f"users={_as_list(self.discord_config.get('allowed_user_ids') or self.discord_config.get('user_id'))}"
            )
            self._record_operation(command=latest.content, status="denied", error="unauthorized Discord source")
            return
        if command_age_seconds(latest, self.now()) > self.max_command_age_seconds():
            self._console(f"DISCORD ignored stale message {latest.id}")
            self._record_operation(command=latest.content, status="stale", message="stale Discord command ignored")
            return
        if not self._consume_rate_limit():
            self._console(f"DISCORD rate-limited command {latest.id}")
            self._record_operation(command=latest.content, status="rate_limited", message="Discord command rate limited")
            self._record_notification("command", "rate_limited", message="Discord command rate limited")
            return
        self._console(f"DISCORD command {command.kind} from {latest.author_id}: {command.text or command.kind}")
        self._execute_command(command, channel_id=latest.channel_id)

    def _is_new_message(self, message: DiscordMessage) -> bool:
        if self.last_seen_message_id:
            try:
                return int(message.id) > int(self.last_seen_message_id)
            except ValueError:
                pass
        if self.last_seen_timestamp is not None:
            return message.timestamp > self.last_seen_timestamp
        return True

    def _mark_seen(self, message: DiscordMessage) -> None:
        self.last_seen_message_id = message.id
        self.last_seen_timestamp = message.timestamp

    def _is_authorized(self, scope: DiscordScope) -> bool:
        authorized, _reason = self._authorization_result(scope)
        return authorized

    def _authorization_result(self, scope: DiscordScope) -> tuple[bool, str]:
        guild_ids = _as_list(self.discord_config.get("allowed_guild_ids") or self.discord_config.get("guild_id"))
        channel_ids = _as_list(self.discord_config.get("allowed_channel_ids") or self.discord_config.get("channel_id"))
        user_ids = _as_list(self.discord_config.get("allowed_user_ids") or self.discord_config.get("user_id"))
        if not guild_ids or not channel_ids or not user_ids:
            return False, "failed: allowlist is incomplete"
        if scope.channel_id not in channel_ids:
            return False, "failed: channel not allowed"
        if scope.user_id not in user_ids:
            return False, "failed: user not allowed"
        if not scope.guild_id:
            return True, "ok: guild missing in message payload; channel and user allowlist matched"
        if scope.guild_id not in guild_ids:
            return False, "failed: guild not allowed"
        return True, "ok: guild, channel, and user allowlist matched"

    def _consume_rate_limit(self) -> bool:
        limit = int(self.discord_config.get("rate_limit_per_hour", 0) or 0)
        if limit <= 0:
            return True
        now_monotonic = time.monotonic()
        cutoff = now_monotonic - 3600.0
        self._recent_command_times = [value for value in self._recent_command_times if value >= cutoff]
        if len(self._recent_command_times) >= limit:
            return False
        self._recent_command_times.append(now_monotonic)
        return True

    def max_command_age_seconds(self) -> float:
        return max(0.0, float(self.discord_config.get("max_command_age_sec", 60.0)))

    def attachment_limit_bytes(self) -> int:
        return int(float(self.discord_config.get("attachment_limit_mb", 8)) * 1024 * 1024)

    def _execute_command(self, command: DiscordCommand, *, channel_id: str) -> None:
        self.store.record_user_input(input_text=command.text or command.kind, source="discord", planning=command.planning)
        try:
            if command.kind == "screen":
                screenshot = self.control_client.capture_screenshot()
                self._send_screenshot(channel_id, "Current screenshot", screenshot)
                self._record_operation(command="screen", status="sent", message="screenshot sent")
                self._console("DISCORD command screen completed")
                return
            if command.kind == "hid":
                result = self.control_client.manual_hid(command.text)
                self._send_text(channel_id, str(result.get("message", "manual HID command completed")))
                self._record_operation(command=command.text, status="sent", message="manual HID command completed")
                self._console("DISCORD command hid completed")
                return
            if command.kind == "stop":
                result = self.control_client.emergency_stop()
                self._send_text(channel_id, str(result.get("message", "emergency stop requested")))
                self._record_operation(command="stop", status="sent", message="emergency stop requested")
                self._console("DISCORD command stop completed")
                return
            if command.kind == "approve":
                result = self.control_client.approve()
                self._send_text(channel_id, str(result.get("message", "approval accepted")))
                self._record_operation(command="approve", status="sent", message="approval accepted")
                self._console("DISCORD command approve completed")
                return
            if command.kind == "reject":
                result = self.control_client.reject()
                self._send_text(channel_id, str(result.get("message", "approval rejected")))
                self._record_operation(command="reject", status="sent", message="approval rejected")
                self._console("DISCORD command reject completed")
                return

            result = self.control_client.request(command.text, planning=command.planning)
            screenshot = self.control_client.capture_screenshot()
            self._send_screenshot(channel_id, str(result.get("message", "operation completed")), screenshot)
            self._record_operation(command=command.text, status="sent", message="planned request completed")
            self._console("DISCORD command request completed")
        except Exception as exc:
            self._console(f"DISCORD command failed: {exc}")
            self._record_operation(command=command.text or command.kind, status="failed", error=str(exc))
            self._send_text(channel_id, f"Command failed: {exc}")

    def _send_screenshot(self, channel_id: str, content: str, screenshot: bytes) -> None:
        attachment_policy = "attached"
        attachment: bytes | None = screenshot
        limit = self.attachment_limit_bytes()
        self._console(
            f"DISCORD prepare screenshot send channel={channel_id} bytes={len(screenshot)} "
            f"limit={limit} content_len={len(content)}"
        )
        if limit > 0 and len(screenshot) > limit:
            attachment_policy = "omitted"
            attachment = None
            content = f"{content}\nScreenshot omitted because it exceeds the configured attachment limit."
        self.discord_client.send_message(
            channel_id,
            content,
            attachment=attachment,
            filename="screenshot.jpg" if attachment is not None else "",
        )
        self._console(f"DISCORD send screenshot {attachment_policy} bytes={len(screenshot)}")
        self._record_notification(
            "screen",
            "sent",
            message=content,
            attachment_policy=attachment_policy,
            attachment_bytes=len(screenshot),
        )

    def _send_text(self, channel_id: str, content: str) -> None:
        self._console(f"DISCORD prepare text send channel={channel_id} content_len={len(content)}")
        self.discord_client.send_message(channel_id, content)
        self._console(f"DISCORD send message: {content}")
        self._record_notification("message", "sent", message=content)

    def _console(self, message: str) -> None:
        if self.console:
            print(message, flush=True)

    def _record_operation(
        self,
        *,
        command: str,
        status: str,
        message: str = "",
        error: str = "",
    ) -> None:
        operation_id = self.store.record_operation(
            command=command,
            normalized="DISCORD",
            status=status,
            source="discord",
            error=error,
            message=message,
        )
        if error:
            self.store.record_error(
                message=error,
                domain="discord",
                operation_id=operation_id,
            )

    def _record_notification(
        self,
        event: str,
        status: str,
        *,
        message: str = "",
        error: str = "",
        attachment_policy: str = "",
        attachment_bytes: int = 0,
    ) -> None:
        self.store.record_notification(
            channel="discord",
            event=event,
            status=status,
            recipient=self.channel_id,
            message=message,
            error=error,
            attachment_policy=attachment_policy,
            attachment_bytes=attachment_bytes,
            source="discord",
        )


__all__ = [
    "DiscordApiError",
    "DiscordBotWorker",
    "DiscordCommand",
    "DiscordCommandParser",
    "DiscordMessage",
    "DiscordRateLimitError",
    "DiscordRestClient",
    "DiscordScope",
    "FlaskControlClient",
]
