from contextlib import closing
import time
import uuid
from datetime import date, timedelta
import numpy as np
from fastapi import HTTPException
from qdrant_client import models as qm
from .db import session, dumps
from .ingest import enqueue
from .config import qclient
from .vector import dish_vector, model, qlog


def fail(code, message):
    raise HTTPException(code, message)


def user(db, user_id):
    rows = db.docs("users", "WHERE entity_id=?", [user_id or "u-001"])
    if not rows:
        fail(404, "Không tìm thấy người dùng")
    return rows[0]


def decorate(db, docs, kind):
    # One SQL query for synchronization state instead of N+1 queries.
    states = {
        r[0]: (int(r[1]), int(r[2]))
        for r in db.execute(
            f"SELECT entity_id,revision,applied FROM {db.table('outbox')}"
        )
    }
    for d in docs:
        key = f"{kind}:{d['itemId'] if kind == 'dish' else d['id']}"
        rev, applied = states.get(key, (1, 0))
        d["vectorStatus"] = "synced" if applied == rev else "pending"
    return docs


def dishes(db):
    return decorate(
        db, db.docs("dishes", "WHERE active_flag=1 ORDER BY item_id"), "dish"
    )


def validate_items(db, ids):
    known = {
        r[0]
        for r in db.execute(
            f"SELECT item_id FROM {db.table('dishes')} WHERE active_flag=1"
        )
    }
    if not set(ids) <= known:
        fail(400, "Có mã món không tồn tại")


def put_dish(body, item_id=None):
    d = body.model_dump()
    i = d["itemId"]
    if item_id is not None and item_id != i:
        fail(400, "Không được thay đổi itemId")
    with session() as db:
        existing = db.docs("dishes", "WHERE item_id=?", [i])
        if item_id is None and existing:
            fail(409, "Mã món đã tồn tại")
        if item_id is not None and (not existing or existing[0].get("deleted")):
            fail(404, "Không tìm thấy món")
        old = existing[0] if existing else {}
        d.update(
            clusterId=old.get("clusterId", -1),
            x=old.get("x", 0),
            y=old.get("y", 0),
            source="synthetic",
            vectorStatus="pending",
            modelVersion=old.get("modelVersion"),
        )
        if existing:
            db.execute(
                f"UPDATE {db.table('dishes')} SET price=?,category_id=?,doc=? WHERE item_id=?",
                [d["price"], d["categoryId"], dumps(d), i],
            )
        else:
            db.execute(
                f"INSERT INTO {db.table('dishes')} VALUES (?,?,?,-1,1,?)",
                [i, d["price"], d["categoryId"], dumps(d)],
            )
        enqueue(db, f"dish:{i}", dict(kind="dish", id=i, action="upsert"))
    return d


def delete_dish(i):
    with session() as db:
        existing = db.docs("dishes", "WHERE item_id=? AND active_flag=1", [i])
        if not existing:
            fail(404, "Không tìm thấy món")
        count = db.execute(
            f"SELECT COUNT(*) FROM {db.table('meal_items')} WHERE item_id=?", [i]
        )[0][0]
        if count:
            fail(409, "Món đang có trong lịch sử bữa ăn")
        d = existing[0]
        d["deleted"] = True
        db.execute(
            f"UPDATE {db.table('dishes')} SET active_flag=0,doc=? WHERE item_id=?",
            [dumps(d), i],
        )
        enqueue(db, f"dish:{i}", dict(kind="dish", id=i, action="delete"))


def put_meal(body, user_id, meal_id=None):
    with session() as db:
        u = user(db, user_id)
        validate_items(db, body.itemIds)
        if meal_id is not None:
            old = db.docs(
                "meals", "WHERE entity_id=? AND user_id=?", [meal_id, u["id"]]
            )
            if not old:
                fail(404, "Không tìm thấy bữa ăn")
        i = meal_id or str(uuid.uuid4())
        d = body.model_dump(mode="json")
        d.update(id=i, userId=u["id"], source="app", vectorStatus="pending")
        if meal_id:
            db.execute(
                f"UPDATE {db.table('meals')} SET meal_date=?,label=?,doc=? WHERE entity_id=?",
                [d["date"], d["label"], dumps(d), i],
            )
            db.execute(f"DELETE FROM {db.table('meal_items')} WHERE entity_id=?", [i])
        else:
            db.execute(
                f"INSERT INTO {db.table('meals')} VALUES (?,?,?,?,?)",
                [i, u["id"], d["date"], d["label"], dumps(d)],
            )
        db.execute(
            f"INSERT INTO {db.table('meal_items')} VALUES (?,?,?)",
            [[i, p, item] for p, item in enumerate(d["itemIds"])],
            many=True,
        )
        enqueue(db, "meal:" + i, dict(kind="meal", id=i, action="upsert"))
    return d


def delete_meal(i, user_id):
    with session() as db:
        u = user(db, user_id)
        if not db.docs("meals", "WHERE entity_id=? AND user_id=?", [i, u["id"]]):
            fail(404, "Không tìm thấy bữa ăn")
        db.execute(f"DELETE FROM {db.table('meal_items')} WHERE entity_id=?", [i])
        db.execute(f"DELETE FROM {db.table('meals')} WHERE entity_id=?", [i])
        enqueue(db, "meal:" + i, dict(kind="meal", id=i, action="delete"))


def affinity(db, u):
    rows = db.execute(
        f"""SELECT d.cluster_id, SUM(CASE WHEN m.label='yes' THEN 1 ELSE -1 END)
        FROM {db.table("meals")} m JOIN {db.table("meal_items")} mi ON m.entity_id=mi.entity_id
        JOIN {db.table("dishes")} d ON mi.item_id=d.item_id WHERE m.user_id=? AND d.cluster_id>=0 GROUP BY 1""",
        [u["id"]],
    )
    result = {str(int(k)): int(v) for k, v in rows}
    lookup = {
        int(i): int(c)
        for i, c in db.execute(
            f"SELECT item_id,cluster_id FROM {db.table('dishes')} WHERE active_flag=1 AND cluster_id>=0"
        )
    }
    for i in u["likedItemIds"]:
        if i in lookup:
            k = str(lookup[i])
            result[k] = result.get(k, 0) + 2
    return result


def stats(db, uid):
    u = user(db, uid)
    catalog = {d["itemId"]: d for d in dishes(db)}
    n, rate = db.execute(
        f"SELECT COUNT(*),AVG(CASE WHEN label='yes' THEN 1.0 ELSE 0 END) FROM {db.table('meals')} WHERE user_id=?",
        [u["id"]],
    )[0]
    rows = db.execute(
        f"""SELECT m.meal_date,SUM(d.price) FROM {db.table("meals")} m
        JOIN {db.table("meal_items")} mi ON m.entity_id=mi.entity_id JOIN {db.table("dishes")} d ON d.item_id=mi.item_id
        WHERE m.user_id=? GROUP BY 1 ORDER BY 1""",
        [u["id"]],
    )
    weeks = {}
    for day, amount in rows:
        day = date.fromisoformat(str(day))
        week = str(day - timedelta(days=day.weekday()))
        weeks[week] = weeks.get(week, 0) + int(amount)
    top = db.execute(
        f"""SELECT TOP 6 mi.item_id,COUNT(*) AS cnt FROM {db.table("meals")} m
        JOIN {db.table("meal_items")} mi ON m.entity_id=mi.entity_id JOIN {db.table("dishes")} d ON mi.item_id=d.item_id
        WHERE m.user_id=? AND (d.category_id IS NULL OR d.category_id<>6) GROUP BY 1 ORDER BY cnt DESC,mi.item_id""",
        [u["id"]],
    )
    top = [
        dict(dish=catalog[int(i)], count=int(c)) for i, c in top if int(i) in catalog
    ]
    clusters = db.execute(
        f"""SELECT x.cluster_id,SUM(CASE WHEN x.label='yes' THEN 1 ELSE 0 END),SUM(CASE WHEN x.label='no' THEN 1 ELSE 0 END)
        FROM (SELECT DISTINCT d.cluster_id,m.entity_id,m.label FROM {db.table("meals")} m JOIN {db.table("meal_items")} mi ON m.entity_id=mi.entity_id
        JOIN {db.table("dishes")} d ON mi.item_id=d.item_id WHERE m.user_id=? AND d.cluster_id>=0) x GROUP BY 1""",
        [u["id"]],
    )
    today = date.today()
    week = str(today - timedelta(days=today.weekday()))
    return dict(
        totalMeals=int(n),
        yesRate=float(rate or 0),
        spendThisWeek=weeks.get(week, 0),
        favorite=top[0] if top else None,
        weeklySpend=[dict(week=w, amount=weeks[w]) for w in sorted(weeks)[-8:]],
        topDishes=top,
        clusterYes=[
            dict(clusterId=int(c), yes=int(y), no=int(n)) for c, y, n in clusters
        ],
    )


def recommendations(db, uid, body):
    model.refresh()
    with closing(qclient()) as q:
        return _recommendations(db, uid, body, q)


def _recommendations(db, uid, body, q):
    u = user(db, uid)
    members = [u] + [user(db, i) for i in dict.fromkeys(body.members) if i != u["id"]]
    catalog = {d["itemId"]: d for d in dishes(db)}
    positives = []
    negatives = []
    for member in members:
        positives.extend(member["likedItemIds"])
        history = db.docs(
            "meals", "WHERE user_id=? ORDER BY meal_date DESC", [member["id"]]
        )[:20]
        for meal in history:
            (positives if meal["label"] == "yes" else negatives).extend(meal["itemIds"])

    def preference_vector(item_id):
        if item_id in model.items:
            return model.items[item_id]["vector"]
        dish = catalog.get(item_id)
        if dish and dish["vectorStatus"] == "synced":
            return dish_vector(model.items, dish, catalog.values())
        return None

    vectors = [
        vector
        for i in positives
        if catalog.get(i, {}).get("categoryId") != 6
        if (vector := preference_vector(i)) is not None
    ]
    neg = [vector for i in negatives if (vector := preference_vector(i)) is not None]
    query = np.mean(vectors, axis=0) if vectors else None
    if query is not None and neg:
        query = query - 0.25 * np.mean(neg, axis=0)
    ctx = body.context
    must = [
        qm.FieldCondition(key="active", match=qm.MatchValue(value=True)),
        qm.FieldCondition(key="modelVersion", match=qm.MatchValue(value=model.version)),
    ]
    must.append(qm.FieldCondition(key="mapped", match=qm.MatchValue(value=True)))
    must_not = [qm.FieldCondition(key="categoryId", match=qm.MatchValue(value=6))]
    if body.exclude:
        must_not.append(qm.HasIdCondition(has_id=body.exclude))
    min_price, max_price = {
        "duoi-35": (1, 34999),
        "35-50": (35000, 50000),
        "tren-50": (50001, None),
    }[ctx.budget]
    must.append(
        qm.FieldCondition(key="price", range=qm.Range(gte=min_price, lte=max_price))
    )
    avoid = list({a for m in members for a in m["avoid"]})
    if avoid:
        must_not.append(qm.FieldCondition(key="tags", match=qm.MatchAny(any=avoid)))
    tags = []
    if any(m["diet"] == "chay" for m in members):
        tags.append("chay")
    if any(m["diet"] == "it-tinh-bot" for m in members):
        tags.append("healthy")
    if ctx.breakTime == 15:
        tags.append("nhanh")
    if ctx.mood in ("an-nhe", "no-bung", "healthy"):
        tags.append(
            {"an-nhe": "nhẹ", "no-bung": "no-lau", "healthy": "healthy"}[ctx.mood]
        )
    for tag in tags:
        must.append(qm.FieldCondition(key="tags", match=qm.MatchValue(value=tag)))
    filt = qm.Filter(must=must, must_not=must_not)
    t = time.perf_counter()
    if query is None or not np.linalg.norm(query):
        counts = db.execute(
            f"SELECT item_id,COUNT(*) AS cnt FROM {db.table('research_items')} GROUP BY 1 ORDER BY cnt DESC,item_id"
        )
        t = time.perf_counter()
        points = q.scroll(
            model.active["dishes"], scroll_filter=filt, limit=2000, with_payload=True
        )[0]
        allowed = {int(p.id) for p in points}
        popular = [int(i) for i, _ in counts if i in allowed]
        ordered = popular + sorted(allowed.difference(popular))
        ranked = [(i, None) for i in ordered[: body.limit]]
    else:
        query = query / np.linalg.norm(query)
        t = time.perf_counter()
        points = q.query_points(
            model.active["dishes"],
            query=query.tolist(),
            query_filter=filt,
            limit=body.limit * 4,
            with_payload=True,
        ).points
        # Weather is a secondary preference; cosine remains the reported similarity.
        preferred = "lạnh" if ctx.weather == "nang-nong" else "nóng"
        points.sort(
            key=lambda p: (
                float(p.score)
                + (
                    0.03
                    if preferred in catalog.get(int(p.id), {}).get("tags", [])
                    else 0
                )
            ),
            reverse=True,
        )
        ranked = [(int(p.id), float(p.score)) for p in points][: body.limit]
    qlog(
        "Tìm món",
        dict(
            collection=model.active["dishes"],
            filter=filt.model_dump(exclude_none=True),
            operation="query_points" if query is not None else "scroll",
            limit=body.limit * 4 if query is not None else 2000,
            with_payload=True,
            query="<profile vector redacted>" if query is not None else None,
        ),
        t,
        len(points),
    )
    result = []
    for i, score in ranked:
        dish = catalog.get(i)
        if not dish or dish["categoryId"] is None:
            continue
        # Revalidate against authoritative SQL metadata while outbox may be pending.
        if (
            dish["price"] < min_price
            or (max_price is not None and dish["price"] > max_price)
            or set(dish["tags"]) & set(avoid)
            or not set(tags) <= set(dish["tags"])
            or dish["categoryId"] == 6
        ):
            continue
        vector = preference_vector(i)
        if vector is None:
            continue
        t = time.perf_counter()
        near = q.query_points(
            model.active["transactions"],
            query=vector.tolist(),
            limit=15,
            with_payload=True,
        ).points
        votes = [p.payload["label"] for p in near]
        predicted = "yes" if votes.count("yes") > votes.count("no") else "no"
        qlog(
            "kNN yes/no",
            dict(collection=model.active["transactions"], limit=15),
            t,
            len(near),
        )
        rules = db.execute(
            f"""SELECT TOP 1 r.consequent,r.confidence FROM {db.table("item_rules")} r JOIN {db.table("dishes")} d ON r.consequent=d.item_id
            WHERE r.antecedent=? AND d.category_id=6 AND d.active_flag=1 ORDER BY r.confidence DESC,r.consequent""",
            [i],
        )
        drink = None
        if rules and rules[0][0] in catalog:
            candidate = catalog[rules[0][0]]
            if not set(candidate["tags"]) & set(avoid):
                drink = dict(dish=candidate, confidence=float(rules[0][1]))
        result.append(
            dict(
                dish=dish,
                score=score,
                reason="Món phổ biến (cold start)"
                if score is None
                else "Tương đồng vector khẩu vị; metadata món là dữ liệu demo",
                predictedLabel=predicted,
                drink=drink,
            )
        )
    return result
