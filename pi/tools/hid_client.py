#!/usr/bin/env python3
"""Send one line from Raspberry Pi 5 to Pico over UART."""

from __future__ import annotations

import argparse
import sys

import serial

from pico_hid_bridge.hid import (
    COMMAND_PREFIXES,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    MAX_LINE_LENGTH,
    send_line,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "line",
        nargs="*",
        default=["hello"],
        help='Text to type. Use "KEY ENTER", "MOUSE_MOVE 20 -10", or "CLICK LEFT" for commands.',
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    return parser.parse_args(argv)


def build_command(words: list[str]) -> str:
    if not words:
        words = ["hello"]

    if words[0] in COMMAND_PREFIXES:
        return " ".join(words)

    return f"TEXT {' '.join(words)}"


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    line = build_command(args.line)

    try:
        send_line(line, port=args.port, baudrate=args.baudrate, timeout=args.timeout)
    except (OSError, serial.SerialException, ValueError) as exc:
        print(f"send failed: {exc}", file=sys.stderr)
        return 1

    print(f"sent: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
