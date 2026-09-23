from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import yaml

from app.config import MachineConfig, load_config


class SettingsError(ValueError):
    """Raised when a settings edit cannot be persisted safely."""


class MachineSettingsStore:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)

    def save_output(
        self,
        name: str,
        gpio: int | None,
        delay_ms: float,
        pulse_ms: float,
        active_high: bool,
        create: bool = False,
    ) -> MachineConfig:
        normalized_name = name.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", normalized_name):
            raise SettingsError("Use um nome simples: letras, numeros e sublinhado")

        def edit(raw: dict[str, Any]) -> None:
            outputs = raw.setdefault("outputs", {})
            exists = normalized_name in outputs
            if create and exists:
                raise SettingsError("Ja existe uma saida com esse nome")
            if not create and not exists:
                raise SettingsError("Saida de expulsao nao encontrada")
            previous = outputs.get(normalized_name, {})
            outputs[normalized_name] = {
                "gpio": gpio,
                "active_high": active_high,
                "delay_ms": delay_ms,
                "distance_mm": float(previous.get("distance_mm", 0)),
                "pulse_ms": pulse_ms,
            }

        return self._edit(edit)

    def save_machine_settings(
        self,
        *,
        name: str,
        camera_device: int,
        camera_width: int,
        camera_height: int,
        camera_fps: int,
        conveyor_speed_mm_s: float,
        min_good_matches: int,
        min_inliers: int,
        scan_interval_ms: int,
        stable_hits: int,
        background_threshold: int,
        min_foreground_ratio: float,
        max_image_width: int,
        color_weight: float,
    ) -> MachineConfig:
        clean_name = name.strip()
        if not clean_name:
            raise SettingsError("Informe o nome da maquina")
        if len(clean_name) > 80:
            raise SettingsError("O nome da maquina deve ter no maximo 80 caracteres")

        def edit(raw: dict[str, Any]) -> None:
            raw.setdefault("machine", {})["name"] = clean_name
            camera = raw.setdefault("camera", {})
            camera.update(
                {
                    "device": camera_device,
                    "width": camera_width,
                    "height": camera_height,
                    "fps": camera_fps,
                    "roi": {
                        "x": 0,
                        "y": 0,
                        "width": camera_width,
                        "height": camera_height,
                    },
                }
            )
            raw.setdefault("conveyor", {})["speed_mm_s"] = conveyor_speed_mm_s
            recognition = raw.setdefault("recognition", {})
            recognition.update(
                {
                    "min_good_matches": min_good_matches,
                    "min_inliers": min_inliers,
                    "scan_interval_ms": scan_interval_ms,
                    "stable_hits": stable_hits,
                    "background_threshold": background_threshold,
                    "min_foreground_ratio": min_foreground_ratio,
                    "max_image_width": max_image_width,
                    "color_weight": color_weight,
                }
            )

        return self._edit(edit)

    def delete_output(self, name: str) -> MachineConfig:
        def edit(raw: dict[str, Any]) -> None:
            outputs = raw.get("outputs", {})
            if name not in outputs:
                raise SettingsError("Saida de expulsao nao encontrada")
            if len(outputs) <= 1:
                raise SettingsError("A maquina deve manter ao menos uma saida")
            del outputs[name]

        return self._edit(edit)

    def _edit(self, editor: Callable[[dict[str, Any]], None]) -> MachineConfig:
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise SettingsError(f"Nao foi possivel ler a configuracao: {exc}") from exc

        editor(raw)
        temporary = self.config_path.with_suffix(self.config_path.suffix + ".pending")
        try:
            temporary.write_text(
                yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            validated = load_config(temporary)
            temporary.replace(self.config_path)
            return validated
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
