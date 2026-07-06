"""SQLite-backed operation log storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def token_prediction_log_message(data: dict[str, Any]) -> str:
    estimated = int(data.get("estimated_tokens", 0) or 0)
    step_count = int(data.get("step_count", 0) or 0)
    return f"estimated {estimated} tokens for {step_count} step(s): {data.get('message', '')}"


def _row_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


@dataclass
class OperationLogStore:
    database_path: Path
    screenshot_dir: Path
    max_screenshots: int = 5000
    recovery_performed: bool = False

    def __post_init__(self) -> None:
        self.database_path = Path(self.database_path)
        self.screenshot_dir = Path(self.screenshot_dir)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema_with_recovery()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "OperationLogStore":
        from .paths import resolve_path

        logs = config["logs"]
        app = config["app"]
        database = logs.get("database") or (Path(str(app["runtime_dir"])) / "app.db")
        return cls(
            database_path=resolve_path(database),
            screenshot_dir=resolve_path(logs["screenshot_dir"]),
            max_screenshots=int(logs.get("max_screenshots", 5000)),
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema_with_recovery(self) -> None:
        try:
            self.ensure_schema()
        except sqlite3.DatabaseError:
            self._move_corrupt_database()
            self.recovery_performed = True
            self.ensure_schema()

    def _move_corrupt_database(self) -> None:
        if not self.database_path.exists():
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        corrupt_path = self.database_path.with_name(f"{self.database_path.name}.corrupt-{stamp}")
        shutil.move(str(self.database_path), str(corrupt_path))

    def ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS user_input_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    input TEXT NOT NULL,
                    source TEXT NOT NULL,
                    planning INTEGER NOT NULL DEFAULT 0,
                    case_name TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS operation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    command TEXT NOT NULL,
                    normalized TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    case_name TEXT NOT NULL DEFAULT '',
                    action_type TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS screenshot_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    path TEXT NOT NULL,
                    event TEXT NOT NULL,
                    case_name TEXT NOT NULL DEFAULT '',
                    step_name TEXT NOT NULL DEFAULT '',
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    mean_brightness REAL NOT NULL DEFAULT 0.0
                );
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    message TEXT NOT NULL,
                    domain TEXT NOT NULL DEFAULT '',
                    case_name TEXT NOT NULL DEFAULT '',
                    operation_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS system_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS token_usage_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    phase TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    response_id TEXT NOT NULL DEFAULT '',
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_tokens INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT '',
                    case_name TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS notification_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    event TEXT NOT NULL,
                    status TEXT NOT NULL,
                    recipient TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    attachment_policy TEXT NOT NULL DEFAULT '',
                    attachment_bytes INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT '',
                    case_name TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_user_input_source ON user_input_log(source);
                CREATE INDEX IF NOT EXISTS idx_user_input_created ON user_input_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_operation_status ON operation_log(status);
                CREATE INDEX IF NOT EXISTS idx_operation_source ON operation_log(source);
                CREATE INDEX IF NOT EXISTS idx_operation_case ON operation_log(case_name);
                CREATE INDEX IF NOT EXISTS idx_operation_created ON operation_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_screenshot_case ON screenshot_log(case_name);
                CREATE INDEX IF NOT EXISTS idx_screenshot_created ON screenshot_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_error_case ON error_log(case_name);
                CREATE INDEX IF NOT EXISTS idx_error_created ON error_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_system_created ON system_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_token_created ON token_usage_log(created_at);
                CREATE INDEX IF NOT EXISTS idx_notification_channel ON notification_log(channel);
                CREATE INDEX IF NOT EXISTS idx_notification_event ON notification_log(event);
                CREATE INDEX IF NOT EXISTS idx_notification_created ON notification_log(created_at);
                """
            )

    def record_user_input(
        self,
        *,
        input_text: str,
        source: str,
        planning: bool = False,
        case_name: str = "",
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO user_input_log (created_at, input, source, planning, case_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (created_at or now_iso(), input_text, source, int(planning), case_name),
            )
            return int(cursor.lastrowid)

    def record_operation(
        self,
        *,
        command: str,
        status: str,
        normalized: str = "",
        source: str = "",
        case_name: str = "",
        action_type: str = "",
        error: str = "",
        message: str = "",
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO operation_log
                    (created_at, command, normalized, status, source, case_name, action_type, error, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at or now_iso(),
                    command,
                    normalized,
                    status,
                    source,
                    case_name,
                    action_type,
                    error,
                    message,
                ),
            )
            return int(cursor.lastrowid)

    def record_screenshot(
        self,
        *,
        path: Path | str,
        event: str,
        case_name: str = "",
        step_name: str = "",
        width: int = 0,
        height: int = 0,
        mean_brightness: float = 0.0,
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO screenshot_log
                    (created_at, path, event, case_name, step_name, width, height, mean_brightness)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at or now_iso(),
                    str(path),
                    event,
                    case_name,
                    step_name,
                    int(width),
                    int(height),
                    float(mean_brightness),
                ),
            )
            screenshot_id = int(cursor.lastrowid)
        self.enforce_screenshot_limit()
        return screenshot_id

    def record_error(
        self,
        *,
        message: str,
        domain: str = "",
        case_name: str = "",
        operation_id: int | None = None,
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO error_log (created_at, message, domain, case_name, operation_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (created_at or now_iso(), message, domain, case_name, operation_id),
            )
            return int(cursor.lastrowid)

    def record_system(
        self,
        *,
        event: str,
        status: str = "",
        message: str = "",
        source: str = "",
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO system_log (created_at, event, status, message, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (created_at or now_iso(), event, status, message, source),
            )
            return int(cursor.lastrowid)

    def record_token_usage(
        self,
        *,
        phase: str = "",
        model: str = "",
        response_id: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_tokens: int = 0,
        source: str = "",
        case_name: str = "",
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO token_usage_log
                    (created_at, phase, model, response_id, input_tokens, output_tokens,
                     total_tokens, estimated_tokens, source, case_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at or now_iso(),
                    phase,
                    model,
                    response_id,
                    int(input_tokens),
                    int(output_tokens),
                    int(total_tokens),
                    int(estimated_tokens),
                    source,
                    case_name,
                ),
            )
            return int(cursor.lastrowid)

    def record_notification(
        self,
        *,
        channel: str,
        event: str,
        status: str,
        recipient: str = "",
        subject: str = "",
        message: str = "",
        error: str = "",
        attachment_policy: str = "",
        attachment_bytes: int = 0,
        source: str = "",
        case_name: str = "",
        created_at: str | None = None,
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO notification_log
                    (created_at, channel, event, status, recipient, subject, message, error,
                     attachment_policy, attachment_bytes, source, case_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at or now_iso(),
                    channel,
                    event,
                    status,
                    recipient,
                    subject,
                    message,
                    error,
                    attachment_policy,
                    int(attachment_bytes),
                    source,
                    case_name,
                ),
            )
            return int(cursor.lastrowid)

    def query_user_inputs(
        self,
        *,
        source: str | None = None,
        case_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._query(
            "user_input_log",
            filters={"source": source, "case_name": case_name},
            limit=limit,
        )

    def query_operations(
        self,
        *,
        source: str | None = None,
        status: str | None = None,
        case_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._query(
            "operation_log",
            filters={"source": source, "status": status, "case_name": case_name},
            limit=limit,
        )

    def query_screenshots(
        self,
        *,
        case_name: str | None = None,
        event: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._query(
            "screenshot_log",
            filters={"case_name": case_name, "event": event},
            limit=limit,
        )

    def query_errors(self, *, case_name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._query("error_log", filters={"case_name": case_name}, limit=limit)

    def query_system(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._query("system_log", filters={}, limit=limit)

    def query_token_usage(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if start_at or end_at:
            return self._query_time_range("token_usage_log", start_at=start_at, end_at=end_at, limit=limit)
        return self._query("token_usage_log", filters={}, limit=limit)

    def query_notifications(
        self,
        *,
        channel: str | None = None,
        event: str | None = None,
        status: str | None = None,
        case_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._query(
            "notification_log",
            filters={"channel": channel, "event": event, "status": status, "case_name": case_name},
            limit=limit,
        )

    def query_token_totals(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> dict[str, int]:
        clauses = []
        values: list[Any] = []
        if start_at:
            clauses.append("created_at >= ?")
            values.append(start_at)
        if end_at:
            clauses.append("created_at <= ?")
            values.append(end_at)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as connection:
            row = connection.execute(
                f"""
                SELECT
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(estimated_tokens), 0) AS estimated_tokens
                FROM token_usage_log{where}
                """,
                values,
            ).fetchone()
        totals = dict(row)
        return {key: int(value or 0) for key, value in totals.items()}

    def estimate_tokens_per_operation(self, *, default: int, limit: int = 50) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT total_tokens, estimated_tokens
                FROM token_usage_log
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            rows = _row_dicts(cursor)
        samples = [
            int(row["total_tokens"] or row["estimated_tokens"] or 0)
            for row in rows
            if int(row["total_tokens"] or row["estimated_tokens"] or 0) > 0
        ]
        if not samples:
            return max(1, int(default))
        return max(1, int(round(sum(samples) / len(samples))))

    def query_detail_logs(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int = 500,
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "user_logs": self._query_time_range("user_input_log", start_at=start_at, end_at=end_at, limit=limit),
            "operation_logs": self._query_time_range("operation_log", start_at=start_at, end_at=end_at, limit=limit),
            "system_logs": self._query_time_range("system_log", start_at=start_at, end_at=end_at, limit=limit),
            "screenshot_logs": self._query_time_range("screenshot_log", start_at=start_at, end_at=end_at, limit=limit),
            "error_logs": self._query_time_range("error_log", start_at=start_at, end_at=end_at, limit=limit),
            "token_usage": self._query_time_range("token_usage_log", start_at=start_at, end_at=end_at, limit=limit),
            "notification_logs": self._query_time_range(
                "notification_log",
                start_at=start_at,
                end_at=end_at,
                limit=limit,
            ),
        }

    def _query(self, table: str, *, filters: dict[str, str | None], limit: int) -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        for column, value in filters.items():
            if value is None:
                continue
            clauses.append(f"{column} = ?")
            values.append(value)

        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(max(1, int(limit)))
        with self.connect() as connection:
            cursor = connection.execute(
                f"SELECT * FROM {table}{where} ORDER BY id ASC LIMIT ?",
                values,
            )
            return _row_dicts(cursor)

    def _query_time_range(
        self,
        table: str,
        *,
        start_at: str | None,
        end_at: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if start_at:
            clauses.append("created_at >= ?")
            values.append(start_at)
        if end_at:
            clauses.append("created_at <= ?")
            values.append(end_at)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(max(1, int(limit)))
        with self.connect() as connection:
            cursor = connection.execute(
                f"SELECT * FROM {table}{where} ORDER BY created_at ASC, id ASC LIMIT ?",
                values,
            )
            return _row_dicts(cursor)

    def enforce_screenshot_limit(self) -> None:
        if self.max_screenshots <= 0:
            return

        with self.connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, path FROM screenshot_log
                ORDER BY id DESC
                LIMIT -1 OFFSET ?
                """,
                (self.max_screenshots,),
            )
            stale_rows = _row_dicts(cursor)
            if not stale_rows:
                return

            stale_ids = [int(row["id"]) for row in stale_rows]
            placeholders = ",".join("?" for _ in stale_ids)
            connection.execute(f"DELETE FROM screenshot_log WHERE id IN ({placeholders})", stale_ids)

        for row in stale_rows:
            self._remove_screenshot_file(Path(str(row["path"])))

    def _remove_screenshot_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            root = self.screenshot_dir.resolve()
            if resolved == root or root not in resolved.parents:
                return
            if resolved.exists():
                resolved.unlink()
        except OSError:
            return


@dataclass
class OperationLogEventSink:
    store: OperationLogStore
    source: str = "e2e"
    case_name: str = ""

    def emit(self, event: Any) -> None:
        data = getattr(event, "data", {}) or {}
        message = str(getattr(event, "message", ""))
        kind = str(getattr(event, "kind", ""))
        created_at = str(getattr(event, "created_at", now_iso()))

        if kind in {"hid.attempt", "hid.sent"}:
            line = str(data.get("line", message))
            self.store.record_operation(
                command=line,
                normalized=line,
                status="attempting" if kind == "hid.attempt" else "sent",
                source=self.source,
                case_name=self.case_name,
                action_type=line.split(" ", 1)[0],
                message=message,
                created_at=created_at,
            )
            return

        if kind == "action.wait":
            self.store.record_operation(
                command="WAIT",
                status="sent",
                source=self.source,
                case_name=self.case_name,
                action_type="wait",
                message=message,
                created_at=created_at,
            )
            return

        if kind in {"action.unsupported", "action.skipped"}:
            operation_id = self.store.record_operation(
                command=str(data.get("action", message)),
                status="failed",
                source=self.source,
                case_name=self.case_name,
                action_type=kind,
                error=message,
                created_at=created_at,
            )
            self.store.record_error(
                message=message,
                domain="implementation",
                case_name=self.case_name,
                operation_id=operation_id,
                created_at=created_at,
            )
            return

        if kind == "token.usage":
            if not bool(data.get("usage_known", True)):
                estimated_tokens = int(data.get("estimated_tokens", 0) or 0)
                self.store.record_system(
                    event="token_usage",
                    status="unknown",
                    message=f"token usage metadata missing; estimated {estimated_tokens} tokens",
                    source=self.source,
                    created_at=created_at,
                )
            self.store.record_token_usage(
                phase=str(data.get("phase", "")),
                model=str(data.get("model", "")),
                response_id=str(data.get("response_id", "")),
                input_tokens=int(data.get("input_tokens", 0) or 0),
                output_tokens=int(data.get("output_tokens", 0) or 0),
                total_tokens=int(data.get("total_tokens", 0) or 0),
                estimated_tokens=int(data.get("estimated_tokens", 0) or 0),
                source=self.source,
                case_name=self.case_name,
                created_at=created_at,
            )
            return

        if kind == "token.prediction":
            self.store.record_system(
                event="token_budget",
                status="predicted",
                message=token_prediction_log_message(data),
                source=self.source,
                created_at=created_at,
            )
            return
