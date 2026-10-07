import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import app


def test_render_postgres_url_uses_installed_driver():
    value = Settings(database_url="postgresql://user:password@db.example/folio")
    assert value.database_url == "postgresql+psycopg://user:password@db.example/folio"


def test_legacy_postgres_url_uses_installed_driver():
    value = Settings(database_url="postgres://user:password@db.example/folio")
    assert value.database_url.startswith("postgresql+psycopg://")


def test_public_demo_rejects_local_token(monkeypatch):
    monkeypatch.setattr(settings, "public_demo", True)
    monkeypatch.setattr(settings, "embedded_worker", False)
    with pytest.raises(RuntimeError, match="unique operator token"):
        with TestClient(app):
            pass
