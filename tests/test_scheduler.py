from __future__ import annotations

from app.config import OutputConfig
from hardware.gpio import SimulatedGPIO
from hardware.valves import ValveController
from scheduler.ejector import EjectorScheduler


def test_ejector_scheduler_pulses_without_sleep() -> None:
    gpio = SimulatedGPIO()
    valves = ValveController(
        gpio,
        {"reject": OutputConfig(gpio=10, distance_mm=100, pulse_ms=50)},
    )
    scheduler = EjectorScheduler(valves)

    scheduler.schedule_ejection("reject", fire_at=10.0, pulse_s=0.05)

    assert scheduler.tick(9.99) == 0
    assert gpio.states[10] is False

    assert scheduler.tick(10.0) == 1
    assert gpio.states[10] is True

    assert scheduler.tick(10.05) == 1
    assert gpio.states[10] is False
