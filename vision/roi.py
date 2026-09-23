from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class RoiError(ValueError):
    """Raised when an ROI cannot be applied safely to a frame."""


@dataclass(frozen=True)
class RoiBounds:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def bounding_box(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height


def resolve_roi(
    frame: Any,
    roi: Any | None,
    *,
    legacy_fallback: bool = False,
) -> RoiBounds:
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 2:
        raise RoiError("frame invalido para aplicar ROI")
    frame_height, frame_width = frame.shape[:2]
    if frame_width <= 0 or frame_height <= 0:
        raise RoiError("frame vazio para aplicar ROI")

    if roi is None:
        if legacy_fallback:
            x1 = int(frame_width * 0.12)
            y1 = int(frame_height * 0.12)
            x2 = int(frame_width * 0.88)
            y2 = int(frame_height * 0.88)
            bounds = RoiBounds(x1, y1, x2 - x1, y2 - y1)
        else:
            bounds = RoiBounds(0, 0, frame_width, frame_height)
    elif isinstance(roi, (tuple, list)) and len(roi) == 4:
        bounds = RoiBounds(*(int(value) for value in roi))
    else:
        try:
            bounds = RoiBounds(
                int(roi.x),
                int(roi.y),
                int(roi.width),
                int(roi.height),
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise RoiError("ROI deve informar x, y, width e height") from exc

    if bounds.x < 0 or bounds.y < 0:
        raise RoiError("ROI nao pode ter x ou y negativos")
    if bounds.width <= 0 or bounds.height <= 0:
        raise RoiError("largura e altura da ROI devem ser maiores que zero")
    if bounds.x >= frame_width or bounds.y >= frame_height:
        raise RoiError("ROI esta fora do frame")
    if bounds.x2 > frame_width or bounds.y2 > frame_height:
        raise RoiError("ROI ultrapassa os limites do frame")
    return bounds


def crop_to_roi(frame: Any, bounds: RoiBounds) -> Any:
    return frame[bounds.y : bounds.y2, bounds.x : bounds.x2]
