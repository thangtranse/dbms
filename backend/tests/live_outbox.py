"""Real outage/retry smoke. Run with the background vector-worker stopped.
Uses an unreachable URL only in this process; never stops the actual Qdrant.
"""

import os
import httpx
from ol import vector
from ol.db import session
from ol.config import qclient

api = httpx.Client(
    base_url=os.getenv("API_URL", "http://host.docker.internal:3000"), timeout=90
)
meal = None
actual_url = os.environ["QDRANT_URL"]
try:
    response = api.post(
        "/api/meals", json=dict(date="2026-11-01", itemIds=[1102], label="yes")
    )
    assert response.status_code == 201, response.text
    meal = response.json()["id"]
    os.environ["QDRANT_URL"] = "http://127.0.0.1:1"
    vector.sync_once()
    with session() as db:
        state = db.execute(
            f"SELECT revision,applied,attempts FROM {db.table('outbox')} WHERE entity_id=?",
            ["meal:" + meal],
        )[0]
        assert state[0] > state[1] and state[2] > 0
    assert any(m["id"] == meal for m in api.get("/api/meals").json())
    # A newer mutation must replace the failed event rather than replaying its stale label.
    response = api.put("/api/meals/" + meal, json={"label": "no"})
    assert response.status_code == 200, response.text
    os.environ["QDRANT_URL"] = actual_url
    vector.sync_once()
    saved = next(m for m in api.get("/api/meals").json() if m["id"] == meal)
    assert saved["vectorStatus"] == "synced"
    vector.model.refresh()
    q = qclient()
    try:
        points = q.retrieve(
            vector.model.active["transactions"],
            [vector.point_id("meal", meal)],
            with_payload=True,
        )
        assert (
            len(points) == 1
            and points[0].payload["label"] == "no"
            and points[0].payload["revision"] == 2
        )
    finally:
        q.close()
    print(
        "PASS: SQL survives failed vector write; retry applies latest revision and label; API reports synced"
    )
finally:
    os.environ["QDRANT_URL"] = actual_url
    if meal:
        api.delete("/api/meals/" + meal)
        vector.sync_once()
    api.close()
