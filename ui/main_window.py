from __future__ import annotations

from app.controller import MachineStatus


class TextStatusView:
    def render(self, status: MachineStatus) -> str:
        state = "RODANDO" if status.running else "PARADO"
        safe = "SEGURO" if status.safe_state else "PRODUCAO"
        return f"{state} | {safe} | total={status.total_caps} | rejeitadas={status.rejected_caps}"
