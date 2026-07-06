#!/usr/bin/env python3
"""Compatibility entrypoint for the open-browser E2E probe."""

from __future__ import annotations

import sys

from tools.open_browser_e2e_test import *  # noqa: F401,F403
from tools.open_browser_e2e_test import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
