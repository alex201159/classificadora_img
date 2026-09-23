from __future__ import annotations

from hardware.gpio import OrangePiGPIO, SimulatedGPIO, _CtypesWiringPi


class FakeFunction:
    def __init__(self, result: int | None = None) -> None:
        self.result = result
        self.calls: list[tuple[int, ...]] = []
        self.argtypes: list[object] = []
        self.restype: object | None = None

    def __call__(self, *args: int) -> int | None:
        self.calls.append(args)
        return self.result


class FakeLibrary:
    def __init__(self) -> None:
        self.wiringPiSetup = FakeFunction(0)
        self.pinMode = FakeFunction()
        self.digitalWrite = FakeFunction()


def test_ctypes_wiringpi_adapter_calls_library() -> None:
    library = FakeLibrary()
    adapter = _CtypesWiringPi(library)

    assert adapter.wiringPiSetup() == 0
    adapter.pinMode(19, 1)
    adapter.digitalWrite(19, 1)

    assert library.pinMode.calls == [(19, 1)]
    assert library.digitalWrite.calls == [(19, 1)]


def test_orangepi_gpio_sets_outputs_low_and_closes_safely() -> None:
    wiringpi = _CtypesWiringPi(FakeLibrary())
    gpio = OrangePiGPIO(wiringpi)

    gpio.setup_output(19)
    gpio.write(19, True)
    gpio.close()

    assert wiringpi._library.digitalWrite.calls == [(19, 0), (19, 1), (19, 0)]


def test_simulated_gpio_finishes_with_all_outputs_off() -> None:
    gpio = SimulatedGPIO()
    gpio.setup_output(19)
    gpio.setup_output(20)
    gpio.write(19, True)
    gpio.write(20, True)

    gpio.close()

    assert gpio.states == {19: False, 20: False}
