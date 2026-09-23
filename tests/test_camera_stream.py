from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import numpy as np

from camera.stream import CameraStream


class FakeCapture:
    def __init__(
        self,
        device: int,
        available: bool,
        actual_size: tuple[int, int] = (1280, 720),
    ) -> None:
        self.device = device
        self.available = available
        self.actual_size = actual_size
        self.released = False
        self.settings: list[tuple[int, int]] = []

    def isOpened(self) -> bool:
        return self.available and not self.released

    def set(self, prop: int, value: int) -> None:
        self.settings.append((prop, value))

    def release(self) -> None:
        self.released = True

    def read(self) -> tuple[bool, Any | None]:
        width, height = self.actual_size
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        return self.isOpened(), frame if self.isOpened() else None


def test_camera_reconfigure_restores_previous_device_when_new_one_fails(monkeypatch: Any) -> None:
    opened: list[FakeCapture] = []

    def video_capture(device: int) -> FakeCapture:
        capture = FakeCapture(device, available=device == 0)
        opened.append(capture)
        return capture

    fake_cv2 = SimpleNamespace(
        VideoCapture=video_capture,
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_FPS=3,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    stream = CameraStream(0, 1280, 720, 30)

    assert stream.open() is True
    assert stream.reconfigure(1, 1920, 1080, 60) is False
    assert stream.device == 0
    assert stream.opened is True
    assert [capture.device for capture in opened] == [0, 1, 0]


def test_camera_reconfigure_records_dimensions_actually_delivered(monkeypatch: Any) -> None:
    def video_capture(device: int) -> FakeCapture:
        size = (1280, 720) if device == 0 else (640, 480)
        return FakeCapture(device, available=True, actual_size=size)

    fake_cv2 = SimpleNamespace(
        VideoCapture=video_capture,
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_FPS=3,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    stream = CameraStream(0, 1280, 720, 30)
    assert stream.open() is True

    assert stream.reconfigure(1, 1920, 1080, 30) is True
    assert (stream.width, stream.height) == (640, 480)
