import json
from fastapi.testclient import TestClient
from ol import api
from ol.build import load_info


def test_build_file_is_validated_and_only_exposes_metadata(tmp_path):
    p = tmp_path / "build-info.json"
    assert load_info(p)["version"] == "unknown"
    p.write_text(json.dumps(dict(commit="a" * 40, dirty=True, builtAt="2026-11-06T00:00:00Z", password="never expose")))
    info = load_info(p)
    assert info["version"] == "a" * 12 + "-dirty"
    assert "password" not in info
    p.write_text(json.dumps(dict(commit="invalid", dirty=False, builtAt="2026-11-06T00:00:00Z")))
    assert load_info(p)["version"] == "unknown"


def test_version_endpoint_does_not_need_a_database(monkeypatch):
    def unavailable():
        raise AssertionError("Version must not access the database")

    monkeypatch.setattr(api, "session", unavailable)
    with TestClient(api.app) as client:
        response = client.get("/api/version")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == client.get("/api/health/live").json()["build"]
