from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config import ConfigError, load_config


def test_load_default_config() -> None:
    config = load_config(Path("config/machine.yaml"))

    assert config.simulation is True
    assert config.camera.device >= 0
    assert config.gpio_numbering == "wpi"
    assert config.conveyor.gpio == 19
    assert config.outputs["red_round"].gpio == 20
    assert config.outputs["red_round"].delay_ms == 1500
    assert config.recognition.stable_hits == 3
    assert config.recognition.reject_unrecognized is False
    assert config.recognition.color_weight == pytest.approx(0.55)
    assert config.recognition.max_tracking_distance_px == 60
    assert config.recognition.max_missed_frames == 3
    assert config.recognition.crop_margin_px == 15


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


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("recognition", "stable_hits", 0, "stable_hits"),
        ("recognition", "max_missed_frames", -1, "max_missed_frames"),
        ("recognition", "max_tracking_distance_px", 0, "max_tracking_distance_px"),
        ("recognition", "color_weight", 0, "color_weight"),
        ("outputs.red_round", "pulse_ms", 0, "pulse_ms"),
        ("conveyor", "speed_mm_s", 0, "speed_mm_s"),
    ],
)
def test_invalid_numeric_configuration_is_rejected(
    tmp_path: Path,
    section: str,
    field: str,
    value: int,
    message: str,
) -> None:
    raw = yaml.safe_load(Path("config/machine.yaml").read_text(encoding="utf-8"))
    target = raw
    for part in section.split("."):
        target = target[part]
    target[field] = value
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_config(config_file)


def test_duplicate_gpio_configuration_is_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("config/machine.yaml").read_text(encoding="utf-8"))
    raw["outputs"]["reject"]["gpio"] = raw["conveyor"]["gpio"]
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigError, match="GPIO exclusivo"):
        load_config(config_file)
