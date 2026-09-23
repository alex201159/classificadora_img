from __future__ import annotations

from app.config import OutputConfig
from hardware.gpio import SimulatedGPIO
from hardware.valves import ValveController
from scheduler.ejector import EjectorScheduler


class RecordingValves:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def on(self, output_name: str) -> None:
        self.events.append(("on", output_name))

    def off(self, output_name: str) -> None:
        self.events.append(("off", output_name))

    def all_off(self) -> None:
        pass


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


def test_overlapping_pulses_do_not_turn_output_off_early() -> None:
    gpio = SimulatedGPIO()
    valves = ValveController(
        gpio,
        {"reject": OutputConfig(gpio=10, distance_mm=100, pulse_ms=100)},
    )
    scheduler = EjectorScheduler(valves)
    scheduler.schedule_ejection("reject", fire_at=10.0, pulse_s=0.10)
    scheduler.schedule_ejection("reject", fire_at=10.05, pulse_s=0.10)

    scheduler.tick(10.0)
    scheduler.tick(10.05)
    scheduler.tick(10.10)
    assert gpio.states[10] is True

    scheduler.tick(10.15)
    assert gpio.states[10] is False


def test_touching_pulses_keep_output_on_at_shared_boundary() -> None:
    gpio = SimulatedGPIO()
    valves = ValveController(
        gpio,
        {"reject": OutputConfig(gpio=10, distance_mm=100, pulse_ms=100)},
    )
    scheduler = EjectorScheduler(valves)
    scheduler.schedule_ejection("reject", fire_at=10.0, pulse_s=0.10)
    scheduler.schedule_ejection("reject", fire_at=10.10, pulse_s=0.10)

    scheduler.tick(10.0)
    scheduler.tick(10.10)
    assert gpio.states[10] is True

    scheduler.tick(10.20)
    assert gpio.states[10] is False


def test_scheduler_processes_events_in_time_order() -> None:
    valves = RecordingValves()
    scheduler = EjectorScheduler(valves)  # type: ignore[arg-type]
    scheduler.schedule_ejection("later", fire_at=20.0, pulse_s=1.0)
    scheduler.schedule_ejection("first", fire_at=10.0, pulse_s=1.0)

    scheduler.tick(30.0)

    assert valves.events == [
        ("on", "first"),
        ("off", "first"),
        ("on", "later"),
        ("off", "later"),
    ]
