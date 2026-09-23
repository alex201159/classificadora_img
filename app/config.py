from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RoiConfig:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class CameraConfig:
    device: int
    width: int
    height: int
    fps: int
    roi: RoiConfig
    max_read_failures: int


@dataclass(frozen=True)
class ConveyorConfig:
    speed_mm_s: float
    gpio: int | None = None
    active_high: bool = True


@dataclass(frozen=True)
class TimingConfig:
    processing_latency_ms: float
    valve_response_ms: float


@dataclass(frozen=True)
class OutputConfig:
    gpio: int | None
    distance_mm: float
    pulse_ms: float
    active_high: bool = True
    delay_ms: float | None = None


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    file: Path


@dataclass(frozen=True)
class InterfaceConfig:
    host: str
    port: int
    open_browser: bool
    catalog_file: Path
    images_dir: Path


@dataclass(frozen=True)
class RecognitionConfig:
    ratio_threshold: float
    min_good_matches: int
    min_inliers: int
    ambiguity_ratio: float
    scan_interval_ms: int
    stable_hits: int
    background_threshold: int
    min_foreground_ratio: float
    max_image_width: int
    sift_features: int
    flann_checks: int
    max_tracking_distance_px: float
    max_missed_frames: int
    crop_margin_px: int
    min_detection_area_px: float
    reject_unrecognized: bool
    color_weight: float
    color_candidate_margin: float
    max_color_references_per_class: int
    min_color_similarity: float
    max_elongation_ratio: float


@dataclass(frozen=True)
class MachineConfig:
    name: str
    simulation: bool
    gpio_numbering: str
    camera: CameraConfig
    conveyor: ConveyorConfig
    timing: TimingConfig
    outputs: dict[str, OutputConfig]
    logging: LoggingConfig
    interface: InterfaceConfig
    recognition: RecognitionConfig


class ConfigError(ValueError):
    """Raised when machine configuration is unsafe or incomplete."""


def load_config(path: str | Path) -> MachineConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}

    try:
        machine = raw["machine"]
        camera = raw["camera"]
        roi = camera["roi"]
        conveyor = raw["conveyor"]
        timing = raw.get("timing", {})
        outputs = raw["outputs"]
        logging = raw.get("logging", {})
        interface = raw.get("interface", {})
        recognition = raw.get("recognition", {})
    except KeyError as exc:
        raise ConfigError(f"configuracao ausente: {exc.args[0]}") from exc

    parsed = MachineConfig(
        name=str(machine.get("name", "separador_tampas")),
        simulation=bool(machine.get("simulation", True)),
        gpio_numbering=str(machine.get("gpio_numbering", "wpi")).lower(),
        camera=CameraConfig(
            device=int(camera.get("device", 0)),
            width=_positive_int(camera.get("width"), "camera.width"),
            height=_positive_int(camera.get("height"), "camera.height"),
            fps=_positive_int(camera.get("fps", 30), "camera.fps"),
            roi=RoiConfig(
                x=_non_negative_int(roi.get("x", 0), "camera.roi.x"),
                y=_non_negative_int(roi.get("y", 0), "camera.roi.y"),
                width=_positive_int(roi.get("width"), "camera.roi.width"),
                height=_positive_int(roi.get("height"), "camera.roi.height"),
            ),
            max_read_failures=_positive_int(
                camera.get("max_read_failures", 5), "camera.max_read_failures"
            ),
        ),
        conveyor=ConveyorConfig(
            speed_mm_s=_positive_float(conveyor.get("speed_mm_s"), "conveyor.speed_mm_s"),
            gpio=_optional_pin(conveyor.get("gpio"), "conveyor.gpio"),
            active_high=bool(conveyor.get("active_high", True)),
        ),
        timing=TimingConfig(
            processing_latency_ms=_non_negative_float(
                timing.get("processing_latency_ms", 0), "timing.processing_latency_ms"
            ),
            valve_response_ms=_non_negative_float(
                timing.get("valve_response_ms", 0), "timing.valve_response_ms"
            ),
        ),
        outputs=_parse_outputs(outputs),
        logging=LoggingConfig(
            level=str(logging.get("level", "INFO")).upper(),
            file=Path(logging.get("file", "logs/separador.log")),
        ),
        interface=InterfaceConfig(
            host=str(interface.get("host", "127.0.0.1")),
            port=_port(interface.get("port", 8080)),
            open_browser=bool(interface.get("open_browser", True)),
            catalog_file=Path(interface.get("catalog_file", "data/cap_catalog.json")),
            images_dir=Path(interface.get("images_dir", "data/cap_images")),
        ),
        recognition=RecognitionConfig(
            ratio_threshold=_ratio(recognition.get("ratio_threshold", 0.72), "recognition.ratio_threshold"),
            min_good_matches=_positive_int(
                recognition.get("min_good_matches", 8), "recognition.min_good_matches"
            ),
            min_inliers=_positive_int(recognition.get("min_inliers", 5), "recognition.min_inliers"),
            ambiguity_ratio=_positive_float(
                recognition.get("ambiguity_ratio", 1.12), "recognition.ambiguity_ratio"
            ),
            scan_interval_ms=_positive_int(
                recognition.get("scan_interval_ms", 400), "recognition.scan_interval_ms"
            ),
            stable_hits=_positive_int(recognition.get("stable_hits", 2), "recognition.stable_hits"),
            background_threshold=_positive_int(
                recognition.get("background_threshold", 28), "recognition.background_threshold"
            ),
            min_foreground_ratio=_ratio(
                recognition.get("min_foreground_ratio", 0.025),
                "recognition.min_foreground_ratio",
            ),
            max_image_width=_positive_int(
                recognition.get("max_image_width", 640), "recognition.max_image_width"
            ),
            sift_features=_positive_int(
                recognition.get("sift_features", 900), "recognition.sift_features"
            ),
            flann_checks=_positive_int(
                recognition.get("flann_checks", 16), "recognition.flann_checks"
            ),
            max_tracking_distance_px=_positive_float(
                recognition.get("max_tracking_distance_px", 60),
                "recognition.max_tracking_distance_px",
            ),
            max_missed_frames=_non_negative_int(
                recognition.get("max_missed_frames", 3),
                "recognition.max_missed_frames",
            ),
            crop_margin_px=_non_negative_int(
                recognition.get("crop_margin_px", 15), "recognition.crop_margin_px"
            ),
            min_detection_area_px=_positive_float(
                recognition.get("min_detection_area_px", 150),
                "recognition.min_detection_area_px",
            ),
            reject_unrecognized=bool(recognition.get("reject_unrecognized", True)),
            color_weight=_ratio(
                recognition.get("color_weight", 0.55),
                "recognition.color_weight",
            ),
            color_candidate_margin=_ratio(
                recognition.get("color_candidate_margin", 0.12),
                "recognition.color_candidate_margin",
            ),
            max_color_references_per_class=_positive_int(
                recognition.get("max_color_references_per_class", 2),
                "recognition.max_color_references_per_class",
            ),
            min_color_similarity=_ratio(
                recognition.get("min_color_similarity", 0.70),
                "recognition.min_color_similarity",
            ),
            max_elongation_ratio=_positive_float(
                recognition.get("max_elongation_ratio", 2.0),
                "recognition.max_elongation_ratio",
            ),
        ),
    )
    _validate_config(parsed)
    return parsed


def _parse_outputs(outputs: dict[str, Any]) -> dict[str, OutputConfig]:
    if not outputs:
        raise ConfigError("ao menos uma saida deve ser configurada")

    parsed: dict[str, OutputConfig] = {}
    for name, output in outputs.items():
        gpio = output.get("gpio")
        parsed[str(name)] = OutputConfig(
            gpio=_optional_pin(gpio, f"outputs.{name}.gpio"),
            distance_mm=_non_negative_float(output.get("distance_mm"), f"outputs.{name}.distance_mm"),
            pulse_ms=_positive_float(output.get("pulse_ms"), f"outputs.{name}.pulse_ms"),
            active_high=bool(output.get("active_high", True)),
            delay_ms=(
                None
                if output.get("delay_ms") is None
                else _non_negative_float(output.get("delay_ms"), f"outputs.{name}.delay_ms")
            ),
        )
    return parsed


def _validate_config(config: MachineConfig) -> None:
    if config.gpio_numbering != "wpi":
        raise ConfigError("machine.gpio_numbering deve ser wpi")
    if config.recognition.max_elongation_ratio <= 1:
        raise ConfigError("recognition.max_elongation_ratio deve ser maior que um")
    roi = config.camera.roi
    if roi.x + roi.width > config.camera.width or roi.y + roi.height > config.camera.height:
        raise ConfigError("ROI deve estar dentro das dimensoes configuradas da camera")

    if not config.simulation:
        undefined = [name for name, output in config.outputs.items() if output.gpio is None]
        if undefined:
            joined = ", ".join(undefined)
            raise ConfigError(f"GPIO real ausente para saidas: {joined}")
        if config.conveyor.gpio is None:
            raise ConfigError("GPIO real ausente para a esteira")

    configured_pins = [
        pin
        for pin in [config.conveyor.gpio, *(output.gpio for output in config.outputs.values())]
        if pin is not None
    ]
    if len(configured_pins) != len(set(configured_pins)):
        raise ConfigError("cada saida deve usar um GPIO exclusivo")


def _positive_int(value: Any, field: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ConfigError(f"{field} deve ser maior que zero")
    return parsed


def _non_negative_int(value: Any, field: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ConfigError(f"{field} nao pode ser negativo")
    return parsed


def _positive_float(value: Any, field: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ConfigError(f"{field} deve ser maior que zero")
    return parsed


def _non_negative_float(value: Any, field: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise ConfigError(f"{field} nao pode ser negativo")
    return parsed


def _port(value: Any) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise ConfigError("interface.port deve estar entre 1 e 65535")
    return parsed


def _ratio(value: Any, field: str) -> float:
    parsed = float(value)
    if not 0 < parsed < 1:
        raise ConfigError(f"{field} deve estar entre zero e um")
    return parsed


def _optional_pin(value: Any, field: str) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed < 0:
        raise ConfigError(f"{field} nao pode ser negativo")
    return parsed
