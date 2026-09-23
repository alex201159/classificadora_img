from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass
from dataclasses import field

from vision.detector import Detection


@dataclass(frozen=True)
class ClassificationVote:
    class_id: str
    class_name: str
    confidence: float
    inliers: int
    color_similarity: float = 0.0


@dataclass
class TrackedCap:
    id: int
    centroid_x: float
    centroid_y: float
    bounding_box: tuple[int, int, int, int]
    area: float
    class_id: str | None = None
    class_name: str = "NAO RECONHECIDO"
    confidence: float = 0.0
    color_similarity: float = 0.0
    hits: int = 1
    missed_frames: int = 0
    classification_attempts: int = 0
    classification_votes: list[ClassificationVote] = field(default_factory=list)
    counted: bool = False
    scheduled: bool = False
    finalized: bool = False
    last_seen: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0


class CentroidTracker:
    def __init__(self, max_distance_px: float = 60.0, max_missed_frames: int = 3) -> None:
        if max_distance_px <= 0:
            raise ValueError("max_distance_px deve ser maior que zero")
        if max_missed_frames < 0:
            raise ValueError("max_missed_frames nao pode ser negativo")
        self.max_distance_px = max_distance_px
        self.max_missed_frames = max_missed_frames
        self._ids = itertools.count(1)
        self._tracked: dict[int, TrackedCap] = {}
        self._removed: list[TrackedCap] = []
        self._new_ids: list[int] = []

    @property
    def active(self) -> list[TrackedCap]:
        return [self._tracked[cap_id] for cap_id in sorted(self._tracked)]

    @property
    def removed_ids(self) -> list[int]:
        return [cap.id for cap in self._removed]

    @property
    def new_ids(self) -> list[int]:
        return list(self._new_ids)

    def take_removed(self) -> list[TrackedCap]:
        removed = self._removed
        self._removed = []
        return removed

    def update(self, detections: list[Detection], now: float | None = None) -> list[TrackedCap]:
        observed_at = time.monotonic() if now is None else now
        self._removed = []
        self._new_ids = []
        matched_ids: set[int] = set()
        matched_detections: set[int] = set()

        candidates: list[tuple[float, int, int]] = []
        for cap_id, cap in self._tracked.items():
            for detection_index, detection in enumerate(detections):
                prediction_steps = cap.missed_frames + 1
                predicted_x = cap.centroid_x + cap.velocity_x * prediction_steps
                predicted_y = cap.centroid_y + cap.velocity_y * prediction_steps
                predicted_distance = math.hypot(
                    predicted_x - detection.centroid_x,
                    predicted_y - detection.centroid_y,
                )
                overlaps = _intersection_area(cap.bounding_box, detection.bounding_box) > 0
                allowed_distance = self.max_distance_px * prediction_steps
                if predicted_distance <= allowed_distance or overlaps:
                    candidates.append((predicted_distance, cap_id, detection_index))

        for _distance, cap_id, detection_index in sorted(candidates):
            if cap_id in matched_ids or detection_index in matched_detections:
                continue
            cap = self._tracked[cap_id]
            detection = detections[detection_index]
            observed_velocity_x = detection.centroid_x - cap.centroid_x
            observed_velocity_y = detection.centroid_y - cap.centroid_y
            if cap.hits == 1:
                cap.velocity_x = observed_velocity_x
                cap.velocity_y = observed_velocity_y
            else:
                cap.velocity_x = cap.velocity_x * 0.5 + observed_velocity_x * 0.5
                cap.velocity_y = cap.velocity_y * 0.5 + observed_velocity_y * 0.5
            cap.centroid_x = detection.centroid_x
            cap.centroid_y = detection.centroid_y
            cap.bounding_box = detection.bounding_box
            cap.area = detection.area
            cap.hits += 1
            cap.missed_frames = 0
            cap.last_seen = observed_at
            matched_ids.add(cap_id)
            matched_detections.add(detection_index)

        for cap_id in list(self._tracked):
            if cap_id in matched_ids:
                continue
            cap = self._tracked[cap_id]
            cap.missed_frames += 1
            if cap.missed_frames > self.max_missed_frames:
                cap.finalized = True
                self._removed.append(self._tracked.pop(cap_id))

        for detection_index, detection in enumerate(detections):
            if detection_index in matched_detections:
                continue
            cap_id = next(self._ids)
            self._tracked[cap_id] = TrackedCap(
                id=cap_id,
                centroid_x=detection.centroid_x,
                centroid_y=detection.centroid_y,
                bounding_box=detection.bounding_box,
                area=detection.area,
                last_seen=observed_at,
            )
            self._new_ids.append(cap_id)

        return self.active

    def reset(self) -> None:
        self._tracked.clear()
        self._removed = []
        self._new_ids = []


def _intersection_area(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> int:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    overlap_width = max(
        0,
        min(first_x + first_width, second_x + second_width) - max(first_x, second_x),
    )
    overlap_height = max(
        0,
        min(first_y + first_height, second_y + second_height) - max(first_y, second_y),
    )
    return overlap_width * overlap_height
