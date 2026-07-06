from __future__ import annotations

import time

import numpy as np

from pico_hid_bridge import capture as capture_module
from pico_hid_bridge.capture import CaptureService


class FakeVideoCapture:
    instances: list["FakeVideoCapture"] = []

    def __init__(self, device: str, backend: int) -> None:
        self.device = device
        self.backend = backend
        self.released = False
        self.read_count = 0
        FakeVideoCapture.instances.append(self)

    def isOpened(self) -> bool:
        return True

    def set(self, prop: int, value: float) -> None:
        return None

    def read(self):
        self.read_count += 1
        value = min(255, 32 + self.read_count)
        frame = np.full((4, 6, 3), value, dtype=np.uint8)
        return True, frame

    def release(self) -> None:
        self.released = True


def test_capture_service_keeps_device_open_and_serves_latest_frame(monkeypatch) -> None:
    FakeVideoCapture.instances = []
    monkeypatch.setattr(capture_module.cv2, "VideoCapture", FakeVideoCapture)

    service = CaptureService(
        device="/dev/video0",
        width=0,
        height=0,
        fps=0,
        warmup_frames=0,
        min_brightness=1.0,
        ready_timeout=1.0,
        poll_interval=0.01,
    )
    service.start()
    try:
        assert service.wait_until_ready(1.0)
        first = service.latest_frame()
        time.sleep(0.05)
        second = service.latest_frame()
    finally:
        service.stop()

    assert len(FakeVideoCapture.instances) == 1
    assert FakeVideoCapture.instances[0].read_count >= 2
    assert FakeVideoCapture.instances[0].released is True
    assert second.mean() >= first.mean()
