#!/usr/bin/env python3
"""Compatibility entrypoint for the Computer Use controller."""

from __future__ import annotations

import sys

from pico_hid_bridge.cli.controller import *  # noqa: F401,F403
from pico_hid_bridge.cli.controller import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
