from __future__ import annotations

import json
import re
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CatalogError(ValueError):
    """Raised when cap class data or an image sample is invalid."""


class CapCatalog:
    MAX_IMAGE_BYTES = 10 * 1024 * 1024

    def __init__(self, catalog_file: str | Path, images_dir: str | Path) -> None:
        self.catalog_file = Path(catalog_file)
        self.images_dir = Path(images_dir)
        self._lock = threading.RLock()
        self.catalog_file.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        if not self.catalog_file.exists():
            self._write({"classes": []})

    def list_classes(self) -> list[dict[str, Any]]:
        with self._lock:
            classes = self._read()["classes"]
            return [dict(item, samples=list(item.get("samples", []))) for item in classes]

    def create_class(self, name: str, color: str, shape: str, output: str) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise CatalogError("Informe o nome da tampa")
        if len(clean_name) > 60:
            raise CatalogError("O nome da tampa deve ter no maximo 60 caracteres")

        with self._lock:
            data = self._read()
            normalized_name = clean_name.casefold()
            if any(item["name"].casefold() == normalized_name for item in data["classes"]):
                raise CatalogError("Ja existe uma tampa com esse nome")

            class_id = self._available_id(clean_name, data["classes"])
            cap_class = {
                "id": class_id,
                "name": clean_name,
                "color": color.strip() or "nao_informada",
                "shape": shape.strip() or "nao_informado",
                "output": output.strip() or "reject",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "samples": [],
            }
            data["classes"].append(cap_class)
            self._write(data)
            (self.images_dir / class_id).mkdir(parents=True, exist_ok=True)
            return dict(cap_class, samples=[])

    def rename_class(self, class_id: str, new_name: str) -> dict[str, Any]:
        clean_name = new_name.strip()
        if not clean_name:
            raise CatalogError("Informe o novo nome da tampa")
        if len(clean_name) > 60:
            raise CatalogError("O nome da tampa deve ter no maximo 60 caracteres")

        with self._lock:
            data = self._read()
            cap_class = next((item for item in data["classes"] if item["id"] == class_id), None)
            if cap_class is None:
                raise CatalogError("Classe de tampa nao encontrada")
            normalized_name = clean_name.casefold()
            if any(
                item["id"] != class_id and item["name"].casefold() == normalized_name
                for item in data["classes"]
            ):
                raise CatalogError("Ja existe uma tampa com esse nome")

            cap_class["name"] = clean_name
            self._write(data)
            return dict(cap_class, samples=list(cap_class.get("samples", [])))

    def add_sample(self, class_id: str, image: bytes, media_type: str) -> dict[str, Any]:
        if not image:
            raise CatalogError("A imagem recebida esta vazia")
        if len(image) > self.MAX_IMAGE_BYTES:
            raise CatalogError("A imagem excede o limite de 10 MB")

        extension = self._validate_image(image, media_type)
        with self._lock:
            data = self._read()
            cap_class = next((item for item in data["classes"] if item["id"] == class_id), None)
            if cap_class is None:
                raise CatalogError("Classe de tampa nao encontrada")

            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{extension}"
            class_dir = self.images_dir / class_id
            class_dir.mkdir(parents=True, exist_ok=True)
            image_path = class_dir / filename
            image_path.write_bytes(image)

            sample = {
                "filename": filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "url": f"/media/{class_id}/{filename}",
            }
            cap_class.setdefault("samples", []).append(sample)
            try:
                self._write(data)
            except Exception:
                image_path.unlink(missing_ok=True)
                raise
            return dict(sample)

    def delete_sample(self, class_id: str, filename: str) -> None:
        with self._lock:
            data = self._read()
            cap_class = next((item for item in data["classes"] if item["id"] == class_id), None)
            if cap_class is None:
                raise CatalogError("Classe de tampa nao encontrada")

            samples = cap_class.get("samples", [])
            sample = next((item for item in samples if item.get("filename") == filename), None)
            if sample is None:
                raise CatalogError("Imagem cadastrada nao encontrada")

            image_path = self.media_path(class_id, filename)
            cap_class["samples"] = [item for item in samples if item.get("filename") != filename]
            self._write(data)
            if image_path is not None:
                image_path.unlink(missing_ok=True)

    def media_path(self, class_id: str, filename: str) -> Path | None:
        if not re.fullmatch(r"[a-z0-9_-]+", class_id):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
            return None
        candidate = (self.images_dir / class_id / filename).resolve()
        root = self.images_dir.resolve()
        if root not in candidate.parents or not candidate.is_file():
            return None
        return candidate

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.catalog_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Nao foi possivel ler o catalogo: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("classes"), list):
            raise CatalogError("Formato do catalogo de tampas invalido")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        temporary = self.catalog_file.with_suffix(self.catalog_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.catalog_file)

    @staticmethod
    def _available_id(name: str, classes: list[dict[str, Any]]) -> str:
        normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
        base = re.sub(r"[^a-z0-9]+", "_", normalized.casefold()).strip("_") or "tampa"
        used = {item["id"] for item in classes}
        candidate = base
        counter = 2
        while candidate in used:
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    @staticmethod
    def _validate_image(image: bytes, media_type: str) -> str:
        normalized_type = media_type.split(";", 1)[0].strip().lower()
        if normalized_type in {"image/jpeg", "image/jpg"} and image.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if normalized_type == "image/png" and image.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        raise CatalogError("Use uma imagem JPEG ou PNG valida")
