"""UART HID command helpers."""

from __future__ import annotations

import time
from typing import Any

import serial


DEFAULT_PORT = "/dev/serial0"
DEFAULT_BAUDRATE = 115200
DEFAULT_TIMEOUT = 0.5
TEXT_MAX_LENGTH = 256
TEXT_UART_CHUNK_LENGTH = 20
MAX_LINE_LENGTH = len("TEXT ") + TEXT_MAX_LENGTH + 1
TEXT_CHAR_SETTLE_SECONDS = 0.08
ACK_OK = "PICO_HID_OK"
ACK_ERR = "PICO_HID_ERR"
ACK_TIMEOUT_BASE_SECONDS = 2.0
COMMAND_PREFIXES = ("TEXT", "KEY", "MOUSE_MOVE", "CLICK", "PING")

SUPPORTED_KEY_NAMES = {
    "ENTER": "ENTER",
    "RETURN": "ENTER",
    "ESC": "ESC",
    "ESCAPE": "ESC",
    "BACKSPACE": "BACKSPACE",
    "TAB": "TAB",
    "SPACE": "SPACE",
    "DELETE": "DELETE",
    "DEL": "DELETE",
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
    "CTRL": "CTRL",
    "CONTROL": "CTRL",
    "SHIFT": "SHIFT",
    "ALT": "ALT",
    "WIN": "WIN",
    "GUI": "WIN",
    "META": "WIN",
    "CMD": "WIN",
}
MODIFIER_KEYS = {"CTRL", "SHIFT", "ALT", "WIN"}


def send_line(
    line: str,
    *,
    port: str = DEFAULT_PORT,
    baudrate: int = DEFAULT_BAUDRATE,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    if "\n" in line or "\r" in line:
        raise ValueError("line must not contain newline characters")

    uart_lines = split_uart_lines(line)
    ack_timeout = command_ack_timeout(uart_lines[0], timeout)
    with serial.Serial(port, baudrate, timeout=ack_timeout) as ser:
        for uart_line in uart_lines:
            send_uart_line(ser, uart_line, timeout)


def split_uart_lines(line: str) -> list[str]:
    encoded = f"{line}\n".encode("ascii")
    if len(encoded) > MAX_LINE_LENGTH:
        raise ValueError(f"line is too long: max {MAX_LINE_LENGTH - 1} ASCII chars")

    prefix = "TEXT "
    if not line.startswith(prefix):
        return [line]

    text = line.removeprefix(prefix)
    if len(text) <= TEXT_UART_CHUNK_LENGTH:
        return [line]

    return [
        prefix + text[index : index + TEXT_UART_CHUNK_LENGTH]
        for index in range(0, len(text), TEXT_UART_CHUNK_LENGTH)
    ]


def send_uart_line(ser: Any, line: str, timeout: float) -> None:
    encoded = f"{line}\n".encode("ascii")
    ack_timeout = command_ack_timeout(line, timeout)
    ser.write(encoded)
    ser.flush()
    wait_for_pico_ack(ser, ack_timeout)


def command_ack_timeout(line: str, timeout: float) -> float:
    prefix = "TEXT "
    if line.startswith(prefix):
        return max(timeout, ACK_TIMEOUT_BASE_SECONDS + len(line.removeprefix(prefix)) * TEXT_CHAR_SETTLE_SECONDS)
    return max(timeout, ACK_TIMEOUT_BASE_SECONDS)


def wait_for_pico_ack(ser: Any, ack_timeout: float) -> None:
    deadline = time.monotonic() + ack_timeout
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        if hasattr(ser, "timeout"):
            ser.timeout = min(0.5, remaining)
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("ascii", errors="ignore").strip()
        if ACK_OK in line:
            return
        if ACK_ERR in line:
            raise RuntimeError(f"Pico rejected command: {line}")

    raise TimeoutError("Pico did not acknowledge command completion")


def normalize_command(raw: str) -> str:
    command = raw.strip()
    if not command:
        raise ValueError("empty command")

    first, separator, rest = command.partition(" ")
    prefix = first.upper()
    if prefix not in COMMAND_PREFIXES:
        return f"TEXT {command}"

    if prefix == "PING":
        return "PING"

    if prefix == "TEXT":
        return f"TEXT {rest.strip()}" if separator else "TEXT"

    if prefix in {"KEY", "CLICK"}:
        return " ".join([prefix, *[word.upper() for word in rest.split()]])

    return " ".join([prefix, *rest.split()])


def normalize_key_name(value: str) -> str | None:
    raw = value.upper()
    normalized = SUPPORTED_KEY_NAMES.get(raw)
    if normalized is None and len(raw) == 1 and ("A" <= raw <= "Z" or "0" <= raw <= "9"):
        normalized = raw
    return normalized


def normalize_keypress(keys: list[Any]) -> str | None:
    normalized_keys = []
    for key in keys:
        normalized = normalize_key_name(str(key))
        if normalized is None:
            print(f"skip: unsupported keypress key={key!r}")
            continue
        normalized_keys.append(normalized)

    if not normalized_keys:
        return None

    return "KEY " + "+".join(normalized_keys)


def validate_command(line: str) -> None:
    if "\n" in line or "\r" in line:
        raise ValueError("command must be one line")

    try:
        encoded = f"{line}\n".encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("command must be ASCII") from exc

    if len(encoded) > MAX_LINE_LENGTH:
        raise ValueError(f"command is too long: max {MAX_LINE_LENGTH - 1} ASCII bytes")

    prefix, _, body = line.partition(" ")
    if prefix == "PING":
        if body:
            raise ValueError("PING does not take arguments")
        return

    if prefix == "TEXT":
        if not body:
            raise ValueError("TEXT body is empty")
        if len(body) > TEXT_MAX_LENGTH:
            raise ValueError(f"TEXT body is too long: max {TEXT_MAX_LENGTH} characters")
        if any(ord(char) < 32 or ord(char) > 126 for char in body):
            raise ValueError("TEXT body must use printable ASCII")
        return

    if prefix == "KEY":
        validate_key_command(body)
        return

    words = body.split()
    if prefix == "CLICK":
        if words not in (["LEFT"], ["RIGHT"]):
            raise ValueError("CLICK supports LEFT or RIGHT")
        return

    if prefix == "MOUSE_MOVE":
        if len(words) != 2:
            raise ValueError("MOUSE_MOVE requires x and y")
        try:
            x, y = (int(words[0]), int(words[1]))
        except ValueError as exc:
            raise ValueError("MOUSE_MOVE values must be integers") from exc
        if not (-100 <= x <= 100 and -100 <= y <= 100):
            raise ValueError("MOUSE_MOVE values must be between -100 and 100")
        return

    raise ValueError(f"unsupported command: {prefix}")


def validate_key_command(body: str) -> None:
    if not body:
        raise ValueError("KEY body is empty")

    tokens = body.split("+")
    have_non_modifier = False
    for token in tokens:
        normalized = normalize_key_name(token)
        if normalized is None:
            raise ValueError(f"unsupported KEY token: {token}")
        if normalized in MODIFIER_KEYS:
            continue
        if have_non_modifier:
            raise ValueError("KEY supports one non-modifier key")
        have_non_modifier = True

    if not have_non_modifier:
        normalized_tokens = [normalize_key_name(token) for token in tokens]
        if normalized_tokens == ["WIN"]:
            return
        raise ValueError("KEY requires a non-modifier key")
