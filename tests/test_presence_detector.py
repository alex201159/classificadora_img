from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.config import RoiConfig
from vision.presence_detector import BackgroundPresenceDetector
from vision.roi import RoiError


def test_presence_requires_change_after_background_calibration() -> None:
    background = np.full((480, 720, 3), 210, dtype=np.uint8)
    detector = BackgroundPresenceDetector(threshold=20, min_foreground_ratio=0.02)
    detector.calibrate(background)

    unchanged = detector.analyze(background.copy())
    with_object = background.copy()
    cv2.rectangle(with_object, (220, 140), (500, 350), (20, 20, 20), -1)
    changed = detector.analyze(with_object)

    assert unchanged.present is False
    assert changed.present is True
    assert changed.foreground_ratio > 0.02


def test_presence_uses_explicit_offset_roi_and_returns_full_mask() -> None:
    background = np.full((200, 300, 3), 210, dtype=np.uint8)
    roi = RoiConfig(x=100, y=50, width=120, height=100)
    detector = BackgroundPresenceDetector(
        threshold=20,
        min_foreground_ratio=0.02,
        roi=roi,
    )
    detector.calibrate(background)
    changed = background.copy()
    cv2.rectangle(changed, (130, 70), (190, 130), (20, 20, 20), -1)

    result = detector.analyze(changed)

    assert result.present is True
    assert result.roi == (100, 50, 120, 100)
    assert result.mask.shape == background.shape[:2]
    assert np.count_nonzero(result.mask[:50, :]) == 0


@pytest.mark.parametrize(
    "roi",
    [
        RoiConfig(-1, 0, 20, 20),
        RoiConfig(0, -1, 20, 20),
        RoiConfig(0, 0, 0, 20),
        RoiConfig(0, 0, 20, 0),
        RoiConfig(300, 0, 20, 20),
        RoiConfig(290, 10, 20, 20),
    ],
)
def test_presence_rejects_invalid_roi(roi: RoiConfig) -> None:
    detector = BackgroundPresenceDetector(roi=roi)
    with pytest.raises(RoiError, match="ROI"):
        detector.calibrate(np.zeros((200, 300, 3), dtype=np.uint8))
