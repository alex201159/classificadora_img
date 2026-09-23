from __future__ import annotations

import cv2
import numpy as np

from vision.presence_detector import BackgroundPresenceDetector


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
