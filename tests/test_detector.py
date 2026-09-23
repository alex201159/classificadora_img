from __future__ import annotations

import cv2
import numpy as np

from app.config import RoiConfig
from vision.detector import CapDetector


def test_detector_returns_global_coordinates_for_offset_roi() -> None:
    frame = np.full((240, 360, 3), 220, dtype=np.uint8)
    roi = RoiConfig(x=100, y=50, width=180, height=140)
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.circle(mask, (190, 120), 24, 255, -1)

    detections = CapDetector(min_area=100).detect(frame, roi, mask)

    assert len(detections) == 1
    detection = detections[0]
    assert detection.centroid_x == 190
    assert detection.centroid_y == 120
    x, y, width, height = detection.bounding_box
    assert x >= roi.x and y >= roi.y
    assert width > 0 and height > 0


def test_detector_otsu_does_not_select_uniform_bright_background() -> None:
    frame = np.full((200, 300, 3), 230, dtype=np.uint8)
    cv2.circle(frame, (150, 100), 25, (30, 30, 30), -1)

    detections = CapDetector(min_area=100).detect(frame)

    assert len(detections) == 1
    assert detections[0].area < frame.shape[0] * frame.shape[1] / 2
