from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from vision.detector import Detection


@dataclass
class TrackedCap:
    id: int
    centroid_x: float
    centroid_y: float
    class_name: str = "unknown"


class CentroidTracker:
    def __init__(self, max_distance_px: float = 60.0) -> None:
        self.max_distance_px = max_distance_px
        self._ids = itertools.count(1)
        self._tracked: dict[int, TrackedCap] = {}

    def update(self, detections: list[Detection]) -> list[TrackedCap]:
        updated: dict[int, TrackedCap] = {}

        for detection in detections:
            match_id = self._nearest_id(detection)
            if match_id is None:
                cap_id = next(self._ids)
                updated[cap_id] = TrackedCap(cap_id, detection.centroid_x, detection.centroid_y)
            else:
                previous = self._tracked[match_id]
                updated[match_id] = TrackedCap(
                    previous.id,
                    detection.centroid_x,
                    detection.centroid_y,
                    previous.class_name,
                )

        self._tracked = updated
        return list(updated.values())

    def _nearest_id(self, detection: Detection) -> int | None:
        nearest_id: int | None = None
        nearest_distance = self.max_distance_px
        for cap_id, cap in self._tracked.items():
            distance = math.hypot(cap.centroid_x - detection.centroid_x, cap.centroid_y - detection.centroid_y)
            if distance <= nearest_distance:
                nearest_id = cap_id
                nearest_distance = distance
        return nearest_id
