from __future__ import annotations

from pathlib import Path
from typing import Any

from pico_hid_bridge.config import load_config
from pico_hid_bridge.notifications import EmailNotificationSink, parse_smtp_account_file
from pico_hid_bridge.operation_log import OperationLogStore


class FakeSmtp:
    sent_messages: list[Any] = []
    login_calls: list[tuple[str, str]] = []
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, *args: Any, **kwargs: Any) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        FakeSmtp.instances.append(self)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self, *, context: Any) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        FakeSmtp.login_calls.append((username, password))

    def send_message(self, message: Any) -> None:
        FakeSmtp.sent_messages.append(message)


class FailingSmtp(FakeSmtp):
    def login(self, username: str, password: str) -> None:
        raise RuntimeError("SMTP authentication failed")


class ForbiddenSmtp(FakeSmtp):
    def __init__(self, host: str, port: int, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("console delivery must not open SMTP")


def make_store(tmp_path: Path) -> OperationLogStore:
    return OperationLogStore(tmp_path / "runtime" / "app.db", tmp_path / "runtime" / "screenshots")


def make_account_file(tmp_path: Path) -> Path:
    path = tmp_path / "mail-send-vert.txt"
    path.write_text(
        "\n".join(
            [
                "STARTTLS=true",
                "SMTP_SERVER=smtp.example.test",
                "SMTP_PORT=587",
                "SENDER_MAIL=sender@example.test",
                "SMTP_PASSWORD=secret-password",
            ]
        ),
        encoding="utf-8",
    )
    return path


def make_config(tmp_path: Path, *, enabled: bool = True) -> dict[str, Any]:
    config = load_config(None)
    config["email"].update(
        {
            "enabled": enabled,
            "smtp_account_file": str(make_account_file(tmp_path)),
            "to_addrs": [],
            "min_interval_sec": 300,
            "attachment_limit_mb": 1,
        }
    )
    return config


def test_parse_smtp_account_file_accepts_pi_key_names(tmp_path: Path) -> None:
    account = parse_smtp_account_file(make_account_file(tmp_path))

    assert account.starttls is True
    assert account.smtp_server == "smtp.example.test"
    assert account.smtp_port == 587
    assert account.sender_mail == "sender@example.test"
    assert account.smtp_password == "secret-password"


def test_email_notification_sends_to_configured_recipient_and_logs_success(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    config = make_config(tmp_path)
    config["email"]["to_addrs"] = ["operator@example.test"]
    sink = EmailNotificationSink(config, store, smtp_class=FakeSmtp, smtp_ssl_class=FakeSmtp)

    sink.notify("completion", "Done", "The operation completed.")

    rows = store.query_notifications()
    assert rows[0]["channel"] == "email"
    assert rows[0]["event"] == "completion"
    assert rows[0]["status"] == "sent"
    assert rows[0]["recipient"] == "operator@example.test"
    assert FakeSmtp.sent_messages[0]["To"] == "operator@example.test"


def test_email_notification_console_delivery_prints_without_smtp(tmp_path: Path, capsys: Any) -> None:
    store = make_store(tmp_path)
    config = make_config(tmp_path)
    config["email"]["delivery"] = "console"
    sink = EmailNotificationSink(config, store, smtp_class=ForbiddenSmtp, smtp_ssl_class=ForbiddenSmtp)

    sink.notify("completion", "Done", "The operation completed.")

    output = capsys.readouterr().out
    rows = store.query_notifications()
    assert "EMAIL CONSOLE SEND" in output
    assert "Subject: Done" in output
    assert "sender@example.test" in output
    assert "secret-password" not in output
    assert rows[0]["status"] == "sent"
    assert rows[0]["message"] == "console send printed"


def test_email_notification_defaults_to_smtp_account_recipient(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    sink = EmailNotificationSink(make_config(tmp_path), store, smtp_class=FakeSmtp, smtp_ssl_class=FakeSmtp)

    sink.notify("completion", "Done", "Self recipient.")

    assert store.query_notifications()[0]["recipient"] == "sender@example.test"
    assert FakeSmtp.sent_messages[-1]["To"] == "sender@example.test"


def test_email_notification_disabled_logs_skipped_without_smtp(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    sink = EmailNotificationSink(make_config(tmp_path, enabled=False), store, smtp_class=FakeSmtp, smtp_ssl_class=FakeSmtp)

    sink.notify("completion", "Done", "Disabled.")

    rows = store.query_notifications()
    assert rows[0]["status"] == "skipped"
    assert rows[0]["message"] == "email disabled"


def test_email_notification_rate_limits_duplicate_events(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    sink = EmailNotificationSink(make_config(tmp_path), store, smtp_class=FakeSmtp, smtp_ssl_class=FakeSmtp)

    sink.notify("emergency", "Emergency", "Stop requested.")
    sink.notify("emergency", "Emergency", "Stop requested again.")

    rows = store.query_notifications()
    assert [row["status"] for row in rows] == ["sent", "rate_limited"]


def test_email_notification_logs_smtp_failure_without_raising(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    sink = EmailNotificationSink(make_config(tmp_path), store, smtp_class=FailingSmtp, smtp_ssl_class=FailingSmtp)

    sink.notify("completion", "Done", "This should fail safely.")

    rows = store.query_notifications()
    assert rows[0]["status"] == "failed"
    assert "authentication" in rows[0]["error"].lower()


def test_email_notification_omits_oversized_attachment_and_logs_policy(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    config = make_config(tmp_path)
    config["email"]["attachment_limit_mb"] = 0.000001
    sink = EmailNotificationSink(config, store, smtp_class=FakeSmtp, smtp_ssl_class=FakeSmtp)

    sink.notify("completion", "Done", "Large screenshot.", screenshot=b"x" * 100)

    rows = store.query_notifications()
    assert rows[0]["status"] == "sent"
    assert rows[0]["attachment_policy"] == "omitted"
