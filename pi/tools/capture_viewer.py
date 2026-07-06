#!/usr/bin/env python3
"""View a USB HDMI capture device and save screenshots."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import cv2

from pico_hid_bridge.capture import DEFAULT_DEVICE
from pico_hid_bridge.paths import PI_DIR

DEFAULT_OUTPUT_DIR = PI_DIR / "captures"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--fps", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def configure_capture(capture: cv2.VideoCapture, args: argparse.Namespace) -> None:
    if args.width > 0:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height > 0:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if args.fps > 0:
        capture.set(cv2.CAP_PROP_FPS, args.fps)


def screenshot_path(output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / f"capture_{timestamp}.png"


def run_viewer(args: argparse.Namespace) -> int:
    capture = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    if not capture.isOpened():
        print(f"failed to open capture device: {args.device}", file=sys.stderr)
        return 1

    configure_capture(capture, args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    window_name = f"HDMI Capture: {args.device}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("failed to read frame", file=sys.stderr)
                return 1

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                return 0

            if key == ord("s"):
                path = screenshot_path(args.output_dir)
                if cv2.imwrite(str(path), frame):
                    print(f"saved: {path}")
                else:
                    print(f"failed to save screenshot: {path}", file=sys.stderr)
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main(argv: list[str]) -> int:
    return run_viewer(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
