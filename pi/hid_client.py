#!/usr/bin/env python3
"""Compatibility entrypoint for the manual HID client."""

from __future__ import annotations

import sys

from tools.hid_client import *  # noqa: F401,F403
from tools.hid_client import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
