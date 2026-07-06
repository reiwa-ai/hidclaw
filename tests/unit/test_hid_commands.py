from __future__ import annotations

import pytest

from pico_hid_bridge.hid import (
    normalize_command,
    normalize_keypress,
    send_line,
    validate_command,
    wait_for_pico_ack,
)


class FakeSerial:
    reads: list[bytes] = [b"PICO_HID_OK\n"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.written: list[bytes] = []
        self.timeout = kwargs.get("timeout")
        self.initial_timeout = kwargs.get("timeout")

    def __enter__(self) -> "FakeSerial":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        if self.reads:
            return self.reads.pop(0)
        return b""


def test_normalize_plain_text_command() -> None:
    assert normalize_command("hello") == "TEXT hello"


def test_normalize_ping_command() -> None:
    command = normalize_command("PING")
    validate_command(command)
    assert command == "PING"


def test_validate_ping_rejects_arguments() -> None:
    with pytest.raises(ValueError, match="PING does not take arguments"):
        validate_command("PING now")


def test_normalize_key_win_r() -> None:
    command = normalize_command("KEY WIN+R")
    validate_command(command)
    assert command == "KEY WIN+R"


def test_normalize_keypress_allows_standalone_modifier_key() -> None:
    assert normalize_keypress(["WIN"]) == "KEY WIN"


def test_normalize_key_alt_f4() -> None:
    command = normalize_command("KEY ALT+F4")
    validate_command(command)
    assert command == "KEY ALT+F4"


def test_normalize_key_n() -> None:
    command = normalize_command("KEY n")
    validate_command(command)
    assert command == "KEY N"


def test_validate_allows_standalone_win_key() -> None:
    validate_command("KEY WIN")


def test_validate_rejects_standalone_non_win_modifier_key() -> None:
    with pytest.raises(ValueError, match="KEY requires a non-modifier key"):
        validate_command("KEY ALT")


def test_validate_allows_256_character_text() -> None:
    validate_command("TEXT " + ("A" * 256))


def test_validate_rejects_too_long_text() -> None:
    with pytest.raises(ValueError):
        validate_command("TEXT " + ("A" * 257))


def test_validate_rejects_non_ascii_text() -> None:
    with pytest.raises(ValueError, match="ASCII"):
        validate_command("TEXT café")


def test_send_line_waits_for_pico_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()

    def fake_serial(*args: object, **kwargs: object) -> FakeSerial:
        fake.timeout = kwargs.get("timeout")
        fake.initial_timeout = kwargs.get("timeout")
        return fake

    monkeypatch.setattr("pico_hid_bridge.hid.serial.Serial", fake_serial)

    send_line("TEXT " + ("A" * 20))

    assert fake.written == [b"TEXT AAAAAAAAAAAAAAAAAAAA\n"]
    assert fake.initial_timeout >= 2.0


def test_send_line_chunks_long_text_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    fake.reads = [b"PICO_HID_OK\n", b"PICO_HID_OK\n", b"PICO_HID_OK\n"]

    monkeypatch.setattr("pico_hid_bridge.hid.serial.Serial", lambda *args, **kwargs: fake)

    send_line("TEXT " + ("A" * 45))

    assert fake.written == [
        b"TEXT AAAAAAAAAAAAAAAAAAAA\n",
        b"TEXT AAAAAAAAAAAAAAAAAAAA\n",
        b"TEXT AAAAA\n",
    ]


def test_send_line_rejects_pico_error_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    fake.reads = [b"PICO_HID_ERR\n"]

    monkeypatch.setattr("pico_hid_bridge.hid.serial.Serial", lambda *args, **kwargs: fake)

    with pytest.raises(RuntimeError, match="Pico rejected command"):
        send_line("KEY ENTER")


def test_wait_for_pico_ack_times_out_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial()
    fake.reads = []
    ticks = iter([0.0, 0.05, 0.05, 0.2])

    monkeypatch.setattr("pico_hid_bridge.hid.time.monotonic", lambda: next(ticks, 0.2))

    with pytest.raises(TimeoutError, match="Pico did not acknowledge"):
        wait_for_pico_ack(fake, 0.1)

    assert fake.timeout == pytest.approx(0.05)
