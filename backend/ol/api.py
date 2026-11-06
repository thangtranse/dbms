from contextlib import closing
import json
import logging
from contextlib import asynccontextmanager
from urllib.parse import quote
import anyio
import httpx
from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from . import service as svc
from .db import session, trace, dumps, close_pool
from .models import DishInput, MealInput, ProfilePatch, Recommend, MealPatch
from .config import qclient
from .vector import model
from .build import BUILD_INFO


@asynccontextmanager
async def lifespan(app):
    anyio.to_thread.current_default_thread_limiter().total_tokens = 4
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="OfficeLunch API", lifespan=lifespan)


@app.exception_handler(ValidationError)
@app.exception_handler(RequestValidationError)
async def validation_error(req, exc):
    return JSONResponse(
        {
            "error": "Dữ liệu không hợp lệ",
            "details": [dict(loc=e["loc"], msg=e["msg"]) for e in exc.errors()],
        },
        status_code=400,
    )


@app.exception_handler(HTTPException)
async def http_error(req, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unavailable(req, exc):
    logging.exception("Request failed")
    return JSONResponse(
        {"error": "Dịch vụ dữ liệu tạm thời không sẵn sàng"}, status_code=503
    )


@app.middleware("http")
async def query_trace(req, call_next):
    entries = []
    token = trace.set(entries)
    try:
        response = await call_next(req)
        # Never truncate encoded JSON mid-character; discard oldest excess entries.
        encoded = quote(dumps(entries), safe="")
        while len(encoded) > 6000 and entries:
            entries.pop()
            encoded = quote(dumps(entries), safe="")
        response.headers["x-ol-queries"] = encoded
        return response
    finally:
        trace.reset(token)


@app.get("/api/health")
@app.get("/api/health/live")
async def live():
    return dict(status="ok", dataMode="database", build=BUILD_INFO)


@app.get("/api/version")
async def version():
    return JSONResponse(BUILD_INFO, headers={"Cache-Control": "no-store"})


@app.get("/api/health/ready")
def ready():
    checks = {}
    try:
        with session() as db:
            checks["teradata"] = bool(
                db.execute(
                    f"SELECT entity_id FROM {db.table('imports')} WHERE entity_id=?",
                    ["food"],
                )
            )
    except Exception:
        checks["teradata"] = False
    try:
        model.refresh()
        checks["model"] = True
    except Exception:
        checks["model"] = False
    try:
        with closing(qclient()) as q:
            checks["qdrant"] = (
                all(
                    q.collection_exists(model.active[k])
                    for k in ["dishes", "transactions"]
                )
                if checks["model"]
                else bool(q.info())
            )
    except Exception:
        checks["qdrant"] = False
    return JSONResponse(
        dict(status="ready" if all(checks.values()) else "not_ready", checks=checks),
        status_code=200 if all(checks.values()) else 503,
    )


@app.get("/api/users")
def users():
    with session() as db:
        return db.docs("users", "ORDER BY entity_id")


@app.get("/api/profile")
def profile(x_user_id: str | None = Header(default=None)):
    with session() as db:
        u = svc.user(db, x_user_id)
        return dict(profile=u, affinity=svc.affinity(db, u))


@app.put("/api/profile")
def update_profile(body: ProfilePatch, x_user_id: str | None = Header(default=None)):
    with session() as db:
        u = svc.user(db, x_user_id)
        patch = body.model_dump(exclude_unset=True)
        if any(v is None for v in patch.values()):
            svc.fail(400, "Trường hồ sơ không được null")
        if "likedItemIds" in patch:
            svc.validate_items(db, patch["likedItemIds"])
        u.update(patch)
        db.execute(
            f"UPDATE {db.table('users')} SET doc=? WHERE entity_id=?",
            [dumps(u), u["id"]],
        )
        return u


@app.get("/api/dishes")
def dishes():
    with session() as db:
        return svc.dishes(db)


@app.post("/api/dishes", status_code=201)
def add_dish(body: DishInput):
    return svc.put_dish(body)


@app.put("/api/dishes/{item_id}")
def edit_dish(item_id: int, body: DishInput):
    return svc.put_dish(body, item_id)


@app.delete("/api/dishes/{item_id}", status_code=204)
def delete_dish(item_id: int):
    svc.delete_dish(item_id)
    return Response(status_code=204)


@app.get("/api/meals")
def meals(x_user_id: str | None = Header(default=None)):
    with session() as db:
        u = svc.user(db, x_user_id)
        return svc.decorate(
            db,
            db.docs(
                "meals", "WHERE user_id=? ORDER BY meal_date DESC,entity_id", [u["id"]]
            ),
            "meal",
        )


@app.post("/api/meals", status_code=201)
def add_meal(body: MealInput, x_user_id: str | None = Header(default=None)):
    return svc.put_meal(body, x_user_id)


@app.put("/api/meals/{meal_id}")
def edit_meal(
    meal_id: str, body: MealPatch, x_user_id: str | None = Header(default=None)
):
    with session() as db:
        u = svc.user(db, x_user_id)
        rows = db.docs("meals", "WHERE entity_id=? AND user_id=?", [meal_id, u["id"]])
        if not rows:
            svc.fail(404, "Không tìm thấy bữa ăn")
        old = {k: rows[0].get(k) for k in ["date", "itemIds", "label", "context"]}
        old.update(body.model_dump(mode="json", exclude_unset=True))
        parsed = MealInput.model_validate(old)
    return svc.put_meal(parsed, x_user_id, meal_id)


@app.delete("/api/meals/{meal_id}", status_code=204)
def delete_meal(meal_id: str, x_user_id: str | None = Header(default=None)):
    svc.delete_meal(meal_id, x_user_id)
    return Response(status_code=204)


@app.get("/api/clusters")
def clusters():
    from pathlib import Path

    categories = json.loads(
        (Path(__file__).parent.parent / "data/demo.json").read_text()
    )["categories"]
    with session() as db:
        docs = svc.dishes(db)
        ids = sorted({d["clusterId"] for d in docs if d["clusterId"] >= 0})
        colors = [
            "#4f7cac",
            "#d9822b",
            "#a37c3c",
            "#b5577a",
            "#4a9a6a",
            "#7d6bc2",
            "#8c8c5a",
        ]
        return dict(
            clusters=[
                dict(
                    id=i,
                    name=f"Cụm {i}",
                    description="KMeans trên vector item; không phải nhóm món thủ công",
                    color=colors[i % 7],
                )
                for i in ids
            ],
            categories=categories,
            dishes=docs,
        )


@app.get("/api/stats")
def stats(x_user_id: str | None = Header(default=None)):
    with session() as db:
        return svc.stats(db, x_user_id)


@app.post("/api/recommend")
def recommend(body: Recommend, x_user_id: str | None = Header(default=None)):
    with session() as db:
        return svc.recommendations(db, x_user_id, body)


@app.get("/api/evaluation")
def evaluation():
    with session() as db:
        rows = db.docs(
            "results", "WHERE result_kind='evaluation' ORDER BY entity_id DESC"
        )
        return (
            max(rows, key=lambda r: r.get("publishedAt", ""))
            if rows
            else dict(status="not_run", results=[])
        )


@app.get("/api/benchmarks")
def benchmarks():
    with session() as db:
        rows = db.docs("results", "WHERE result_kind='benchmark'")
        return sorted(rows, key=lambda r: r.get("publishedAt", ""), reverse=True)


@app.get("/api/benchmarks/{run_id}")
def benchmark(run_id: str):
    with session() as db:
        rows = db.docs(
            "results", "WHERE result_kind='benchmark' AND entity_id=?", [run_id]
        )
        if not rows:
            svc.fail(404, "Chưa có benchmark hoàn tất")
        return rows[0]


@app.get("/api/weather")
def weather(city: str = "hcm"):
    cities = {
        "hcm": ("TP.HCM", 10.82, 106.63),
        "hn": ("Hà Nội", 21.03, 105.85),
        "dn": ("Đà Nẵng", 16.05, 108.2),
    }
    if city not in cities:
        svc.fail(400, "Thành phố không hợp lệ")
    name, lat, lon = cities[city]
    try:
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params=dict(
                latitude=lat,
                longitude=lon,
                current="temperature_2m,precipitation,weather_code",
            ),
            timeout=5,
        )
        r.raise_for_status()
        c = r.json()["current"]
        rainy = c["precipitation"] > 0.2 or c["weather_code"] >= 51
        return dict(
            city=name,
            temperature=round(c["temperature_2m"]),
            description="Mưa" if rainy else "Có mây",
            weather="mua"
            if rainy
            else "nang-nong"
            if c["temperature_2m"] >= 30
            else "mat",
            source="open-meteo",
        )
    except Exception:
        return dict(
            city=name,
            temperature=32,
            description="Không lấy được thời tiết",
            weather="nang-nong",
            source="fallback",
        )
