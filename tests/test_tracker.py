from __future__ import annotations

from vision.detector import Detection
from vision.tracker import CentroidTracker


def test_tracker_keeps_id_for_nearby_detection() -> None:
    tracker = CentroidTracker(max_distance_px=20)

    first = tracker.update([Detection(10, 10, 300, (0, 0, 20, 20))])
    second = tracker.update([Detection(15, 12, 310, (5, 2, 20, 20))])

    assert first[0].id == second[0].id


def test_tracker_assigns_each_id_only_once_and_ignores_detection_order() -> None:
    tracker = CentroidTracker(max_distance_px=40)
    first = tracker.update(
        [
            Detection(20, 20, 300, (10, 10, 20, 20)),
            Detection(50, 20, 300, (40, 10, 20, 20)),
        ]
    )
    ids_by_side = {"left": first[0].id, "right": first[1].id}

    second = tracker.update(
        [
            Detection(47, 22, 300, (37, 12, 20, 20)),
            Detection(24, 22, 300, (14, 12, 20, 20)),
        ]
    )

    assert len({cap.id for cap in second}) == 2
    assert min(second, key=lambda cap: cap.centroid_x).id == ids_by_side["left"]
    assert max(second, key=lambda cap: cap.centroid_x).id == ids_by_side["right"]


def test_tracker_recovers_id_after_missing_frame_and_removes_after_limit() -> None:
    tracker = CentroidTracker(max_distance_px=20, max_missed_frames=2)
    original = tracker.update([Detection(10, 10, 300, (0, 0, 20, 20))])[0]

    assert tracker.update([])[0].missed_frames == 1
    recovered = tracker.update([Detection(13, 11, 300, (3, 1, 20, 20))])[0]
    assert recovered.id == original.id

    tracker.update([])
    tracker.update([])
    assert tracker.update([]) == []
    assert tracker.removed_ids == [original.id]
