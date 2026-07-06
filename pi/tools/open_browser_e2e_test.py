#!/usr/bin/env python3
"""Compatibility wrapper for the open_browser_e2e test case."""

from __future__ import annotations

import argparse
import sys

from pico_hid_bridge.e2e.cases import OPEN_BROWSER
from pico_hid_bridge.e2e.runner import add_common_args, run_case


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    return run_case(OPEN_BROWSER, parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
