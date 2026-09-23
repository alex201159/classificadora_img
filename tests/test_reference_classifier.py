from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.cap_catalog import CapCatalog
from vision.reference_classifier import ReferenceImageClassifier


def _textured_image() -> np.ndarray:
    image = np.full((480, 720, 3), 235, dtype=np.uint8)
    random = np.random.default_rng(42)
    for _index in range(80):
        x = int(random.integers(70, 650))
        y = int(random.integers(60, 420))
        radius = int(random.integers(3, 12))
        color = tuple(int(value) for value in random.integers(20, 220, size=3))
        cv2.circle(image, (x, y), radius, color, -1)
    cv2.putText(image, "TAMPA A", (210, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 4)
    return image


def test_classifier_matches_registered_sample_after_small_translation(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    cap_class = catalog.create_class("Tampa A", "azul", "redonda", "reject")
    source = _textured_image()
    ok, encoded = cv2.imencode(".jpg", source)
    assert ok
    catalog.add_sample(cap_class["id"], encoded.tobytes(), "image/jpeg")

    classifier = ReferenceImageClassifier(
        catalog,
        min_good_matches=6,
        min_inliers=4,
        ambiguity_ratio=1.05,
    )
    transform = np.float32([[1, 0, 8], [0, 1, 5]])
    shifted = cv2.warpAffine(source, transform, (source.shape[1], source.shape[0]))
    result = classifier.classify(shifted)

    assert result.accepted is True
    assert result.class_name == "Tampa A"
    assert result.inliers >= 4


def test_classifier_rejects_frame_without_features(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    cap_class = catalog.create_class("Tampa A", "azul", "redonda", "reject")
    ok, encoded = cv2.imencode(".jpg", _textured_image())
    assert ok
    catalog.add_sample(cap_class["id"], encoded.tobytes(), "image/jpeg")
    classifier = ReferenceImageClassifier(catalog)

    result = classifier.classify(np.full((480, 720, 3), 128, dtype=np.uint8))

    assert result.accepted is False
    assert result.class_id is None


def _same_shape_with_color(color: tuple[int, int, int]) -> np.ndarray:
    image = np.full((420, 420, 3), 225, dtype=np.uint8)
    cv2.circle(image, (210, 210), 145, color, -1)
    random = np.random.default_rng(7)
    for _index in range(90):
        angle = float(random.uniform(0, np.pi * 2))
        radius = float(random.uniform(15, 125))
        x = int(210 + np.cos(angle) * radius)
        y = int(210 + np.sin(angle) * radius)
        cv2.circle(image, (x, y), 3, (245, 245, 245), -1)
    cv2.putText(image, "MESMA", (118, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (15, 15, 15), 3)
    return image


def test_classifier_uses_color_for_classes_with_same_shape(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    green_class = catalog.create_class("Tampa verde", "verde", "redonda", "reject")
    blue_class = catalog.create_class("Tampa azul", "azul", "redonda", "reject")
    green = _same_shape_with_color((40, 190, 70))
    blue = _same_shape_with_color((210, 80, 30))
    for cap_class, image in [(green_class, green), (blue_class, blue)]:
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        catalog.add_sample(cap_class["id"], encoded.tobytes(), "image/jpeg")

    classifier = ReferenceImageClassifier(
        catalog,
        min_good_matches=6,
        min_inliers=4,
        ambiguity_ratio=1.05,
        color_weight=0.65,
    )
    transform = np.float32([[1, 0, 5], [0, 1, 4]])
    query = cv2.warpAffine(blue, transform, (blue.shape[1], blue.shape[0]))

    result = classifier.classify(query)

    assert result.accepted is True
    assert result.class_name == "Tampa azul"
    assert result.color_similarity > 0.8
