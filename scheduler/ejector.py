from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from hardware.valves import ValveController


@dataclass(order=True)
class ScheduledEvent:
    due_time: float
    sequence: int
    output_name: str = field(compare=False)
    turn_on: bool = field(compare=False)


class EjectorScheduler:
    def __init__(self, valves: ValveController) -> None:
        self.valves = valves
        self._events: list[ScheduledEvent] = []
        self._sequence = 0

    def schedule_ejection(self, output_name: str, fire_at: float, pulse_s: float) -> None:
        if pulse_s <= 0:
            raise ValueError("pulse_s deve ser maior que zero")
        self._push(output_name, fire_at, True)
        self._push(output_name, fire_at + pulse_s, False)

    def tick(self, now: float) -> int:
        fired = 0
        while self._events and self._events[0].due_time <= now:
            event = heapq.heappop(self._events)
            if event.turn_on:
                self.valves.on(event.output_name)
            else:
                self.valves.off(event.output_name)
            fired += 1
        return fired

    def pending_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
        self.valves.all_off()

    def _push(self, output_name: str, due_time: float, turn_on: bool) -> None:
        self._sequence += 1
        heapq.heappush(
            self._events,
            ScheduledEvent(
                due_time=due_time,
                sequence=self._sequence,
                output_name=output_name,
                turn_on=turn_on,
            ),
        )
