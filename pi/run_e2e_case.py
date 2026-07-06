#!/usr/bin/env python3
"""Compatibility entrypoint for a single E2E case."""

from __future__ import annotations

import sys

from tools.run_e2e_case import *  # noqa: F401,F403
from tools.run_e2e_case import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
