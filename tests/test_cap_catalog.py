from __future__ import annotations

from pathlib import Path

import pytest

from app.cap_catalog import CapCatalog, CatalogError


def test_create_class_and_persist_image_sample(tmp_path: Path) -> None:
    catalog_file = tmp_path / "catalog.json"
    images_dir = tmp_path / "images"
    catalog = CapCatalog(catalog_file, images_dir)

    created = catalog.create_class("Vermelha 28 mm", "vermelha", "redonda", "red_round")
    sample = catalog.add_sample(created["id"], b"\xff\xd8\xfftest-image", "image/jpeg")

    reloaded = CapCatalog(catalog_file, images_dir).list_classes()
    assert reloaded[0]["name"] == "Vermelha 28 mm"
    assert reloaded[0]["samples"][0]["url"] == sample["url"]
    assert (images_dir / created["id"] / sample["filename"]).is_file()


def test_duplicate_class_name_is_rejected(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    catalog.create_class("Tampa Azul", "azul", "redonda", "reject")

    with pytest.raises(CatalogError, match="Ja existe"):
        catalog.create_class("tampa azul", "azul", "redonda", "reject")


def test_invalid_image_is_rejected(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    created = catalog.create_class("Teste", "outra", "outro", "reject")

    with pytest.raises(CatalogError, match="JPEG ou PNG"):
        catalog.add_sample(created["id"], b"not-an-image", "image/jpeg")


def test_delete_sample_removes_metadata_and_file(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    created = catalog.create_class("Teste", "outra", "outro", "reject")
    sample = catalog.add_sample(created["id"], b"\xff\xd8\xfftest-image", "image/jpeg")
    image_path = catalog.media_path(created["id"], sample["filename"])
    assert image_path is not None

    catalog.delete_sample(created["id"], sample["filename"])

    assert image_path.exists() is False
    assert catalog.list_classes()[0]["samples"] == []


def test_rename_class_keeps_id_and_samples(tmp_path: Path) -> None:
    catalog = CapCatalog(tmp_path / "catalog.json", tmp_path / "images")
    created = catalog.create_class("Alex", "preta", "outro", "reject")
    sample = catalog.add_sample(created["id"], b"\xff\xd8\xfftest-image", "image/jpeg")

    renamed = catalog.rename_class(created["id"], "Celular preto")

    assert renamed["id"] == created["id"]
    assert renamed["name"] == "Celular preto"
    assert renamed["samples"][0]["filename"] == sample["filename"]
