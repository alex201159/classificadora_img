from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineMetrics:
    capture_fps: float = 0.0
    processing_fps: float = 0.0
    detection_ms: float = 0.0
    classification_ms: float = 0.0
    average_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    detected_caps: int = 0
    recognized_caps: int = 0
    unrecognized_caps: int = 0
    rejected_caps: int = 0
    scheduled_ejections: int = 0
    failures: int = 0
    _captured_frames: int = field(default=0, repr=False)
    _processed_frames: int = field(default=0, repr=False)
    _capture_started: float | None = field(default=None, repr=False)
    _processing_started: float | None = field(default=None, repr=False)
    _total_latency_ms: float = field(default=0.0, repr=False)

    def record_capture(self, now: float) -> None:
        if self._capture_started is None:
            self._capture_started = now
        self._captured_frames += 1
        elapsed = now - self._capture_started
        if elapsed > 0:
            self.capture_fps = max(0.0, (self._captured_frames - 1) / elapsed)

    def record_processing(self, now: float, latency_ms: float) -> None:
        if self._processing_started is None:
            self._processing_started = now
        self._processed_frames += 1
        self._total_latency_ms += latency_ms
        self.average_latency_ms = self._total_latency_ms / self._processed_frames
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        elapsed = now - self._processing_started
        if elapsed > 0:
            self.processing_fps = max(0.0, (self._processed_frames - 1) / elapsed)
