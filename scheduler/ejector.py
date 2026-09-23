from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from hardware.valves import ValveController


@dataclass(order=True)
class ScheduledEvent:
    due_time: float
    priority: int
    sequence: int
    output_name: str = field(compare=False)
    turn_on: bool = field(compare=False)


class EjectorScheduler:
    def __init__(self, valves: ValveController) -> None:
        self.valves = valves
        self._events: list[ScheduledEvent] = []
        self._sequence = 0
        self._active_pulses: dict[str, int] = {}

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
                active = self._active_pulses.get(event.output_name, 0)
                if active == 0:
                    self.valves.on(event.output_name)
                self._active_pulses[event.output_name] = active + 1
            else:
                active = self._active_pulses.get(event.output_name, 0)
                if active <= 1:
                    self.valves.off(event.output_name)
                    self._active_pulses.pop(event.output_name, None)
                else:
                    self._active_pulses[event.output_name] = active - 1
            fired += 1
        return fired

    def pending_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._active_pulses.clear()
        self.valves.all_off()

    def _push(self, output_name: str, due_time: float, turn_on: bool) -> None:
        self._sequence += 1
        heapq.heappush(
            self._events,
            ScheduledEvent(
                due_time=due_time,
                priority=0 if turn_on else 1,
                sequence=self._sequence,
                output_name=output_name,
                turn_on=turn_on,
            ),
        )
