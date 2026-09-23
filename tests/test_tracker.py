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


def test_tracker_keeps_id_for_fast_motion_when_boxes_still_overlap() -> None:
    tracker = CentroidTracker(max_distance_px=60)
    original = tracker.update([Detection(100, 100, 10_000, (50, 50, 100, 100))])[0]

    moved = tracker.update([Detection(180, 100, 10_000, (130, 50, 100, 100))])[0]

    assert moved.id == original.id


def test_tracker_uses_motion_prediction_after_missing_frame() -> None:
    tracker = CentroidTracker(max_distance_px=50, max_missed_frames=2)
    original = tracker.update([Detection(100, 100, 2_500, (75, 75, 50, 50))])[0]
    tracker.update([Detection(145, 100, 2_500, (120, 75, 50, 50))])
    tracker.update([])

    recovered = tracker.update([Detection(235, 100, 2_500, (210, 75, 50, 50))])

    assert recovered[0].id == original.id
