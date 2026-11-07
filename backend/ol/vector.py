import json
import threading
import time
import uuid
from contextlib import contextmanager, closing
from qdrant_client import models as qm
import numpy as np
from .config import ARTIFACTS, PREFIX, qclient
from .db import session, dumps, trace

INFERENCE_LOCK = threading.Lock()


def point_id(kind, entity_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"officelunch:{kind}:{entity_id}"))


def qlog(title, text, started, rows):
    entries = trace.get()
    if entries is not None and len(entries) < 12:
        entries.append(
            dict(
                engine="qdrant",
                title=title,
                text=json.dumps(text),
                durationMs=round((time.perf_counter() - started) * 1000, 3),
                rows=rows,
            )
        )


@contextmanager
def worker_lock():
    import fcntl

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with (ARTIFACTS / "worker.lock").open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


class Model:
    def __init__(self):
        self.version = None

    def refresh(self):
        active = json.loads((ARTIFACTS / "active.json").read_text())
        if active["modelVersion"] == self.version:
            return self
        from gensim.models import Doc2Vec
        from .numerics import check_blas

        check_blas()

        folder = ARTIFACTS / active["runId"] / f"seed-{active['seed']}"
        self.doc = Doc2Vec.load(str(folder / "joi.model"))
        self.patterns = json.loads((folder / "patterns.json").read_text())
        a = np.load(folder / "items.npz")
        self.items = {
            int(i): dict(vector=v, clusterId=int(c), x=float(xy[0]), y=float(xy[1]))
            for i, v, c, xy in zip(a["ids"], a["vectors"], a["clusters"], a["xy"])
        }
        self.version = active["modelVersion"]
        self.active = active
        return self

    def infer(self, items):
        from .pipeline import infer, normalize, tokens, stable_seed

        words = [f"i:{i}" for i in items] + tokens(items, self.patterns)
        with INFERENCE_LOCK:
            return normalize(
                infer(self.doc, words, stable_seed(sorted(items)), self.doc.epochs)
            )


model = Model()


def dish_vector(items, dish, catalog):
    trained = items.get(dish["itemId"])
    if trained is not None:
        return trained["vector"]

    tags = {tag.casefold() for tag in dish["tags"]}
    neighbors = []
    weights = []
    for candidate in catalog:
        if candidate["categoryId"] != dish["categoryId"]:
            continue
        trained = items.get(candidate["itemId"])
        if trained is None or not np.linalg.norm(trained["vector"]):
            continue
        overlap = tags.intersection(tag.casefold() for tag in candidate["tags"])
        neighbors.append(trained["vector"])
        weights.append(1 + len(overlap))
    if not neighbors:
        return None
    vector = np.average(neighbors, axis=0, weights=weights)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else None


def activate(run_id, seed=0):
    from .pipeline import write_json

    folder = ARTIFACTS / run_id / f"seed-{seed}"
    manifest = json.loads((ARTIFACTS / run_id / "manifest.json").read_text())
    if manifest["status"] != "complete":
        raise ValueError("Training incomplete")
    from .ingest import require_dataset

    with session() as db:
        require_dataset(db, manifest["datasetHash"])
    active = dict(runId=run_id, seed=seed, modelVersion=f"{run_id}-s{seed}")
    # Physical collections are versioned: incomplete activation cannot replace serving model.
    suffix = uuid.uuid5(uuid.NAMESPACE_URL, active["modelVersion"]).hex[:12]
    active.update(
        dishes=f"{PREFIX}_dishes_{suffix}",
        transactions=f"{PREFIX}_transactions_{suffix}",
    )
    with worker_lock(), closing(qclient()) as q:
        arrays = np.load(folder / "items.npz")
        corpus = np.load(folder / "vectors.npz")
        for name in [active["dishes"], active["transactions"]]:
            if not q.collection_exists(name):
                q.create_collection(
                    name,
                    vectors_config=qm.VectorParams(
                        size=manifest["dimension"], distance=qm.Distance.COSINE
                    ),
                    hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=100),
                )
        for key, kind in [
            ("categoryId", "integer"),
            ("price", "integer"),
            ("active", "bool"),
            ("mapped", "bool"),
            ("tags", "keyword"),
            ("modelVersion", "keyword"),
        ]:
            q.create_payload_index(active["dishes"], key, field_schema=kind, wait=True)
        with session() as db:
            docs = {d["itemId"]: d for d in db.docs("dishes", "WHERE active_flag=1")}
            points = []
            for i, v, c, xy in zip(
                arrays["ids"], arrays["vectors"], arrays["clusters"], arrays["xy"]
            ):
                i = int(i)
                d = docs.get(i)
                if not d:
                    continue
                payload = dict(
                    itemId=i,
                    categoryId=d["categoryId"],
                    price=d["price"],
                    tags=d["tags"],
                    active=True,
                    mapped=d["categoryId"] is not None,
                    modelVersion=active["modelVersion"],
                )
                points.append(qm.PointStruct(id=i, vector=v.tolist(), payload=payload))
                d.update(
                    clusterId=int(c),
                    x=float(xy[0]),
                    y=float(xy[1]),
                    modelVersion=active["modelVersion"],
                )
                db.execute(
                    f"UPDATE {db.table('dishes')} SET cluster_id=?, doc=? WHERE item_id=?",
                    [int(c), dumps(d), i],
                )
            for start in range(0, len(points), 128):
                q.upsert(active["dishes"], points[start : start + 128], wait=True)
            for start in range(0, len(corpus["train"]), 128):
                q.upsert(
                    active["transactions"],
                    [
                        qm.PointStruct(
                            id=int(i),
                            vector=v.tolist(),
                            payload=dict(
                                label=str(label),
                                source="food",
                                modelVersion=active["modelVersion"],
                            ),
                        )
                        for i, v, label in zip(
                            corpus["trainIds"][start : start + 128],
                            corpus["train"][start : start + 128],
                            corpus["trainLabels"][start : start + 128],
                        )
                    ],
                    wait=True,
                )
            from .ingest import enqueue

            known = {int(i) for i in arrays["ids"]}
            for item_id, dish in docs.items():
                if item_id not in known:
                    dish.update(
                        clusterId=-1,
                        x=0,
                        y=0,
                        modelVersion=None,
                        vectorStatus="pending",
                    )
                    db.execute(
                        f"UPDATE {db.table('dishes')} SET cluster_id=-1,doc=? WHERE item_id=?",
                        [dumps(dish), item_id],
                    )
                enqueue(
                    db,
                    f"dish:{item_id}",
                    dict(kind="dish", id=item_id, action="upsert"),
                )
            for r in db.execute(f"SELECT entity_id FROM {db.table('meals')}"):
                enqueue(db, "meal:" + r[0], dict(kind="meal", id=r[0], action="upsert"))
            save_result(db, run_id, "evaluation", manifest)
        write_json(ARTIFACTS / "active.json", active)
    print("Activated", active["modelVersion"])


def save_result(db, run_id, kind, result):
    from .ingest import require_dataset

    require_dataset(db, result["datasetHash"])
    # Large raw results stay in immutable artifact; API stores compact summaries only.
    if kind == "evaluation":
        result = {k: v for k, v in result.items() if k != "results"} | {
            "results": result["results"]
        }
    from datetime import datetime, timezone

    result = result | {"publishedAt": datetime.now(timezone.utc).isoformat()}
    annotation_path = ARTIFACTS / run_id / "annotations.json"
    if annotation_path.exists():
        result = result | {"annotations": json.loads(annotation_path.read_text())}
    text = dumps(result)
    if len(text.encode("utf-16-le")) > 58000:
        raise ValueError("Result summary too large")
    db.execute(f"DELETE FROM {db.table('results')} WHERE entity_id=?", [run_id])
    db.execute(
        f"INSERT INTO {db.table('results')} VALUES (?,?,?)", [run_id, kind, text]
    )


def sync_once():
    completed = 0
    with worker_lock(), closing(qclient()) as q:
        model.refresh()
        with session() as db:
            events = db.execute(
                f"SELECT TOP 100 entity_id,revision,doc FROM {db.table('outbox')} WHERE revision>applied ORDER BY attempts,entity_id"
            )
        for key, revision, raw in events:
            try:
                event = json.loads(raw)
                kind = event["kind"]
                entity_id = event["id"]
                collection = model.active[
                    "dishes" if kind == "dish" else "transactions"
                ]
                pid = entity_id if kind == "dish" else point_id(kind, entity_id)
                with session() as db:
                    # Read the current entity, never an obsolete body from the event.
                    docs = (
                        db.docs(
                            "dishes", "WHERE item_id=? AND active_flag=1", [entity_id]
                        )
                        if kind == "dish"
                        else db.docs("meals", "WHERE entity_id=?", [entity_id])
                    )
                if not docs:
                    q.delete(collection, qm.PointIdsList(points=[pid]), wait=True)
                else:
                    doc = docs[0]
                    if kind == "dish":
                        references = []
                        if entity_id not in model.items:
                            with session() as db:
                                references = db.docs(
                                    "dishes", "WHERE active_flag=1 AND category_id=? ORDER BY item_id",
                                    [doc["categoryId"]],
                                )
                        vector = dish_vector(model.items, doc, references)
                    else:
                        vector = model.infer(doc["itemIds"])
                    if vector is None or not np.linalg.norm(vector):
                        # Keep pending when the model has no usable reference.
                        with session() as db:
                            db.execute(
                                f"UPDATE {db.table('outbox')} SET attempts=attempts+1 WHERE entity_id=? AND revision=?",
                                [key, revision],
                            )
                        continue
                    payload = dict(
                        modelVersion=model.version,
                        revision=int(revision),
                        source=doc.get("source", "app"),
                    )
                    if kind == "dish":
                        payload.update(
                            itemId=entity_id,
                            price=doc["price"],
                            tags=doc["tags"],
                            categoryId=doc["categoryId"],
                            active=True,
                            mapped=doc["categoryId"] is not None and doc["price"] > 0,
                        )
                    else:
                        payload.update(label=doc["label"], userId=doc["userId"])
                    q.upsert(
                        collection,
                        [
                            qm.PointStruct(
                                id=pid, vector=vector.tolist(), payload=payload
                            )
                        ],
                        wait=True,
                    )
                with session() as db:
                    db.execute(
                        f"UPDATE {db.table('outbox')} SET applied=?, attempts=0, last_error=NULL WHERE entity_id=? AND revision=?",
                        [revision, key, revision],
                    )
                completed += 1
            except Exception:
                with session() as db:
                    db.execute(
                        f"UPDATE {db.table('outbox')} SET attempts=attempts+1,last_error=? WHERE entity_id=? AND revision=?",
                        [
                            "Vector synchronization failed; inspect worker logs",
                            key,
                            revision,
                        ],
                    )
                import logging

                logging.exception("Outbox event failed: %s", key)
    return completed


def publish(run_id):
    """Retry publishing completed artifacts without rerunning training/measurement."""
    manifest = json.loads((ARTIFACTS / run_id / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("runId") != run_id:
        raise ValueError("Only matching completed manifests may be published")
    kind = "benchmark" if "summaries" in manifest else "evaluation"
    with session() as db:
        imports = db.docs("imports", "WHERE entity_id=?", ["food"])
        if imports and imports[0]["checksum"] != manifest["datasetHash"]:
            raise ValueError("Artifact dataset differs from current imported food")
        save_result(db, run_id, kind, manifest)
    print("Published", run_id)
