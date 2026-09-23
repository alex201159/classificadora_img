from __future__ import annotations

from pathlib import Path

import pytest

from app.config import load_config
from app.controller import MachineController, MachineState


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
    assert controller.status.state == MachineState.STOPPED
    controller.shutdown()


def test_critical_failure_clears_scheduler_and_turns_all_outputs_off() -> None:
    controller = MachineController(load_config(Path("config/machine.yaml")))
    controller.initialize()
    controller.start()
    controller.schedule_ejection("red_round", immediate=True)
    controller.scheduler.tick(float("inf"))
    controller.schedule_ejection("red_round")

    controller.enter_safe_state("falha de teste")

    assert controller.status.state == MachineState.FAULT
    assert controller.status.failure_reason == "falha de teste"
    assert controller.status.running is False
    assert controller.scheduler.pending_count() == 0
    assert controller.gpio.states[19] is False
    assert controller.gpio.states[20] is False
    assert controller.status.metrics.failures == 1
    controller.shutdown()


def test_camera_failure_during_production_enters_safe_state() -> None:
    controller = MachineController(load_config(Path("config/machine.yaml")))
    controller.initialize()
    controller.start()

    controller.report_camera_failure()

    assert controller.status.state == MachineState.FAULT
    assert controller.status.running is False
    assert controller.status.camera_available is False
    assert controller.status.conveyor_running is False
    assert controller.gpio.states[19] is False
    assert controller.gpio.states[20] is False
    controller.shutdown()
