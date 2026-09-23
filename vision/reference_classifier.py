from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.cap_catalog import CapCatalog


@dataclass(frozen=True)
class ClassificationResult:
    class_id: str | None
    class_name: str
    confidence: float
    good_matches: int
    inliers: int
    accepted: bool
    color_similarity: float = 0.0


@dataclass(frozen=True)
class _Reference:
    class_id: str
    class_name: str
    path: Path
    keypoints: Any
    descriptors: Any
    color_histogram: Any
    matcher: Any


class ReferenceImageClassifier:
    """Matches live frames against registered samples using local image features."""

    def __init__(
        self,
        catalog: CapCatalog,
        ratio_threshold: float = 0.72,
        min_good_matches: int = 8,
        min_inliers: int = 5,
        ambiguity_ratio: float = 1.12,
        max_image_width: int = 640,
        sift_features: int = 900,
        flann_checks: int = 16,
        color_weight: float = 0.55,
    ) -> None:
        self.catalog = catalog
        self.ratio_threshold = ratio_threshold
        self.min_good_matches = min_good_matches
        self.min_inliers = min_inliers
        self.ambiguity_ratio = ambiguity_ratio
        self.max_image_width = max_image_width
        self.sift_features = sift_features
        self.flann_checks = flann_checks
        if not 0 < color_weight < 1:
            raise ValueError("color_weight deve estar entre zero e um")
        self.color_weight = color_weight
        self._references: list[_Reference] = []
        self._log = logging.getLogger(__name__)
        self._cv2 = self._import_cv2()
        self._detector = self._cv2.SIFT_create(nfeatures=sift_features)
        self.reload()

    @property
    def reference_count(self) -> int:
        return len(self._references)

    def reload(self) -> int:
        references: list[_Reference] = []
        for cap_class in self.catalog.list_classes():
            for sample in cap_class.get("samples", []):
                path = self.catalog.media_path(cap_class["id"], sample["filename"])
                if path is None:
                    continue
                image = self._cv2.imread(str(path), self._cv2.IMREAD_COLOR)
                if image is None:
                    self._log.warning("Amostra ilegivel ignorada: %s", path)
                    continue
                gray = self._to_gray(image)
                keypoints, descriptors = self._extract_features(gray)
                if descriptors is None or len(keypoints) < 80:
                    self._log.warning("Amostra sem detalhes suficientes ignorada: %s", path)
                    continue
                references.append(
                    _Reference(
                        class_id=cap_class["id"],
                        class_name=cap_class["name"],
                        path=path,
                        keypoints=keypoints,
                        descriptors=descriptors,
                        color_histogram=self._color_histogram(image),
                        matcher=self._build_matcher(descriptors),
                    )
                )
        self._references = references
        self._log.info("Classificador carregado com %d amostras", len(references))
        return len(references)

    def classify(self, frame: Any, mask: Any | None = None) -> ClassificationResult:
        if frame is None or not self._references:
            return self._unknown()

        query_color = self._color_histogram(frame, mask)
        gray = self._to_gray(frame)
        query_keypoints, query_descriptors = self._extract_features(gray, mask)
        if query_descriptors is None or len(query_keypoints) < 40:
            return self._unknown()

        best_by_class: dict[str, tuple[str, int, int, float, float]] = {}
        scores = self._score_references(query_keypoints, query_descriptors)
        for reference, (good_matches, inliers) in zip(self._references, scores, strict=True):
            geometric_quality = min(1.0, inliers / max(self.min_inliers * 3, 1))
            match_quality = min(1.0, good_matches / max(self.min_good_matches * 3, 1))
            visual_score = geometric_quality * 0.75 + match_quality * 0.25
            color_similarity = self._histogram_similarity(
                query_color,
                reference.color_histogram,
            )
            score = (
                visual_score * (1.0 - self.color_weight)
                + color_similarity * self.color_weight
            )
            current = best_by_class.get(reference.class_id)
            if current is None or score > current[3]:
                best_by_class[reference.class_id] = (
                    reference.class_name,
                    good_matches,
                    inliers,
                    score,
                    color_similarity,
                )

        ranked = sorted(best_by_class.items(), key=lambda item: item[1][3], reverse=True)
        if not ranked:
            return self._unknown()

        class_id, (class_name, good_matches, inliers, best_score, color_similarity) = ranked[0]
        second_score = ranked[1][1][3] if len(ranked) > 1 else 0.0
        score_ratio = best_score / max(second_score, 0.01)
        accepted = (
            good_matches >= self.min_good_matches
            and inliers >= self.min_inliers
            and score_ratio >= self.ambiguity_ratio
        )

        margin = min(1.0, max(0.0, score_ratio - 1.0) / 1.5)
        confidence = min(0.99, best_score * 0.82 + margin * 0.18)
        if not accepted:
            return ClassificationResult(
                class_id=None,
                class_name="NAO RECONHECIDO",
                confidence=confidence,
                good_matches=good_matches,
                inliers=inliers,
                accepted=False,
                color_similarity=color_similarity,
            )
        return ClassificationResult(
            class_id=class_id,
            class_name=class_name,
            confidence=confidence,
            good_matches=good_matches,
            inliers=inliers,
            accepted=True,
            color_similarity=color_similarity,
        )

    def _score_references(
        self,
        query_keypoints: Any,
        query_descriptors: Any,
    ) -> list[tuple[int, int]]:
        scores: list[tuple[int, int]] = []
        for reference in self._references:
            try:
                pairs = reference.matcher.knnMatch(query_descriptors, k=2)
            except self._cv2.error:
                scores.append((0, 0))
                continue
            good = []
            for pair in pairs:
                if len(pair) < 2:
                    continue
                match, neighbor = pair
                if match.distance < self.ratio_threshold * neighbor.distance:
                    good.append(match)
            scores.append(self._geometric_score(query_keypoints, reference, good))
        return scores

    def _geometric_score(
        self,
        query_keypoints: Any,
        reference: _Reference,
        good: list[Any],
    ) -> tuple[int, int]:

        if len(good) < 4:
            return len(good), 0

        import numpy as np

        query_points = np.float32([query_keypoints[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
        reference_points = np.float32(
            [reference.keypoints[item.trainIdx].pt for item in good]
        ).reshape(-1, 1, 2)
        _matrix, mask = self._cv2.findHomography(
            query_points,
            reference_points,
            self._cv2.RANSAC,
            5.0,
        )
        inliers = int(mask.sum()) if mask is not None else 0
        return len(good), inliers

    def _build_matcher(self, descriptors: Any) -> Any:
        matcher = self._cv2.FlannBasedMatcher(
            {"algorithm": 1, "trees": 4},
            {"checks": self.flann_checks},
        )
        matcher.add([descriptors])
        matcher.train()
        return matcher

    def _color_histogram(self, frame: Any, mask: Any | None = None) -> Any:
        import numpy as np

        if len(frame.shape) == 2:
            color = self._cv2.cvtColor(frame, self._cv2.COLOR_GRAY2BGR)
        else:
            color = frame
        hsv = self._cv2.cvtColor(color, self._cv2.COLOR_BGR2HSV)
        valid = np.ones(hsv.shape[:2], dtype=bool)
        if mask is not None:
            if mask.shape[:2] != hsv.shape[:2]:
                raise ValueError("mascara de cor deve ter o mesmo tamanho da imagem")
            valid = mask > 0
        pixels = hsv[valid]
        if not len(pixels):
            return np.zeros(68, dtype=np.float32)

        saturation = pixels[:, 1].astype(np.float32)
        cutoff = float(np.percentile(saturation, 55))
        colorful = pixels[saturation >= cutoff]
        colorful_saturation = colorful[:, 1].astype(np.float32) + 1.0
        hue_hist, _edges = np.histogram(
            colorful[:, 0],
            bins=36,
            range=(0, 180),
            weights=colorful_saturation,
        )
        saturation_hist, _edges = np.histogram(pixels[:, 1], bins=16, range=(0, 256))
        value_hist, _edges = np.histogram(pixels[:, 2], bins=16, range=(0, 256))
        descriptor = np.concatenate(
            (
                self._normalize_histogram(hue_hist) * 0.70,
                self._normalize_histogram(saturation_hist) * 0.15,
                self._normalize_histogram(value_hist) * 0.15,
            )
        ).astype(np.float32)
        return descriptor

    @staticmethod
    def _normalize_histogram(histogram: Any) -> Any:
        import numpy as np

        values = np.asarray(histogram, dtype=np.float32)
        total = float(values.sum())
        return values / total if total > 0 else np.zeros_like(values)

    @staticmethod
    def _histogram_similarity(first: Any, second: Any) -> float:
        import numpy as np

        return float(np.minimum(first, second).sum())

    def _extract_features(self, gray: Any, mask: Any | None = None) -> tuple[Any, Any]:
        gray, mask = self._resize(gray, mask)
        normalized = self._cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        return self._detector.detectAndCompute(normalized, mask)

    def _resize(self, gray: Any, mask: Any | None = None) -> tuple[Any, Any | None]:
        height, width = gray.shape[:2]
        if width <= self.max_image_width:
            return gray, mask
        scale = self.max_image_width / width
        dimensions = (self.max_image_width, max(1, int(height * scale)))
        resized_gray = self._cv2.resize(gray, dimensions)
        resized_mask = (
            self._cv2.resize(mask, dimensions, interpolation=self._cv2.INTER_NEAREST)
            if mask is not None
            else None
        )
        return resized_gray, resized_mask

    def _to_gray(self, frame: Any) -> Any:
        if len(frame.shape) == 2:
            return frame
        return self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _unknown() -> ClassificationResult:
        return ClassificationResult(None, "NAO RECONHECIDO", 0.0, 0, 0, False)

    @staticmethod
    def _import_cv2() -> Any:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV e necessario para o reconhecimento") from exc
        return cv2
