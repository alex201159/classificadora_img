from __future__ import annotations

from vision.detector import Detection
from vision.tracker import CentroidTracker


def test_tracker_keeps_id_for_nearby_detection() -> None:
    tracker = CentroidTracker(max_distance_px=20)

    first = tracker.update([Detection(10, 10, 300, (0, 0, 20, 20))])
    second = tracker.update([Detection(15, 12, 310, (5, 2, 20, 20))])

    assert first[0].id == second[0].id
