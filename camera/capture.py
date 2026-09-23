from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CameraDeviceInfo:
    index: int
    available: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    error: str | None = None


class CameraDetector:
    def __init__(self, backend: int | None = None) -> None:
        self.backend = backend

    def list_available(self, max_devices: int = 5) -> list[CameraDeviceInfo]:
        return [info for index in range(max_devices) if (info := self.probe_device(index)).available]

    def probe_device(self, index: int) -> CameraDeviceInfo:
        cv2 = _import_cv2()
        if cv2 is None:
            return CameraDeviceInfo(index=index, available=False, error="OpenCV nao instalado")

        capture = self._open_capture(cv2, index)
        try:
            if not capture.isOpened():
                return CameraDeviceInfo(index=index, available=False, error="camera nao abriu")

            ok, _frame = capture.read()
            if not ok:
                return CameraDeviceInfo(index=index, available=False, error="camera abriu sem frame")

            return CameraDeviceInfo(
                index=index,
                available=True,
                width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or None,
                height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None,
                fps=float(capture.get(cv2.CAP_PROP_FPS)) or None,
            )
        finally:
            capture.release()

    def _open_capture(self, cv2: Any, index: int) -> Any:
        if self.backend is None:
            return cv2.VideoCapture(index)
        return cv2.VideoCapture(index, self.backend)


def _import_cv2() -> Any | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    return cv2
