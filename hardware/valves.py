from __future__ import annotations

from app.config import OutputConfig
from hardware.gpio import GpioBackend


class ValveController:
    def __init__(self, gpio: GpioBackend, outputs: dict[str, OutputConfig]) -> None:
        self.gpio = gpio
        self.outputs = outputs
        self.active_outputs: set[str] = set()
        for output in outputs.values():
            if output.gpio is not None:
                self.gpio.setup_output(output.gpio)
        self.all_off()

    def on(self, output_name: str) -> None:
        output = self._output(output_name)
        self.active_outputs.add(output_name)
        if output.gpio is not None:
            self.gpio.write(output.gpio, output.active_high)

    def off(self, output_name: str) -> None:
        output = self._output(output_name)
        self.active_outputs.discard(output_name)
        if output.gpio is not None:
            self.gpio.write(output.gpio, not output.active_high)

    def all_off(self) -> None:
        for name in self.outputs:
            self.off(name)

    def is_on(self, output_name: str) -> bool:
        self._output(output_name)
        return output_name in self.active_outputs

    def reconfigure(self, outputs: dict[str, OutputConfig]) -> None:
        self.all_off()
        self.outputs = outputs
        self.active_outputs.clear()
        for output in outputs.values():
            if output.gpio is not None:
                self.gpio.setup_output(output.gpio)
        self.all_off()

    def _output(self, output_name: str) -> OutputConfig:
        try:
            return self.outputs[output_name]
        except KeyError as exc:
            raise ValueError(f"saida desconhecida: {output_name}") from exc
