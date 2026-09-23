from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vision.roi import RoiBounds, crop_to_roi, resolve_roi


@dataclass(frozen=True)
class PresenceResult:
    present: bool
    foreground_ratio: float
    largest_region_ratio: float
    mask: Any
    roi: tuple[int, int, int, int]


class BackgroundPresenceDetector:
    """Detects an object by comparing the inspection area with an empty background."""

    def __init__(
        self,
        threshold: int = 28,
        min_foreground_ratio: float = 0.025,
        roi: Any | None = None,
    ) -> None:
        self.threshold = threshold
        self.min_foreground_ratio = min_foreground_ratio
        self.roi = roi
        self._background: Any | None = None
        self._calibrated_roi: RoiBounds | None = None

    @property
    def calibrated(self) -> bool:
        return self._background is not None

    def calibrate(self, frame: Any) -> None:
        cv2 = self._import_cv2()
        bounds = resolve_roi(frame, self.roi, legacy_fallback=self.roi is None)
        gray = crop_to_roi(self._gray(frame), bounds)
        self._background = cv2.GaussianBlur(gray, (9, 9), 0)
        self._calibrated_roi = bounds

    def analyze(self, frame: Any) -> PresenceResult:
        cv2 = self._import_cv2()
        height, width = frame.shape[:2]
        empty_mask = self._empty_mask(height, width)
        bounds = resolve_roi(frame, self.roi, legacy_fallback=self.roi is None)
        if self._background is None:
            return PresenceResult(False, 0.0, 0.0, empty_mask, bounds.bounding_box)

        if bounds != self._calibrated_roi:
            raise ValueError("ROI ou resolucao mudou; calibre novamente o fundo")

        gray = cv2.GaussianBlur(crop_to_roi(self._gray(frame), bounds), (9, 9), 0)
        difference = cv2.absdiff(self._background, gray)
        _value, roi_mask = cv2.threshold(difference, self.threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel)
        roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel)

        contours, _hierarchy = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_area = max(1, roi_mask.shape[0] * roi_mask.shape[1])
        foreground_ratio = float(cv2.countNonZero(roi_mask) / roi_area)
        largest_ratio = max((cv2.contourArea(item) / roi_area for item in contours), default=0.0)
        full_mask = empty_mask
        full_mask[bounds.y : bounds.y2, bounds.x : bounds.x2] = roi_mask
        present = largest_ratio >= self.min_foreground_ratio
        return PresenceResult(
            present,
            foreground_ratio,
            largest_ratio,
            full_mask,
            bounds.bounding_box,
        )

    @staticmethod
    def _empty_mask(height: int, width: int) -> Any:
        import numpy as np

        return np.zeros((height, width), dtype=np.uint8)

    @staticmethod
    def _gray(frame: Any) -> Any:
        cv2 = BackgroundPresenceDetector._import_cv2()
        if len(frame.shape) == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _import_cv2() -> Any:
        import cv2

        return cv2
