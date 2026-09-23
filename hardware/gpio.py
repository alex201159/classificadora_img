from __future__ import annotations

import ctypes
import ctypes.util
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


class _CtypesWiringPi:
    """Small adapter for the wiringOP shared library installed on the board."""

    def __init__(self, library: object | None = None) -> None:
        self._library = library or self._load_library()
        self._setup = self._library.wiringPiSetup
        self._setup.argtypes = []
        self._setup.restype = ctypes.c_int
        self._pin_mode = self._library.pinMode
        self._pin_mode.argtypes = [ctypes.c_int, ctypes.c_int]
        self._pin_mode.restype = None
        self._digital_write = self._library.digitalWrite
        self._digital_write.argtypes = [ctypes.c_int, ctypes.c_int]
        self._digital_write.restype = None

    @staticmethod
    def _load_library() -> object:
        candidates = [
            ctypes.util.find_library("wiringPi"),
            "libwiringPi.so",
            "/usr/local/lib/libwiringPi.so",
        ]
        errors: list[str] = []
        for candidate in dict.fromkeys(item for item in candidates if item):
            try:
                return ctypes.CDLL(candidate, use_errno=True)
            except OSError as exc:
                errors.append(str(exc))
        detail = f" ({'; '.join(errors)})" if errors else ""
        raise RuntimeError(f"biblioteca libwiringPi.so nao encontrada{detail}")

    def wiringPiSetup(self) -> int:
        return int(self._setup())

    def pinMode(self, pin: int, mode: int) -> None:
        self._pin_mode(pin, mode)

    def digitalWrite(self, pin: int, value: int) -> None:
        self._digital_write(pin, value)


class OrangePiGPIO:
    """Orange Pi backend using wiringOP's wPi numbering."""

    def __init__(self, wiringpi_module: object | None = None) -> None:
        if wiringpi_module is None:
            try:
                import wiringpi as wiringpi_module  # type: ignore[no-redef]
            except ImportError:
                try:
                    wiringpi_module = _CtypesWiringPi()
                except RuntimeError as exc:
                    raise RuntimeError(
                        "wiringOP indisponivel; instale a libwiringPi ou "
                        "wiringOP-Python antes de habilitar o GPIO real"
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
