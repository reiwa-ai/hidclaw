#!/usr/bin/env python3
"""Run stage-based Computer Use + Pico HID E2E test cases."""

from __future__ import annotations

import argparse
import sys

from pico_hid_bridge.e2e.cases import ALL_CASES, CASES
from pico_hid_bridge.e2e.model import E2ETestCase


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case", dest="case_names", action="append", choices=sorted(CASES))
    parser.add_argument("--stage", dest="stages", action="append")
    parser.add_argument("--include-pending", action="store_true")
    parser.add_argument("--list", action="store_true")


def parse_args(argv: list[str]) -> argparse.Namespace:
    base_parser = argparse.ArgumentParser(add_help=False)
    add_selection_args(base_parser)
    base_args, _ = base_parser.parse_known_args(argv)
    selected = selected_cases(base_args)
    needs_runner_args = not base_args.list and (
        base_args.include_pending or any(case.implemented for case in selected)
    )

    parser = argparse.ArgumentParser(description=__doc__)
    add_selection_args(parser)
    if needs_runner_args:
        from pico_hid_bridge.e2e.runner import add_common_args

        add_common_args(parser)
    return parser.parse_args(argv)


def selected_cases(args: argparse.Namespace) -> list[E2ETestCase]:
    if args.case_names:
        selected = []
        seen: set[str] = set()
        for name in args.case_names:
            case = CASES[name]
            if case.name not in seen:
                selected.append(case)
                seen.add(case.name)
    else:
        selected = list(ALL_CASES)

    if args.stages:
        wanted = set(args.stages)
        selected = [case for case in selected if case.stage in wanted]

    return selected


def print_cases(cases: list[E2ETestCase]) -> None:
    for case in cases:
        status = "implemented" if case.implemented else "pending"
        print(f"{case.stage:28} {case.name:36} {status}")
        print(f"  {case.description}")
        if case.pending_reason:
            print(f"  pending: {case.pending_reason}")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    cases = selected_cases(args)

    if args.list:
        print_cases(cases)
        return 0

    selected_for_run = []
    for case in cases:
        if case.implemented or args.include_pending:
            selected_for_run.append(case)
        else:
            print(f"SKIP PENDING: {case.name} ({case.pending_reason})")

    if not selected_for_run:
        print("No runnable E2E cases selected.")
        return 0

    result = 0
    run_case = None
    for case in selected_for_run:
        if not case.implemented:
            print(f"RESULT PENDING: {case.name} ({case.pending_reason})")
            case_result = 2
        else:
            if run_case is None:
                from pico_hid_bridge.e2e.runner import run_case as loaded_run_case

                run_case = loaded_run_case
            case_result = run_case(case, args)
        if case_result != 0 and result == 0:
            result = case_result

    return result


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
