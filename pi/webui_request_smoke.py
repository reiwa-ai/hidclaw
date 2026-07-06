#!/usr/bin/env python3
"""Compatibility entrypoint for the WebUI request smoke test."""

from __future__ import annotations

import sys

from tools.webui_request_smoke import *  # noqa: F401,F403
from tools.webui_request_smoke import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
