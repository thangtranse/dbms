from fastapi.testclient import TestClient
from ol.api import app
from ol import api
from contextlib import contextmanager


def test_health_and_validation_without_database():
    with TestClient(app) as client:
        assert client.get("/api/health/live").json()["dataMode"] == "database"
        r = client.post(
            "/api/meals", json={"date": "2026-01-01", "itemIds": [], "label": "yes"}
        )
        assert r.status_code == 400
        assert "error" in r.json()
        assert client.post("/api/recommend", json={"context": {}}).status_code == 400


def test_errors_hide_credentials(monkeypatch):
    @contextmanager
    def broken():
        raise RuntimeError("password=never-return-this")
        yield

    monkeypatch.setattr(api, "session", broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/users")
        assert response.status_code == 503
        assert "never-return-this" not in response.text


def test_readiness_distinguishes_model_and_qdrant_failure(monkeypatch):
    class DB:
        def table(self, name):
            return "officelunch." + name

        def execute(self, *args):
            return [[1]]

    @contextmanager
    def session():
        yield DB()

    class Model:
        active = {
            "dishes": "officelunch_dishes",
            "transactions": "officelunch_transactions",
        }

        def refresh(self):
            return self

    class Q:
        def close(self):
            pass

        def collection_exists(self, name):
            raise ConnectionError("offline")

        def info(self):
            return True

    monkeypatch.setattr(api, "session", session)
    monkeypatch.setattr(api, "model", Model())
    monkeypatch.setattr(api, "qclient", Q)
    with TestClient(app) as client:
        r = client.get("/api/health/ready")
        assert r.status_code == 503
        assert r.json()["checks"] == dict(teradata=True, model=True, qdrant=False)

        def missing():
            raise FileNotFoundError("model")

        monkeypatch.setattr(api.model, "refresh", missing)
        r = client.get("/api/health/ready")
        assert r.json()["checks"] == dict(teradata=True, model=False, qdrant=True)


def test_avoid_tags_match_catalog_aliases_and_normalized_spellings():
    from ol.service import avoid_tag_values

    catalog = [
        {"tags": ["Thịt bò", "Món thịt bò", "bò", "thịt gà"]},
        {"tags": ["ĐẬU PHỘNG", "lạc rang", "lạc"]},
    ]
    assert avoid_tag_values([" BÒ ", "Peanuts"], catalog) == {
        " BÒ ", "Peanuts", "Thịt bò", "Món thịt bò", "bò", "ĐẬU PHỘNG", "lạc",
    }
    assert avoid_tag_values([], catalog) == set()
