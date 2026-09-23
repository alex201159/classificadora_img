from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ShapeFeatures:
    area: float
    perimeter: float
    width: float
    height: float

    @property
    def circularity(self) -> float:
        if self.perimeter <= 0:
            return 0.0
        return 4 * math.pi * self.area / (self.perimeter * self.perimeter)

    @property
    def aspect_ratio(self) -> float:
        if self.height <= 0:
            return 0.0
        return self.width / self.height


class ShapeClassifier:
    def classify(self, features: ShapeFeatures) -> str:
        if features.circularity >= 0.75 and 0.8 <= features.aspect_ratio <= 1.25:
            return "round"
        return "unknown"
