import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import api, main, retention, review, worker
from app.config import settings
from app.db import Base


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, expire_on_commit=False)
    for module in (api, main, retention, review, worker):
        monkeypatch.setattr(module, "Session", session)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    monkeypatch.setattr(settings, "provider", "fixture")
    with TestClient(main.app, headers={"Authorization": "Bearer local-demo-only"}) as client:
        yield client
    engine.dispose()
