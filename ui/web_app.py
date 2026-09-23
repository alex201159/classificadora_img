from __future__ import annotations

import base64
import binascii
import json
import logging
import mimetypes
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from app.cap_catalog import CapCatalog, CatalogError
from app.config import MachineConfig
from app.controller import MachineController


class WebInterface:
    def __init__(
        self,
        controller: MachineController,
        config: MachineConfig,
        host: str,
        port: int,
    ) -> None:
        self.controller = controller
        self.config = config
        self.host = host
        self.port = port
        self.catalog = CapCatalog(config.interface.catalog_file, config.interface.images_dir)
        self.static_dir = Path(__file__).with_name("static")
        self._stop_event = threading.Event()
        self._log = logging.getLogger(__name__)

    def run(self, open_browser: bool = True) -> None:
        handler = self._handler_class()
        server = ThreadingHTTPServer((self.host, self.port), handler)
        tick_thread = threading.Thread(target=self._tick_loop, name="machine-tick", daemon=True)
        tick_thread.start()

        url = f"http://{self.host}:{server.server_port}"
        self._log.info("Interface disponivel em %s", url)
        print(f"Interface disponivel em {url}")
        if open_browser:
            threading.Timer(0.4, webbrowser.open, args=(url,)).start()

        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            self._stop_event.set()
            server.server_close()
            tick_thread.join(timeout=1)

    def _tick_loop(self) -> None:
        while not self._stop_event.wait(0.02):
            try:
                self.controller.tick()
            except Exception:
                self._log.exception("Falha no ciclo de controle")
                self.controller.enter_safe_state("falha no ciclo de controle")

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        application = self

        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                application._handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                application._handle_post(self)

            def log_message(self, format: str, *args: Any) -> None:
                application._log.debug("HTTP %s", format % args)

        return RequestHandler

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        path = unquote(urlparse(handler.path).path)
        if path == "/api/status":
            self._send_json(handler, self._status_payload())
            return
        if path == "/api/config":
            self._send_json(
                handler,
                {
                    "machine_name": self.config.name,
                    "simulation": self.config.simulation,
                    "camera_device": self.config.camera.device,
                    "outputs": list(self.config.outputs),
                },
            )
            return
        if path == "/api/classes":
            self._send_json(handler, {"classes": self.catalog.list_classes()})
            return
        if path.startswith("/media/"):
            self._serve_media(handler, path)
            return
        if path == "/":
            self._serve_file(handler, self.static_dir / "index.html")
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            candidate = (self.static_dir / relative).resolve()
            if self.static_dir.resolve() not in candidate.parents:
                self._send_error(handler, HTTPStatus.NOT_FOUND, "Arquivo nao encontrado")
                return
            self._serve_file(handler, candidate)
            return
        self._send_error(handler, HTTPStatus.NOT_FOUND, "Rota nao encontrada")

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        path = unquote(urlparse(handler.path).path)
        try:
            payload = self._read_json(handler)
            if path == "/api/machine/start":
                self.controller.start()
                self._send_json(handler, self._status_payload())
                return
            if path == "/api/machine/stop":
                self.controller.stop()
                self._send_json(handler, self._status_payload())
                return
            if path == "/api/classes":
                output = str(payload.get("output", "reject"))
                if output not in self.config.outputs:
                    raise CatalogError("Saida configurada invalida")
                created = self.catalog.create_class(
                    name=str(payload.get("name", "")),
                    color=str(payload.get("color", "")),
                    shape=str(payload.get("shape", "")),
                    output=output,
                )
                self._send_json(handler, created, HTTPStatus.CREATED)
                return
            if path.startswith("/api/classes/") and path.endswith("/samples"):
                class_id = path.removeprefix("/api/classes/").removesuffix("/samples").strip("/")
                image, media_type = self._decode_data_url(str(payload.get("image", "")))
                sample = self.catalog.add_sample(class_id, image, media_type)
                self._send_json(handler, sample, HTTPStatus.CREATED)
                return
            self._send_error(handler, HTTPStatus.NOT_FOUND, "Rota nao encontrada")
        except (CatalogError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(handler, HTTPStatus.BAD_REQUEST, str(exc))
        except Exception:
            self._log.exception("Erro ao processar requisicao")
            self.controller.enter_safe_state("falha na interface")
            self._send_error(handler, HTTPStatus.INTERNAL_SERVER_ERROR, "Falha interna; maquina parada")

    def _status_payload(self) -> dict[str, Any]:
        status = self.controller.status
        return {
            "running": status.running,
            "safe_state": status.safe_state,
            "camera_available": status.camera_available,
            "total_caps": status.total_caps,
            "rejected_caps": status.rejected_caps,
            "counters_by_class": status.counters_by_class,
        }

    def _serve_media(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            self._send_error(handler, HTTPStatus.NOT_FOUND, "Imagem nao encontrada")
            return
        media_path = self.catalog.media_path(parts[1], parts[2])
        if media_path is None:
            self._send_error(handler, HTTPStatus.NOT_FOUND, "Imagem nao encontrada")
            return
        self._serve_file(handler, media_path)

    @staticmethod
    def _serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
        if not path.is_file():
            WebInterface._send_error(handler, HTTPStatus.NOT_FOUND, "Arquivo nao encontrado")
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(content)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(content)

    @staticmethod
    def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        length = int(handler.headers.get("Content-Length", "0"))
        if length <= 0 or length > 14 * 1024 * 1024:
            raise ValueError("Conteudo da requisicao invalido")
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("O corpo da requisicao deve ser um objeto")
        return payload

    @staticmethod
    def _decode_data_url(data_url: str) -> tuple[bytes, str]:
        try:
            header, encoded = data_url.split(",", 1)
            if not header.startswith("data:image/") or ";base64" not in header:
                raise ValueError
            media_type = header[5:].split(";", 1)[0]
            return base64.b64decode(encoded, validate=True), media_type
        except (ValueError, binascii.Error) as exc:
            raise CatalogError("Imagem enviada em formato invalido") from exc

    @staticmethod
    def _send_json(
        handler: BaseHTTPRequestHandler,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    @staticmethod
    def _send_error(handler: BaseHTTPRequestHandler, status: HTTPStatus, message: str) -> None:
        WebInterface._send_json(handler, {"error": message}, status)
