from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HsvRange:
    hue_min: int
    hue_max: int
    saturation_min: int
    value_min: int


class ColorClassifier:
    def __init__(self, ranges: dict[str, HsvRange] | None = None) -> None:
        self.ranges = ranges or {
            "red": HsvRange(0, 12, 80, 60),
            "green": HsvRange(35, 85, 60, 50),
            "blue": HsvRange(90, 130, 60, 50),
        }

    def classify_hsv(self, hue: float, saturation: float, value: float) -> str:
        for name, hsv_range in self.ranges.items():
            if (
                hsv_range.hue_min <= hue <= hsv_range.hue_max
                and saturation >= hsv_range.saturation_min
                and value >= hsv_range.value_min
            ):
                return name
        return "unknown"
