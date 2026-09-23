from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vision.roi import crop_to_roi, resolve_roi


@dataclass(frozen=True)
class Detection:
    centroid_x: float
    centroid_y: float
    area: float
    bounding_box: tuple[int, int, int, int]


class CapDetector:
    def __init__(self, min_area: float = 150.0) -> None:
        if min_area <= 0:
            raise ValueError("min_area deve ser maior que zero")
        self.min_area = min_area

    def detect(
        self,
        frame: Any,
        roi: Any | None = None,
        foreground_mask: Any | None = None,
    ) -> list[Detection]:
        cv2 = _import_cv2()
        if cv2 is None:
            raise RuntimeError("OpenCV e necessario para detectar tampas")

        bounds = resolve_roi(frame, roi)
        roi_frame = crop_to_roi(frame, bounds)
        if foreground_mask is not None:
            if foreground_mask.shape[:2] == frame.shape[:2]:
                mask = crop_to_roi(foreground_mask, bounds).copy()
            elif foreground_mask.shape[:2] == roi_frame.shape[:2]:
                mask = foreground_mask.copy()
            else:
                raise ValueError("mascara deve ter o tamanho do frame ou da ROI")
        else:
            gray = (
                roi_frame
                if len(roi_frame.shape) == 2
                else cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
            )
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _threshold, mask = cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU,
            )
            border = _border_pixels(mask)
            if cv2.countNonZero(border) > border.size / 2:
                mask = cv2.bitwise_not(mask)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections: list[Detection] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area:
                continue

            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue

            local_x, local_y, width, height = cv2.boundingRect(contour)
            detections.append(
                Detection(
                    centroid_x=float(moments["m10"] / moments["m00"] + bounds.x),
                    centroid_y=float(moments["m01"] / moments["m00"] + bounds.y),
                    area=area,
                    bounding_box=(
                        int(local_x + bounds.x),
                        int(local_y + bounds.y),
                        int(width),
                        int(height),
                    ),
                )
            )
        return detections


def _border_pixels(mask: Any) -> Any:
    import numpy as np

    return np.concatenate((mask[0, :], mask[-1, :], mask[:, 0], mask[:, -1])).reshape(-1, 1)


def _import_cv2() -> Any | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    return cv2
