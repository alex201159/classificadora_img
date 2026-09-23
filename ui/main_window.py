from __future__ import annotations

from app.controller import MachineStatus


class TextStatusView:
    def render(self, status: MachineStatus) -> str:
        safe = "SEGURO" if status.safe_state else "PRODUCAO"
        return (
            f"{status.state.value} | {safe} | "
            f"total reconhecido={status.total_caps}"
        )
