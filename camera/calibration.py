from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraCalibration:
    exposure: float | None = None
    white_balance: float | None = None
    focus: float | None = None


DEFAULT_CALIBRATION = CameraCalibration()
