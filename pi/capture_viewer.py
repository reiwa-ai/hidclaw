#!/usr/bin/env python3
"""Compatibility entrypoint for the capture viewer."""

from __future__ import annotations

import sys

from tools.capture_viewer import *  # noqa: F401,F403
from tools.capture_viewer import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
