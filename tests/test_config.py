from __future__ import annotations

from pathlib import Path

import pytest

from app.config import ConfigError, load_config


def test_load_default_config() -> None:
    config = load_config(Path("config/machine.yaml"))

    assert config.simulation is True
    assert config.camera.device == 0
    assert config.gpio_numbering == "wpi"
    assert config.conveyor.gpio == 19
    assert config.outputs["red_round"].gpio == 20
    assert config.outputs["red_round"].delay_ms == 1500


def test_roi_must_fit_camera(tmp_path: Path) -> None:
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(
        """
machine:
  name: test
  simulation: true
camera:
  device: 0
  width: 100
  height: 100
  fps: 30
  roi:
    x: 50
    y: 0
    width: 100
    height: 100
conveyor:
  speed_mm_s: 300
outputs:
  reject:
    gpio: null
    distance_mm: 500
    pulse_ms: 100
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_file)
