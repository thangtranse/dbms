"""Explicit integration smoke against the running local API; cleans up its own rows."""

import os
import secrets
import httpx

base = os.getenv("API_URL", "http://localhost:3000")
client = httpx.Client(base_url=base, timeout=90)
i = 1900000000 + secrets.randbelow(100000000)
created = False
meal = None
try:
    r = client.post(
        "/api/dishes",
        json=dict(
            itemId=i,
            name="Integration smoke only",
            price=25000,
            categoryId=3,
            tags=["nhanh"],
            image="",
        ),
    )
    assert r.status_code == 201, r.text
    created = True
    assert r.json()["vectorStatus"] == "pending"
    assert (
        client.post(
            "/api/dishes", json=dict(itemId=i, name="Duplicate", price=1)
        ).status_code
        == 409
    )
    r = client.post(
        "/api/meals", json=dict(date="2026-11-01", itemIds=[i], label="yes")
    )
    assert r.status_code == 201, r.text
    meal = r.json()["id"]
    assert client.put("/api/meals/" + meal, json={"label": "no"}).status_code == 200
    assert client.delete("/api/dishes/" + str(i)).status_code == 409
    assert client.get("/api/meals", headers={"x-user-id": "u-002"}).status_code == 200
    assert (
        client.delete("/api/meals/" + meal, headers={"x-user-id": "u-002"}).status_code
        == 404
    )
    assert any(
        m["id"] == meal and m["label"] == "no" for m in client.get("/api/meals").json()
    )
    print(
        "PASS: real CRUD, duplicate conflict, ownership, partial update, SQL persistence, pending vector"
    )
finally:
    if meal:
        client.delete("/api/meals/" + meal)
    if created:
        client.delete("/api/dishes/" + str(i))
    client.close()
