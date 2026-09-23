from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Detection:
    centroid_x: float
    centroid_y: float
    area: float
    bounding_box: tuple[int, int, int, int]


class CapDetector:
    def __init__(self, min_area: float = 150.0) -> None:
        self.min_area = min_area

    def detect(self, frame: Any) -> list[Detection]:
        cv2 = _import_cv2()
        if cv2 is None:
            raise RuntimeError("OpenCV e necessario para detectar tampas")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _threshold, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area:
                continue

            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue

            x, y, width, height = cv2.boundingRect(contour)
            detections.append(
                Detection(
                    centroid_x=float(moments["m10"] / moments["m00"]),
                    centroid_y=float(moments["m01"] / moments["m00"]),
                    area=area,
                    bounding_box=(int(x), int(y), int(width), int(height)),
                )
            )
        return detections


def _import_cv2() -> Any | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    return cv2
