from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.config import MachineConfig
from app.metrics import PipelineMetrics
from vision.detector import CapDetector, Detection
from vision.presence_detector import BackgroundPresenceDetector, PresenceResult
from vision.reference_classifier import ClassificationResult
from vision.roi import resolve_roi
from vision.tracker import ClassificationVote, CentroidTracker, TrackedCap


class Classifier(Protocol):
    def classify(self, frame: Any, mask: Any | None = None) -> ClassificationResult: ...


class ProductionController(Protocol):
    def record_classification(self, class_name: str | None) -> None: ...

    def schedule_ejection(self, output_name: str, immediate: bool = False) -> float: ...


@dataclass(frozen=True)
class PipelineResult:
    presence: PresenceResult
    detections: list[Detection]
    tracks: list[TrackedCap]
    removed_ids: list[int]
    last_classification: ClassificationResult


@dataclass
class _DecisionMemory:
    track_ids: set[int]
    centroid_x: float
    centroid_y: float
    bounding_box: tuple[int, int, int, int]
    class_id: str
    class_name: str
    confidence: float
    color_similarity: float
    last_seen: float


class ProductionPipeline:
    """Runs vision and makes each production decision exactly once per track."""

    def __init__(
        self,
        config: MachineConfig,
        controller: ProductionController,
        classifier: Classifier,
        output_for_class: Callable[[str], str | None],
        *,
        presence_detector: BackgroundPresenceDetector | None = None,
        detector: CapDetector | None = None,
        tracker: CentroidTracker | None = None,
    ) -> None:
        self.config = config
        self.controller = controller
        self.classifier = classifier
        self.output_for_class = output_for_class
        recognition = config.recognition
        self.presence_detector = presence_detector or BackgroundPresenceDetector(
            threshold=recognition.background_threshold,
            min_foreground_ratio=recognition.min_foreground_ratio,
            roi=config.camera.roi,
        )
        roi_area = config.camera.roi.width * config.camera.roi.height
        effective_min_area = max(
            recognition.min_detection_area_px,
            roi_area * recognition.min_foreground_ratio,
        )
        self.detector = detector or CapDetector(effective_min_area)
        self.tracker = tracker or CentroidTracker(
            max_distance_px=recognition.max_tracking_distance_px,
            max_missed_frames=recognition.max_missed_frames,
        )
        controller_metrics = getattr(getattr(controller, "status", None), "metrics", None)
        self.metrics = (
            controller_metrics
            if isinstance(controller_metrics, PipelineMetrics)
            else PipelineMetrics()
        )
        self._log = logging.getLogger(__name__)
        self._decision_memories: list[_DecisionMemory] = []

    def calibrate(self, frame: Any) -> None:
        self.presence_detector.calibrate(frame)
        self.tracker.reset()

    def record_capture(self, now: float | None = None) -> None:
        self.metrics.record_capture(time.monotonic() if now is None else now)

    def process(self, frame: Any, now: float | None = None) -> PipelineResult:
        observed_at = time.monotonic() if now is None else now
        processing_started = time.perf_counter()
        last_result = self._unknown("SEM OBJETO")
        try:
            presence = self.presence_detector.analyze(frame)
            if not presence.present:
                self._decision_memories.clear()
            detection_started = time.perf_counter()
            detections = (
                self.detector.detect(frame, self.config.camera.roi, presence.mask)
                if presence.present
                else []
            )
            self.metrics.detection_ms = (time.perf_counter() - detection_started) * 1000
            tracks = self.tracker.update(detections, observed_at)
            self._refresh_decision_memories(tracks, observed_at)
            self.metrics.detected_caps += len(self.tracker.new_ids)

            classification_total_ms = 0.0
            for cap in tracks:
                if cap.missed_frames or cap.counted:
                    continue
                crop, crop_mask = self.crop_detection(
                    frame,
                    cap.bounding_box,
                    presence.mask,
                )
                classification_started = time.perf_counter()
                result = self.classifier.classify(crop, crop_mask)
                classification_total_ms += (time.perf_counter() - classification_started) * 1000
                last_result = result
                self._record_vote(cap, result)
                self._confirm_if_stable(cap)

            decided = next(
                (cap for cap in reversed(tracks) if cap.class_id is not None),
                None,
            )
            if decided is not None and last_result.class_name == "SEM OBJETO":
                last_result = ClassificationResult(
                    decided.class_id,
                    decided.class_name,
                    decided.confidence,
                    0,
                    max((vote.inliers for vote in decided.classification_votes), default=0),
                    True,
                    decided.color_similarity,
                )

            self.metrics.classification_ms = classification_total_ms
            removed = self.tracker.take_removed()
            for cap in removed:
                self._finalize_unrecognized(cap)

            latency_ms = (time.perf_counter() - processing_started) * 1000
            self.metrics.record_processing(observed_at, latency_ms)
            return PipelineResult(
                presence=presence,
                detections=detections,
                tracks=tracks,
                removed_ids=[cap.id for cap in removed],
                last_classification=last_result,
            )
        except Exception:
            raise

    def reset(self) -> None:
        self.tracker.reset()
        self._decision_memories.clear()

    def _record_vote(self, cap: TrackedCap, result: ClassificationResult) -> None:
        cap.classification_attempts += 1
        if not result.accepted or result.class_id is None:
            return
        cap.classification_votes.append(
            ClassificationVote(
                class_id=result.class_id,
                class_name=result.class_name,
                confidence=result.confidence,
                inliers=result.inliers,
                color_similarity=result.color_similarity,
            )
        )

    def _confirm_if_stable(self, cap: TrackedCap) -> None:
        required_votes = self.config.recognition.stable_hits
        if len(cap.classification_votes) < required_votes or cap.hits < 2:
            return

        grouped: dict[str, list[ClassificationVote]] = {}
        for vote in cap.classification_votes:
            grouped.setdefault(vote.class_id, []).append(vote)
        class_id, votes = max(
            grouped.items(),
            key=lambda item: (
                len(item[1]),
                sum(vote.confidence for vote in item[1]),
                sum(vote.inliers for vote in item[1]),
            ),
        )
        majority = len(votes)
        if majority <= len(cap.classification_votes) / 2 and len(grouped) > 1:
            return

        cap.class_id = class_id
        cap.class_name = votes[-1].class_name
        cap.confidence = sum(vote.confidence for vote in votes) / len(votes)
        cap.color_similarity = sum(vote.color_similarity for vote in votes) / len(votes)
        cap.counted = True

        previous_decision = self._matching_decision(cap)
        if previous_decision is not None:
            previous_decision.track_ids.add(cap.id)
            previous_decision.centroid_x = cap.centroid_x
            previous_decision.centroid_y = cap.centroid_y
            previous_decision.bounding_box = cap.bounding_box
            previous_decision.last_seen = cap.last_seen
            cap.scheduled = True
            self._log.debug(
                "ID %s confirmado visualmente como continuacao da decisao anterior",
                cap.id,
            )
            return

        self._decision_memories.append(
            _DecisionMemory(
                track_ids={cap.id},
                centroid_x=cap.centroid_x,
                centroid_y=cap.centroid_y,
                bounding_box=cap.bounding_box,
                class_id=cap.class_id,
                class_name=cap.class_name,
                confidence=cap.confidence,
                color_similarity=cap.color_similarity,
                last_seen=cap.last_seen,
            )
        )
        self.controller.record_classification(cap.class_name)
        self.metrics.recognized_caps += 1

        output_name = self.output_for_class(class_id)
        if output_name is None:
            raise RuntimeError(f"classe {class_id} nao possui saida configurada")
        cap.scheduled = True
        self.controller.schedule_ejection(output_name)
        self.metrics.scheduled_ejections += 1
        self._log.info(
            "Tampa ID %s confirmada como %s e agendada em %s",
            cap.id,
            cap.class_name,
            output_name,
        )

    def _refresh_decision_memories(
        self,
        tracks: list[TrackedCap],
        observed_at: float,
    ) -> None:
        for cap in tracks:
            memory = next(
                (
                    item
                    for item in self._decision_memories
                    if cap.id in item.track_ids
                ),
                None,
            )
            if memory is None:
                continue
            memory.centroid_x = cap.centroid_x
            memory.centroid_y = cap.centroid_y
            memory.bounding_box = cap.bounding_box
            memory.last_seen = observed_at

    def _matching_decision(self, cap: TrackedCap) -> _DecisionMemory | None:
        return next(
            (
                item
                for item in self._decision_memories
                if item.class_id == cap.class_id and self._same_physical_region(cap, item)
            ),
            None,
        )

    def _same_physical_region(self, cap: TrackedCap, memory: _DecisionMemory) -> bool:
        if _boxes_overlap(cap.bounding_box, memory.bounding_box):
            return True
        distance = (
            (cap.centroid_x - memory.centroid_x) ** 2
            + (cap.centroid_y - memory.centroid_y) ** 2
        ) ** 0.5
        return distance <= self.config.recognition.max_tracking_distance_px

    def _finalize_unrecognized(self, cap: TrackedCap) -> None:
        if cap.counted:
            return
        minimum_hits = max(2, self.config.recognition.stable_hits)
        if cap.hits < minimum_hits:
            self._log.debug(
                "Track transitorio ID %s ignorado com %s observacoes",
                cap.id,
                cap.hits,
            )
            return
        cap.counted = True
        self.metrics.unrecognized_caps += 1
        if not self.config.recognition.reject_unrecognized:
            self._log.debug("Tampa ID %s finalizada sem classificacao", cap.id)
            return
        self.controller.record_classification(None)
        self.metrics.rejected_caps += 1
        if "reject" in self.config.outputs and not cap.scheduled:
            cap.scheduled = True
            self.controller.schedule_ejection("reject")
            self.metrics.scheduled_ejections += 1
        self._log.info("Tampa ID %s finalizada sem reconhecimento", cap.id)

    def crop_detection(
        self,
        frame: Any,
        bounding_box: tuple[int, int, int, int],
        foreground_mask: Any | None = None,
    ) -> tuple[Any, Any]:
        roi = resolve_roi(frame, self.config.camera.roi)
        x, y, width, height = bounding_box
        margin = self.config.recognition.crop_margin_px
        x1 = max(roi.x, x - margin)
        y1 = max(roi.y, y - margin)
        x2 = min(roi.x2, x + width + margin)
        y2 = min(roi.y2, y + height + margin)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bounding box invalida para recorte da tampa")
        crop = frame[y1:y2, x1:x2]
        object_mask = self._bounding_box_mask(crop, x - x1, y - y1, width, height)
        if foreground_mask is not None:
            if foreground_mask.shape[:2] != frame.shape[:2]:
                raise ValueError("mascara de primeiro plano deve ter o tamanho do frame")
            foreground_crop = foreground_mask[y1:y2, x1:x2]
            import cv2

            object_mask = cv2.bitwise_and(object_mask, foreground_crop)
        return crop, object_mask

    @staticmethod
    def _bounding_box_mask(
        crop: Any,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Any:
        import numpy as np

        crop_height, crop_width = crop.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(crop_width, x + width)
        y2 = min(crop_height, y + height)
        object_mask = np.zeros((crop_height, crop_width), dtype=np.uint8)
        object_mask[y1:y2, x1:x2] = 255
        return object_mask

    @staticmethod
    def _unknown(name: str = "NAO RECONHECIDO") -> ClassificationResult:
        return ClassificationResult(None, name, 0.0, 0, 0, False)


def _boxes_overlap(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
) -> bool:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    return (
        first_x < second_x + second_width
        and first_x + first_width > second_x
        and first_y < second_y + second_height
        and first_y + first_height > second_y
    )
