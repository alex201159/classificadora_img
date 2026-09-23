from __future__ import annotations

from app.config import MachineConfig


class SettingsSummaryView:
    def render(self, config: MachineConfig) -> str:
        mode = "simulacao" if config.simulation else "producao"
        return f"{config.name} | modo={mode} | camera={config.camera.device}"
