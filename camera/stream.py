from __future__ import annotations

import threading
from typing import Any


class CameraStream:
    def __init__(self, device: int, width: int, height: int, fps: int) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._capture: Any | None = None
        self._lock = threading.Lock()

    @property
    def opened(self) -> bool:
        return self._capture is not None and bool(self._capture.isOpened())

    def open(self) -> bool:
        import cv2

        with self._lock:
            if self.opened:
                return True
            capture = self._create_capture(cv2, self.device, self.width, self.height, self.fps)
            if not capture.isOpened():
                capture.release()
                return False
            self.width, self.height = self._actual_dimensions(
                cv2,
                capture,
                self.width,
                self.height,
            )
            self._capture = capture
            return True

    def reconfigure(self, device: int, width: int, height: int, fps: int) -> bool:
        import cv2

        with self._lock:
            previous = (self.device, self.width, self.height, self.fps)
            if self._capture is not None:
                self._capture.release()
                self._capture = None

            capture = self._create_capture(cv2, device, width, height, fps)
            received_frame = False
            if capture.isOpened():
                for _attempt in range(3):
                    received_frame, _frame = capture.read()
                    if received_frame:
                        break
            if received_frame:
                self.device = device
                self.width, self.height = self._actual_dimensions(
                    cv2,
                    capture,
                    width,
                    height,
                    _frame,
                )
                self.fps = fps
                self._capture = capture
                return True

            capture.release()
            restored = self._create_capture(cv2, *previous)
            if restored.isOpened():
                self.device, self.width, self.height, self.fps = previous
                self._capture = restored
            else:
                restored.release()
            return False

    def read(self) -> tuple[bool, Any | None]:
        with self._lock:
            if not self.opened:
                return False, None
            return self._capture.read()

    def close(self) -> None:
        with self._lock:
            if self._capture is not None:
                self._capture.release()
                self._capture = None

    @staticmethod
    def _create_capture(cv2: Any, device: int, width: int, height: int, fps: int) -> Any:
        capture = cv2.VideoCapture(device)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)
        return capture

    @staticmethod
    def _actual_dimensions(
        cv2: Any,
        capture: Any,
        requested_width: int,
        requested_height: int,
        frame: Any | None = None,
    ) -> tuple[int, int]:
        if frame is not None and hasattr(frame, "shape") and len(frame.shape) >= 2:
            height, width = frame.shape[:2]
            if width > 0 and height > 0:
                return int(width), int(height)

        get_property = getattr(capture, "get", None)
        if callable(get_property):
            width = int(get_property(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(get_property(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if width > 0 and height > 0:
                return width, height
        return requested_width, requested_height
