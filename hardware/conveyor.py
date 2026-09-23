from __future__ import annotations

from app.config import ConveyorConfig
from hardware.gpio import GpioBackend


class ConveyorController:
    def __init__(self, gpio: GpioBackend, config: ConveyorConfig) -> None:
        self.gpio = gpio
        self.config = config
        self.running = False
        if config.gpio is not None:
            self.gpio.setup_output(config.gpio)
        self.stop()

    def start(self) -> None:
        self.running = True
        self._write(self.config.active_high)

    def stop(self) -> None:
        self.running = False
        self._write(not self.config.active_high)

    def _write(self, value: bool) -> None:
        if self.config.gpio is not None:
            self.gpio.write(self.config.gpio, value)
