"""Black-box check: the supervised worker must synchronize without manual sync."""

import os
import time
from datetime import date
import httpx
from ol.config import qclient
from ol.vector import model, point_id
from ol.db import session


def wait_until(check):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise AssertionError("Supervised worker did not complete within 30 seconds")


with httpx.Client(base_url=os.environ["API_URL"], timeout=30) as api:
    meal = None
    q = qclient()
    try:
        response = api.post("/api/meals", json=dict(date=date.today().isoformat(), itemIds=[1102], label="yes"))
        assert response.status_code == 201, response.text
        meal = response.json()["id"]

        def synced():
            response = api.get("/api/meals")
            response.raise_for_status()
            return any(m["id"] == meal and m["vectorStatus"] == "synced" for m in response.json())

        wait_until(synced)
        model.refresh()
        points = q.retrieve(model.active["transactions"], [point_id("meal", meal)], with_payload=True)
        assert len(points) == 1 and points[0].payload["label"] == "yes" and points[0].payload["revision"] == 1
        response = api.delete("/api/meals/" + meal)
        assert response.status_code == 204, response.text

        def deleted():
            with session() as db:
                state = db.execute(f"SELECT revision,applied FROM {db.table('outbox')} WHERE entity_id=?", ["meal:" + meal])[0]
            return state[0] == state[1] == 2 and not q.retrieve(model.active["transactions"], [point_id("meal", meal)])

        wait_until(deleted)
        print("PASS: supervised worker automatically upserts and deletes; API synced and latest SQL revision acknowledged")
    finally:
        if meal:
            response = api.delete("/api/meals/" + meal)
            assert response.status_code in (204, 404), response.text
        q.close()
