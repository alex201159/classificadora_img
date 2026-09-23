from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from app.config import MachineConfig, OutputConfig
from app.metrics import PipelineMetrics
from camera.capture import CameraDetector
from hardware.gpio import OrangePiGPIO, SimulatedGPIO
from hardware.conveyor import ConveyorController
from hardware.valves import ValveController
from scheduler.ejector import EjectorScheduler


class MachineState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAULT = "FAULT"


@dataclass
class MachineStatus:
    state: MachineState = MachineState.IDLE
    running: bool = False
    safe_state: bool = True
    camera_available: bool = False
    total_caps: int = 0
    rejected_caps: int = 0
    counters_by_class: dict[str, int] = field(default_factory=dict)
    conveyor_running: bool = False
    scheduled_ejections: int = 0
    last_ejection_output: str | None = None
    failure_reason: str | None = None
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)


class MachineController:
    def __init__(self, config: MachineConfig) -> None:
        self.config = config
        self.status = MachineStatus()
        self.gpio = SimulatedGPIO() if config.simulation else OrangePiGPIO()
        self.conveyor = ConveyorController(self.gpio, config.conveyor)
        self.valves = ValveController(self.gpio, config.outputs)
        self.scheduler = EjectorScheduler(self.valves)
        self.camera_detector = CameraDetector()
        self._log = logging.getLogger(__name__)

    def initialize(self) -> MachineStatus:
        self._log.info("Inicializando maquina '%s'", self.config.name)
        self.valves.all_off()
        self.conveyor.stop()

        if self.config.simulation:
            self._log.info("Modo simulacao habilitado; camera fisica nao e obrigatoria")
            self.status.camera_available = False
        else:
            camera = self.camera_detector.probe_device(self.config.camera.device)
            self.status.camera_available = camera.available
            if not camera.available:
                self.enter_safe_state("camera indisponivel")
                return self.status

        self.status.safe_state = True
        self.status.state = MachineState.IDLE
        self.status.failure_reason = None
        return self.status

    def start(self) -> None:
        if not self.config.simulation and not self.status.camera_available:
            self.enter_safe_state("producao bloqueada sem camera")
            return
        try:
            self.conveyor.start()
            self.status.conveyor_running = True
            self.status.running = True
            self.status.safe_state = False
            self.status.state = MachineState.RUNNING
            self.status.failure_reason = None
            self._log.info("Producao iniciada; esteira ligada")
        except Exception:
            self._log.exception("Falha ao ligar a esteira")
            self.enter_safe_state("falha ao ligar a esteira")

    def stop(self) -> None:
        self.status.running = False
        self.enter_safe_state("parada solicitada", fault=False)

    def report_camera_failure(self, reason: str = "camera indisponivel durante producao") -> None:
        self.status.camera_available = False
        if self.status.running:
            self.enter_safe_state(reason)

    def tick(self) -> None:
        now = time.monotonic()
        try:
            self.scheduler.tick(now)
        except Exception:
            self._log.exception("Falha no scheduler de expulsao")
            self.enter_safe_state("falha no scheduler de expulsao")
            raise

    def schedule_ejection(self, output_name: str, immediate: bool = False) -> float:
        if not self.status.running and not self.config.simulation:
            raise RuntimeError("expulsao bloqueada com a maquina parada")
        output = self.config.outputs.get(output_name)
        if output is None:
            raise ValueError(f"saida desconhecida: {output_name}")

        if output.delay_ms is not None:
            configured_delay_s = output.delay_ms / 1000
        else:
            compensation_s = (
                self.config.timing.processing_latency_ms + self.config.timing.valve_response_ms
            ) / 1000
            configured_delay_s = max(
                0.0,
                output.distance_mm / self.config.conveyor.speed_mm_s - compensation_s,
            )
        delay_s = 0.0 if immediate else configured_delay_s
        fire_at = time.monotonic() + delay_s
        self.scheduler.schedule_ejection(output_name, fire_at, output.pulse_ms / 1000)
        self.status.scheduled_ejections += 1
        self.status.last_ejection_output = output_name
        self._log.info("Expulsao agendada: %s em %.3f s", output_name, delay_s)
        return delay_s

    def reconfigure_outputs(self, outputs: dict[str, OutputConfig]) -> None:
        if self.status.running:
            raise RuntimeError("pare a maquina antes de alterar as saidas")
        self.scheduler.clear()
        typed_outputs = dict(outputs)
        self.valves.reconfigure(typed_outputs)
        self.config.outputs.clear()
        self.config.outputs.update(typed_outputs)

    def reconfigure_machine(self, config: MachineConfig) -> None:
        if self.status.running:
            raise RuntimeError("pare a maquina antes de alterar a configuracao")
        self.scheduler.clear()
        self.valves.reconfigure(config.outputs)
        self.conveyor.config = config.conveyor
        self.config = config

    def record_classification(self, class_name: str | None) -> None:
        if not self.status.running:
            return
        self.status.total_caps += 1
        if class_name is None:
            self.status.rejected_caps += 1
            return
        self.status.counters_by_class[class_name] = (
            self.status.counters_by_class.get(class_name, 0) + 1
        )

    def rename_class_counter(self, old_name: str, new_name: str) -> None:
        if old_name == new_name:
            return
        previous_count = self.status.counters_by_class.pop(old_name, 0)
        if previous_count:
            self.status.counters_by_class[new_name] = (
                self.status.counters_by_class.get(new_name, 0) + previous_count
            )

    def enter_safe_state(self, reason: str, *, fault: bool = True) -> None:
        self._log.warning("Entrando em estado seguro: %s", reason)
        self.status.running = False
        self.status.safe_state = True
        self.status.conveyor_running = False
        self.status.state = MachineState.FAULT if fault else MachineState.STOPPED
        self.status.failure_reason = reason if fault else None
        if fault:
            self.status.metrics.failures += 1

        try:
            self.conveyor.stop()
        except Exception:
            self._log.exception("Falha ao desligar esteira durante estado seguro")
        try:
            self.scheduler.clear()
        except Exception:
            self._log.exception("Falha ao limpar scheduler durante estado seguro")
            try:
                self.valves.all_off()
            except Exception:
                self._log.exception("Falha ao desligar valvulas durante estado seguro")

    def shutdown(self) -> None:
        self._log.info("Encerrando controlador")
        self.enter_safe_state("shutdown", fault=False)
        self.gpio.close()
