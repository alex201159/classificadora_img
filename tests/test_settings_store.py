from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigError
from app.settings_store import MachineSettingsStore


def _copy_config(tmp_path: Path) -> Path:
    target = tmp_path / "machine.yaml"
    target.write_text(Path("config/machine.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_output_can_be_added_updated_and_deleted(tmp_path: Path) -> None:
    config_path = _copy_config(tmp_path)
    store = MachineSettingsStore(config_path)

    added = store.save_output("azul", 21, 850, 65, True, create=True)
    assert added.outputs["azul"].gpio == 21
    assert added.outputs["azul"].delay_ms == 850

    updated = store.save_output("azul", 21, 920, 70, False)
    assert updated.outputs["azul"].delay_ms == 920
    assert updated.outputs["azul"].pulse_ms == 70
    assert updated.outputs["azul"].active_high is False

    deleted = store.delete_output("azul")
    assert "azul" not in deleted.outputs


def test_output_rejects_pin_already_used_by_conveyor(tmp_path: Path) -> None:
    config_path = _copy_config(tmp_path)
    store = MachineSettingsStore(config_path)

    with pytest.raises(ConfigError, match="GPIO exclusivo"):
        store.save_output("duplicada", 19, 1000, 80, True, create=True)

    assert "duplicada" not in config_path.read_text(encoding="utf-8")


def test_machine_camera_and_recognition_settings_are_persisted(tmp_path: Path) -> None:
    config_path = _copy_config(tmp_path)
    store = MachineSettingsStore(config_path)

    updated = store.save_machine_settings(
        name="Linha Principal",
        camera_device=2,
        camera_width=1920,
        camera_height=1080,
        camera_fps=60,
        conveyor_speed_mm_s=420,
        min_good_matches=10,
        min_inliers=6,
        scan_interval_ms=90,
        stable_hits=2,
        background_threshold=32,
        min_foreground_ratio=0.03,
        max_image_width=720,
    )

    assert updated.name == "Linha Principal"
    assert updated.camera.device == 2
    assert updated.camera.roi.width == 1920
    assert updated.camera.roi.height == 1080
    assert updated.conveyor.speed_mm_s == 420
    assert updated.recognition.min_good_matches == 10
    assert updated.recognition.min_foreground_ratio == pytest.approx(0.03)
