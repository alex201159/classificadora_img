from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from app.config import load_config
from app.controller import MachineController
from app.production_pipeline import ProductionPipeline
from vision.detector import Detection
from vision.presence_detector import PresenceResult
from vision.reference_classifier import ClassificationResult


class FakePresenceDetector:
    def __init__(self) -> None:
        self.present = True

    def calibrate(self, _frame: Any) -> None:
        pass

    def analyze(self, frame: Any) -> PresenceResult:
        mask = np.full(frame.shape[:2], 255 if self.present else 0, dtype=np.uint8)
        return PresenceResult(self.present, float(self.present), float(self.present), mask, (0, 0, 1920, 1080))


class FakeDetector:
    def __init__(self) -> None:
        self.detections = [Detection(100, 100, 900, (80, 80, 40, 40))]

    def detect(self, _frame: Any, _roi: Any, _mask: Any) -> list[Detection]:
        return list(self.detections)


class SequenceClassifier:
    def __init__(self, results: list[ClassificationResult]) -> None:
        self.results = results
        self.calls = 0

    def classify(self, _frame: Any, _mask: Any = None) -> ClassificationResult:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


def _accepted(class_id: str = "azul", name: str = "Azul") -> ClassificationResult:
    return ClassificationResult(class_id, name, 0.9, 12, 8, True)


def _unknown() -> ClassificationResult:
    return ClassificationResult(None, "NAO RECONHECIDO", 0.0, 0, 0, False)


def _pipeline(
    results: list[ClassificationResult],
    *,
    stable_hits: int | None = None,
) -> tuple[
    ProductionPipeline,
    MachineController,
    FakePresenceDetector,
    FakeDetector,
]:
    config = load_config(Path("config/machine.yaml"))
    if stable_hits is not None:
        config = replace(
            config,
            recognition=replace(config.recognition, stable_hits=stable_hits),
        )
    controller = MachineController(config)
    controller.initialize()
    controller.start()
    presence = FakePresenceDetector()
    detector = FakeDetector()
    pipeline = ProductionPipeline(
        config,
        controller,
        SequenceClassifier(results),
        lambda class_id: "red_round" if class_id == "azul" else None,
        presence_detector=presence,  # type: ignore[arg-type]
        detector=detector,  # type: ignore[arg-type]
    )
    return pipeline, controller, presence, detector


def test_pipeline_counts_and_schedules_each_track_only_once() -> None:
    pipeline, controller, _presence, _detector = _pipeline([_accepted()])
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    track_ids = []
    for index in range(6):
        result = pipeline.process(frame, now=float(index))
        track_ids.append(result.tracks[0].id)

    assert len(set(track_ids)) == 1
    assert controller.status.total_caps == 1
    assert controller.status.counters_by_class == {"Azul": 1}
    assert controller.status.scheduled_ejections == 1
    assert pipeline.metrics.recognized_caps == 1
    controller.shutdown()


def test_pipeline_uses_majority_vote_for_track() -> None:
    votes = [
        _accepted("azul", "Azul"),
        _accepted("vermelha", "Vermelha"),
        _accepted("azul", "Azul"),
    ]
    pipeline, controller, _presence, _detector = _pipeline(votes)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    for index in range(3):
        result = pipeline.process(frame, now=float(index))

    assert result.tracks[0].class_id == "azul"
    assert controller.status.counters_by_class == {"Azul": 1}
    controller.shutdown()


def test_pipeline_finalizes_unknown_track_through_reject_output() -> None:
    pipeline, controller, presence, detector = _pipeline([_unknown()])
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    pipeline.process(frame, now=0.0)
    presence.present = False
    detector.detections = []

    for index in range(1, 5):
        result = pipeline.process(frame, now=float(index))

    assert result.removed_ids == [1]
    assert controller.status.total_caps == 1
    assert controller.status.rejected_caps == 1
    assert controller.status.scheduled_ejections == 1
    assert controller.status.last_ejection_output == "reject"
    assert pipeline.metrics.rejected_caps == 1
    controller.shutdown()


def test_pipeline_tracks_and_decides_two_caps_independently() -> None:
    pipeline, controller, _presence, detector = _pipeline([_accepted()])
    detector.detections = [
        Detection(100, 100, 900, (80, 80, 40, 40)),
        Detection(220, 100, 900, (200, 80, 40, 40)),
    ]
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    for index in range(4):
        result = pipeline.process(frame, now=float(index))

    assert len({cap.id for cap in result.tracks}) == 2
    assert controller.status.total_caps == 2
    assert controller.status.scheduled_ejections == 2
    controller.shutdown()


def test_stable_hits_one_still_requires_same_track_in_two_frames() -> None:
    pipeline, controller, _presence, _detector = _pipeline(
        [_accepted()],
        stable_hits=1,
    )
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    pipeline.process(frame, now=0.0)
    assert controller.status.total_caps == 0

    pipeline.process(frame, now=1.0)
    assert controller.status.total_caps == 1
    assert controller.status.scheduled_ejections == 1
    controller.shutdown()
