#!/usr/bin/env python3
"""Smoke test the WebUI Request endpoint through Computer Use."""

from __future__ import annotations

import argparse
import sys

from pico_hid_bridge.config import load_config
from pico_hid_bridge.web.app import create_app


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="*", default=["open", "browser"])
    parser.add_argument("--config")
    parser.add_argument("--runtime-dir", default="runtime/webui_request_smoke")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    config["app"]["runtime_dir"] = args.runtime_dir
    config["logs"]["database"] = f"{args.runtime_dir}/app.db"
    config["logs"]["screenshot_dir"] = f"{args.runtime_dir}/screenshots"

    app = create_app(config, start_capture_service=True)
    response = app.test_client().post(
        "/api/command",
        json={"command": " ".join(args.command), "planning": False},
    )
    print(f"status={response.status_code}")
    print(response.get_data(as_text=True))
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
