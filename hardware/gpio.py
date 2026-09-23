from __future__ import annotations

import logging
from typing import Protocol


class GpioBackend(Protocol):
    def setup_output(self, pin: int) -> None: ...

    def write(self, pin: int, value: bool) -> None: ...

    def close(self) -> None: ...


class SimulatedGPIO:
    def __init__(self) -> None:
        self.states: dict[int, bool] = {}
        self._log = logging.getLogger(__name__)

    def setup_output(self, pin: int) -> None:
        self.states.setdefault(pin, False)
        self._log.debug("GPIO simulado configurado como saida: %s", pin)

    def write(self, pin: int, value: bool) -> None:
        self.states[pin] = value
        self._log.info("GPIO simulado %s -> %s", pin, "ON" if value else "OFF")

    def close(self) -> None:
        for pin in list(self.states):
            self.states[pin] = False
        self._log.debug("GPIO simulado encerrado")


class OrangePiGPIO:
    """Orange Pi backend using wiringOP's wPi numbering."""

    def __init__(self, wiringpi_module: object | None = None) -> None:
        if wiringpi_module is None:
            try:
                import wiringpi as wiringpi_module  # type: ignore[no-redef]
            except ImportError as exc:
                raise RuntimeError(
                    "wiringOP-Python nao instalado; GPIO real permanece bloqueado"
                ) from exc
        self._wiringpi = wiringpi_module
        self._pins: set[int] = set()
        result = self._wiringpi.wiringPiSetup()
        if result == -1:
            raise RuntimeError("wiringPiSetup falhou")

    def setup_output(self, pin: int) -> None:
        self._wiringpi.pinMode(pin, 1)
        self._wiringpi.digitalWrite(pin, 0)
        self._pins.add(pin)

    def write(self, pin: int, value: bool) -> None:
        if pin not in self._pins:
            raise RuntimeError(f"GPIO wPi {pin} nao foi configurado como saida")
        self._wiringpi.digitalWrite(pin, int(value))

    def close(self) -> None:
        for pin in self._pins:
            self._wiringpi.digitalWrite(pin, 0)
