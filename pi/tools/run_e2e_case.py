#!/usr/bin/env python3
"""Run a named Computer Use + Pico HID E2E test case."""

from __future__ import annotations

import argparse
import sys

from pico_hid_bridge.e2e.cases import CASES
from pico_hid_bridge.e2e.runner import add_common_args, run_case


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=sorted(CASES))
    add_common_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return run_case(CASES[args.case], args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
