"""HDMI capture helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
import threading
import time
from typing import Any

import cv2


DEFAULT_DEVICE = "/dev/video0"
DEFAULT_MIN_BRIGHTNESS = 5.0
DEFAULT_READY_TIMEOUT = 5.0


@dataclass
class CaptureService:
    device: str = DEFAULT_DEVICE
    width: int = 0
    height: int = 0
    fps: int = 0
    warmup_frames: int = 60
    min_brightness: float = DEFAULT_MIN_BRIGHTNESS
    ready_timeout: float = DEFAULT_READY_TIMEOUT
    jpeg_quality: int = 80
    save_width: int = 0
    poll_interval: float = 0.05
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _ready: threading.Event = field(default_factory=threading.Event, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _frame: Any = field(default=None, init=False)
    _error: str = field(default="", init=False)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def wait_until_ready(self, timeout: float | None = None) -> bool:
        return self._ready.wait(self.ready_timeout if timeout is None else timeout)

    def latest_frame(self) -> Any:
        if not self.wait_until_ready(self.ready_timeout):
            error = self._error or "capture frame is not ready"
            raise RuntimeError(error)
        with self._lock:
            if self._frame is None:
                raise RuntimeError(self._error or "capture frame is not ready")
            return self._frame.copy()

    def latest_png_base64(self) -> str:
        return base64.b64encode(encode_png(self.latest_frame())).decode("ascii")

    def latest_jpeg(self) -> tuple[bytes, dict[str, Any]]:
        return encode_jpeg(self.latest_frame(), quality=self.jpeg_quality, save_width=self.save_width)

    def _run(self) -> None:
        capture = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not capture.isOpened():
            with self._lock:
                self._error = f"failed to open capture device: {self.device}"
            return

        try:
            configure_capture(capture, self.width, self.height, self.fps)
            self._read_warmup_frames(capture)
            while not self._stop.is_set():
                ok, frame = capture.read()
                if ok and frame is not None:
                    self._store_frame(frame)
                else:
                    with self._lock:
                        self._error = "failed to read frame"
                time.sleep(max(0.0, self.poll_interval))
        finally:
            capture.release()

    def _read_warmup_frames(self, capture: Any) -> None:
        for _ in range(max(0, self.warmup_frames)):
            if self._stop.is_set():
                return
            ok, frame = capture.read()
            if ok and frame is not None:
                self._store_frame(frame)
            time.sleep(max(0.0, self.poll_interval))

    def _store_frame(self, frame: Any) -> None:
        if frame.mean() < self.min_brightness and not self._ready.is_set():
            return
        with self._lock:
            self._frame = frame.copy()
            self._error = ""
        self._ready.set()


def configure_capture(capture: Any, width: int, height: int, fps: int) -> None:
    if width > 0:
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if fps > 0:
        capture.set(cv2.CAP_PROP_FPS, fps)


def capture_service_from_config(config: dict[str, Any]) -> CaptureService:
    capture_cfg = config["capture"]
    return CaptureService(
        device=str(capture_cfg["device"]),
        width=int(capture_cfg.get("width", 0)),
        height=int(capture_cfg.get("height", 0)),
        fps=int(capture_cfg.get("fps", 0)),
        warmup_frames=int(capture_cfg.get("warmup_frames", 60)),
        min_brightness=float(capture_cfg.get("min_brightness", DEFAULT_MIN_BRIGHTNESS)),
        ready_timeout=float(capture_cfg.get("ready_timeout", DEFAULT_READY_TIMEOUT)),
        jpeg_quality=int(capture_cfg.get("jpeg_quality", 80)),
        save_width=int(capture_cfg.get("save_width", 0)),
    )


def capture_frame(
    device: str,
    width: int,
    height: int,
    fps: int,
    warmup_frames: int,
    min_brightness: float,
    ready_timeout: float,
) -> Any:
    capture = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not capture.isOpened():
        raise RuntimeError(f"failed to open capture device: {device}")

    try:
        configure_capture(capture, width, height, fps)

        frame = None
        for _ in range(max(0, warmup_frames)):
            ok, candidate = capture.read()
            if ok:
                frame = candidate
            time.sleep(0.05)

        deadline = time.monotonic() + max(0.0, ready_timeout)
        while True:
            ok, candidate = capture.read()
            if ok:
                frame = candidate
                if frame.mean() >= min_brightness:
                    break

            if time.monotonic() >= deadline:
                break

            time.sleep(0.05)

        if frame is None:
            raise RuntimeError("failed to read frame")

        return frame
    finally:
        capture.release()


def capture_frame_from_config(config: dict[str, Any]) -> Any:
    capture_cfg = config["capture"]
    return capture_frame(
        str(capture_cfg["device"]),
        int(capture_cfg.get("width", 0)),
        int(capture_cfg.get("height", 0)),
        int(capture_cfg.get("fps", 0)),
        int(capture_cfg.get("warmup_frames", 0)),
        float(capture_cfg.get("min_brightness", 0.0)),
        float(capture_cfg.get("ready_timeout", 0.0)),
    )


def encode_png(frame: Any) -> bytes:
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("failed to encode frame as PNG")
    return encoded.tobytes()


def encode_jpeg(frame: Any, *, quality: int = 80, save_width: int = 0) -> tuple[bytes, dict[str, Any]]:
    source_height, source_width = frame.shape[:2]
    if save_width > 0 and source_width > save_width:
        ratio = save_width / source_width
        frame = cv2.resize(frame, (save_width, int(source_height * ratio)))

    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("failed to encode frame")

    return encoded.tobytes(), {
        "source_width": source_width,
        "source_height": source_height,
        "brightness": float(frame.mean()),
    }


def save_png(path: Path, png: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def capture_png_base64(args: Any, output_path: Path | None = None) -> str:
    frame = capture_frame(
        args.device,
        args.width,
        args.height,
        args.fps,
        args.warmup_frames,
        args.min_brightness,
        args.ready_timeout,
    )
    png = encode_png(frame)
    if output_path is not None:
        save_png(output_path, png)
        height, width = frame.shape[:2]
        print(f"captured {output_path}: {width}x{height}, mean_brightness={frame.mean():.1f}")
    return base64.b64encode(png).decode("ascii")


def capture_jpeg_from_config(config: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    frame = capture_frame_from_config(config)
    capture_cfg = config["capture"]
    return encode_jpeg(
        frame,
        quality=int(capture_cfg.get("jpeg_quality", 80)),
        save_width=int(capture_cfg.get("save_width", 0)),
    )
