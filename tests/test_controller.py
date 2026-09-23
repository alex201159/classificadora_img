from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_config
from app.controller import MachineController


def test_controller_counts_by_class_and_migrates_renamed_counter() -> None:
    controller = MachineController(load_config(Path("config/machine.yaml")))
    controller.initialize()
    controller.start()
    controller.record_classification("Alex")
    controller.record_classification("Alex")

    controller.rename_class_counter("Alex", "Celular preto")

    assert controller.status.total_caps == 2
    assert controller.status.counters_by_class == {"Celular preto": 2}
    controller.shutdown()


def test_controller_starts_conveyor_and_fires_ejector_after_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = MachineController(load_config(Path("config/machine.yaml")))
    controller.initialize()
    monkeypatch.setattr("app.controller.time.monotonic", lambda: 10.0)

    controller.start()
    delay = controller.schedule_ejection("red_round")

    assert delay == pytest.approx(1.5)
    assert controller.status.conveyor_running is True
    assert controller.gpio.states[19] is True
    controller.scheduler.tick(11.49)
    assert controller.gpio.states[20] is False
    controller.scheduler.tick(11.50)
    assert controller.gpio.states[20] is True
    controller.scheduler.tick(11.59)
    assert controller.gpio.states[20] is False

    controller.stop()
    assert controller.gpio.states[19] is False
    assert controller.status.safe_state is True
    controller.shutdown()
