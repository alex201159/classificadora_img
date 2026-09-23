from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SensorState:
    name: str
    active: bool = False


class SimulatedSensorInput:
    def __init__(self) -> None:
        self._states: dict[str, SensorState] = {}

    def set_state(self, name: str, active: bool) -> None:
        self._states[name] = SensorState(name=name, active=active)

    def read(self, name: str) -> SensorState:
        return self._states.get(name, SensorState(name=name, active=False))
