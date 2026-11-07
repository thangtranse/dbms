"""Read-only integration checks for recommendation constraints via the FE proxy."""

import json
import os
from urllib.parse import unquote
import httpx


with httpx.Client(
    base_url=os.getenv("API_URL", "http://host.docker.internal:3000"), timeout=90
) as api:
    response = api.get("/api/users")
    response.raise_for_status()
    users = response.json()
    scenarios = 0
    returned = 0
    for user in users:
        headers = {"x-user-id": user["id"]}
        response = api.get("/api/profile", headers=headers)
        response.raise_for_status()
        profile = response.json()["profile"]
        for budget, price_range in [("duoi-35", range(1, 35000)), ("35-50", range(35000, 50001)), ("tren-50", range(50001, 100000001))]:
            for break_time, mood in [(30, "gi-cung-duoc"), (15, "gi-cung-duoc"), (30, "healthy")]:
                context = dict(
                    weather="mat", budget=budget, breakTime=break_time,
                    mood=mood, groupSize=1,
                )
                response = api.post("/api/recommend", headers=headers, json={"context": context})
                response.raise_for_status()
                entries = json.loads(unquote(response.headers["x-ol-queries"]))
                assert any(q["engine"] == "qdrant" and q["durationMs"] >= 0 for q in entries)
                result = response.json()
                scenarios += 1
                for recommendation in result:
                    dish = recommendation["dish"]
                    assert dish["price"] in price_range
                    assert dish["categoryId"] is not None and dish["categoryId"] != 6
                    assert not set(profile["avoid"]) & set(dish["tags"])
                    if profile["diet"] == "chay":
                        assert "chay" in dish["tags"]
                    if profile["diet"] == "it-tinh-bot" or mood == "healthy":
                        assert "healthy" in dish["tags"]
                    if break_time == 15:
                        assert "nhanh" in dish["tags"]
                    score = recommendation["score"]
                    assert score is None or -1.00001 <= score <= 1.00001
                    returned += 1
                if result:
                    excluded = [r["dish"]["itemId"] for r in result]
                    response = api.post(
                        "/api/recommend", headers=headers,
                        json={"context": context, "exclude": excluded},
                    )
                    response.raise_for_status()
                    assert not set(excluded) & {r["dish"]["itemId"] for r in response.json()}
    assert returned > 0, "No positive recommendation case was exercised"
    print(f"PASS: {scenarios} contexts, {returned} recommendations; budget/diet/avoid/tags/exclude and real query traces")
