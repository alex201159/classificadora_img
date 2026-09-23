from __future__ import annotations

import argparse
import logging
from pathlib import Path

from camera.capture import CameraDetector


def main() -> int:
    parser = argparse.ArgumentParser(description="Separador automatico de tampas")
    parser.add_argument("--config", default="config/machine.yaml", help="arquivo de configuracao")
    parser.add_argument("--detect-cameras", action="store_true", help="lista cameras disponiveis")
    parser.add_argument("--once", action="store_true", help="inicializa, executa um tick e encerra")
    parser.add_argument("--ui", action="store_true", help="abre a interface grafica local")
    parser.add_argument("--flet", action="store_true", help="abre a interface desktop Flet")
    parser.add_argument("--host", help="endereco da interface; sobrescreve a configuracao")
    parser.add_argument("--port", type=int, help="porta da interface; sobrescreve a configuracao")
    parser.add_argument("--no-browser", action="store_true", help="nao abre o navegador automaticamente")
    args = parser.parse_args()

    if args.detect_cameras:
        return _detect_cameras()

    from app.config import ConfigError, load_config
    from app.controller import MachineController
    from ui.main_window import TextStatusView

    try:
        config = load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"Erro de configuracao: {exc}")
        return 2

    _setup_logging(config.logging.file, config.logging.level)
    controller = MachineController(config)
    try:
        status = controller.initialize()
        print(TextStatusView().render(status))
        if args.once:
            controller.tick()
            return 0

        if args.ui:
            from ui.web_app import WebInterface

            interface = WebInterface(
                controller,
                config,
                host=args.host or config.interface.host,
                port=args.port or config.interface.port,
            )
            interface.run(open_browser=config.interface.open_browser and not args.no_browser)
            return 0

        if args.flet:
            from ui.flet_app import run_flet_interface

            run_flet_interface(controller, config, args.config)
            return 0

        controller.start()
        while controller.status.running:
            controller.tick()
    except KeyboardInterrupt:
        controller.stop()
    finally:
        controller.shutdown()
    return 0


def _detect_cameras() -> int:
    detector = CameraDetector()
    cameras = detector.list_available()
    if not cameras:
        print("Nenhuma camera detectada.")
        return 1

    for camera in cameras:
        print(
            f"Camera {camera.index}: "
            f"{camera.width or '?'}x{camera.height or '?'} "
            f"fps={camera.fps or '?'}"
        )
    return 0


def _setup_logging(log_file: Path, level: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )


if __name__ == "__main__":
    raise SystemExit(main())
