"""Notification extension points for email and Discord integrations."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
import time
from typing import Any

from .actions import CompositeEventSink, EventSink, NullEventSink, PipelineEvent, PrintEventSink
from .operation_log import OperationLogStore


@dataclass(frozen=True)
class SmtpAccount:
    starttls: bool
    smtp_server: str
    smtp_port: int
    sender_mail: str
    smtp_password: str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "starttls"}


def parse_smtp_account_file(path: str | Path) -> SmtpAccount:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
        else:
            continue
        values[key.strip().upper()] = value.strip().strip("\"'")

    def require(name: str) -> str:
        value = values.get(name, "")
        if not value:
            raise ValueError(f"SMTP account file is missing {name}")
        return value

    return SmtpAccount(
        starttls=_parse_bool(values.get("STARTTLS", "false")),
        smtp_server=require("SMTP_SERVER"),
        smtp_port=int(require("SMTP_PORT")),
        sender_mail=require("SENDER_MAIL"),
        smtp_password=require("SMTP_PASSWORD"),
    )


class EmailNotificationSink:
    def __init__(
        self,
        config: dict[str, Any],
        store: OperationLogStore,
        *,
        source: str = "web",
        case_name: str = "",
        smtp_class: type[Any] = smtplib.SMTP,
        smtp_ssl_class: type[Any] = smtplib.SMTP_SSL,
    ) -> None:
        self.config = config
        self.store = store
        self.source = source
        self.case_name = case_name
        self.smtp_class = smtp_class
        self.smtp_ssl_class = smtp_ssl_class
        self._last_sent_at: dict[tuple[str, str], float] = {}

    @property
    def email_config(self) -> dict[str, Any]:
        return dict(self.config.get("email", {}) or {})

    def notify(self, event: str, subject: str, body: str, *, screenshot: bytes | None = None) -> None:
        email_cfg = self.email_config
        if not bool(email_cfg.get("enabled", False)):
            self._record(event=event, status="skipped", subject=subject, message="email disabled")
            return

        try:
            account = parse_smtp_account_file(str(email_cfg.get("smtp_account_file", "")))
            recipients = self._recipients(email_cfg, account)
            recipient_text = ", ".join(recipients)
            rate_key = (event, recipient_text)
            now = time.monotonic()
            min_interval = self._min_interval_seconds(email_cfg)
            if min_interval > 0 and now - self._last_sent_at.get(rate_key, -min_interval) < min_interval:
                self._record(
                    event=event,
                    status="rate_limited",
                    recipient=recipient_text,
                    subject=subject,
                    message="duplicate notification suppressed",
                )
                return

            message, attachment_policy, attachment_bytes = self._build_message(
                account=account,
                recipients=recipients,
                subject=subject,
                body=body,
                screenshot=screenshot,
                email_cfg=email_cfg,
            )
            send_message = self._send(account, message, delivery=str(email_cfg.get("delivery", "smtp")))
            self._last_sent_at[rate_key] = now
            self._record(
                event=event,
                status="sent",
                recipient=recipient_text,
                subject=subject,
                message=send_message,
                attachment_policy=attachment_policy,
                attachment_bytes=attachment_bytes,
            )
        except Exception as exc:
            self._record(event=event, status="failed", subject=subject, error=str(exc))

    def _recipients(self, email_cfg: dict[str, Any], account: SmtpAccount) -> list[str]:
        configured = email_cfg.get("to_addrs", [])
        if isinstance(configured, str):
            recipients = [configured]
        else:
            recipients = [str(value) for value in configured or []]
        recipients = [value.strip() for value in recipients if value.strip()]
        return recipients or [account.sender_mail]

    def _min_interval_seconds(self, email_cfg: dict[str, Any]) -> float:
        if "min_interval_sec" in email_cfg:
            return max(0.0, float(email_cfg.get("min_interval_sec", 0)))
        rate_limit = int(email_cfg.get("rate_limit_per_hour", 0) or 0)
        return 3600.0 / rate_limit if rate_limit > 0 else 0.0

    def _build_message(
        self,
        *,
        account: SmtpAccount,
        recipients: list[str],
        subject: str,
        body: str,
        screenshot: bytes | None,
        email_cfg: dict[str, Any],
    ) -> tuple[EmailMessage, str, int]:
        message = EmailMessage()
        message["From"] = str(email_cfg.get("from_addr") or account.sender_mail)
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)

        attachment_policy = "none"
        attachment_bytes = len(screenshot or b"")
        if screenshot:
            limit = int(float(email_cfg.get("attachment_limit_mb", 10)) * 1024 * 1024)
            if limit > 0 and attachment_bytes <= limit:
                message.add_attachment(screenshot, maintype="image", subtype="jpeg", filename="screenshot.jpg")
                attachment_policy = "attached"
            else:
                attachment_policy = "omitted"
        return message, attachment_policy, attachment_bytes

    def _send(self, account: SmtpAccount, message: EmailMessage, *, delivery: str = "smtp") -> str:
        if delivery.strip().lower() == "console":
            self._print_console_message(message)
            return "console send printed"

        context = ssl.create_default_context()
        if account.starttls:
            with self.smtp_class(account.smtp_server, account.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(account.sender_mail, account.smtp_password)
                server.send_message(message)
            return "SMTP send succeeded"

        with self.smtp_ssl_class(account.smtp_server, account.smtp_port, context=context) as server:
            server.login(account.sender_mail, account.smtp_password)
            server.send_message(message)
        return "SMTP send succeeded"

    def _print_console_message(self, message: EmailMessage) -> None:
        print("EMAIL CONSOLE SEND")
        print(f"From: {message.get('From', '')}")
        print(f"To: {message.get('To', '')}")
        print(f"Subject: {message.get('Subject', '')}")
        body = message.get_body(preferencelist=("plain",))
        if body is not None:
            print(body.get_content().rstrip())
        attachment_count = sum(1 for part in message.iter_attachments())
        if attachment_count:
            print(f"Attachments: {attachment_count}")
        print("EMAIL CONSOLE END")

    def _record(
        self,
        *,
        event: str,
        status: str,
        recipient: str = "",
        subject: str = "",
        message: str = "",
        error: str = "",
        attachment_policy: str = "",
        attachment_bytes: int = 0,
    ) -> None:
        self.store.record_notification(
            channel="email",
            event=event,
            status=status,
            recipient=recipient,
            subject=subject,
            message=message,
            error=error,
            attachment_policy=attachment_policy,
            attachment_bytes=attachment_bytes,
            source=self.source,
            case_name=self.case_name,
        )


class DiscordNotificationSink(NullEventSink):
    """Placeholder sink for future Discord notifications and chat operations."""


__all__ = [
    "CompositeEventSink",
    "DiscordNotificationSink",
    "EmailNotificationSink",
    "EventSink",
    "NullEventSink",
    "PipelineEvent",
    "PrintEventSink",
    "SmtpAccount",
    "parse_smtp_account_file",
]
