import hashlib
import json
from collections import Counter
from pathlib import Path
from .db import session, dumps
from .config import FOOD


def load_food(path):
    raw = Path(path).read_bytes()
    records = []
    for number, line in enumerate(raw.decode().splitlines(), 1):
        label, content = line.split("\t")
        ids = list(map(int, content.split()))
        if label not in ("yes", "no") or not ids or min(ids) < 1:
            raise ValueError(f"Invalid food row {number}")
        records.append(dict(id=number, label=label, itemIds=ids, source="food"))
    return hashlib.sha256(raw).hexdigest(), records


def enqueue(db, key, payload):
    found = db.execute(
        f"SELECT revision FROM {db.table('outbox')} WHERE entity_id=?", [key]
    )
    if found:
        db.execute(
            f"UPDATE {db.table('outbox')} SET revision=revision+1, attempts=0, last_error=NULL, doc=? WHERE entity_id=?",
            [dumps(payload), key],
        )
    else:
        db.execute(
            f"INSERT INTO {db.table('outbox')} VALUES (?,1,0,0,NULL,?)",
            [key, dumps(payload)],
        )


def import_food():
    checksum, records = load_food(FOOD)
    demo = json.loads((Path(__file__).parent.parent / "data/demo.json").read_text())
    with session() as db:
        previous = db.execute(
            f"SELECT entity_id FROM {db.table('imports')} WHERE entity_id=?", ["food"]
        )
        if previous:
            manifest = db.docs("imports", "WHERE entity_id=?", ["food"])[0]
            if manifest["checksum"] != checksum:
                raise ValueError(
                    "Different food checksum: use a separate namespaced schema"
                )
            print("Food already imported")
            return
        hashes = db.execute(
            f"SELECT DISTINCT dataset_hash FROM {db.table('research_transactions')}"
        )
        if any(r[0].strip() != checksum for r in hashes):
            raise ValueError("Existing research rows have a different checksum")
        existing_research = {
            int(r[0])
            for r in db.execute(
                f"SELECT entity_id FROM {db.table('research_transactions')}"
            )
        }
        existing_items = {
            (int(r[0]), int(r[1]))
            for r in db.execute(
                f"SELECT entity_id,item_id FROM {db.table('research_items')}"
            )
        }
        existing_dishes = {
            int(r[0]) for r in db.execute(f"SELECT item_id FROM {db.table('dishes')}")
        }
        existing_outbox = {
            r[0] for r in db.execute(f"SELECT entity_id FROM {db.table('outbox')}")
        }
        db.execute(
            f"INSERT INTO {db.table('research_transactions')} VALUES (?,?,?,?)",
            [
                [r["id"], checksum, r["label"], dumps(r)]
                for r in records
                if r["id"] not in existing_research
            ],
            many=True,
        )
        db.execute(
            f"INSERT INTO {db.table('research_items')} VALUES (?,?)",
            [
                [r["id"], i]
                for r in records
                for i in sorted(set(r["itemIds"]))
                if (r["id"], i) not in existing_items
            ],
            many=True,
        )
        seeds = {d["itemId"]: d for d in demo["dishes"]}
        dish_rows = []
        outbox_rows = []
        for i in sorted({i for r in records for i in r["itemIds"]}):
            d = seeds.get(
                i,
                dict(
                    itemId=i,
                    name=f"Item #{i}",
                    categoryId=None,
                    clusterId=-1,
                    price=0,
                    tags=[],
                    image="",
                    x=0,
                    y=0,
                    source="unmapped",
                ),
            )
            d.update(vectorStatus="pending", modelVersion=None)
            dish_rows.append([i, d["price"], d["categoryId"], -1, dumps(d)])
            outbox_rows.append(
                [f"dish:{i}", dumps(dict(kind="dish", id=i, action="upsert"))]
            )
        db.execute(
            f"INSERT INTO {db.table('dishes')} VALUES (?,?,?,?,1,?)",
            [r for r in dish_rows if r[0] not in existing_dishes],
            many=True,
        )
        db.execute(
            f"INSERT INTO {db.table('users')} VALUES (?,?)",
            [[u["id"], dumps(u | {"source": "synthetic"})] for u in demo["users"]],
            many=True,
        )
        meal_rows = []
        item_rows = []
        for m in demo["meals"]:
            m["source"] = "synthetic"
            m["vectorStatus"] = "pending"
            meal_rows.append([m["id"], m["userId"], m["date"], m["label"], dumps(m)])
            item_rows.extend([[m["id"], p, i] for p, i in enumerate(m["itemIds"])])
            outbox_rows.append(
                [
                    "meal:" + m["id"],
                    dumps(dict(kind="meal", id=m["id"], action="upsert")),
                ]
            )
        db.execute(
            f"INSERT INTO {db.table('meals')} VALUES (?,?,?,?,?)", meal_rows, many=True
        )
        db.execute(
            f"INSERT INTO {db.table('meal_items')} VALUES (?,?,?)", item_rows, many=True
        )
        db.execute(
            f"INSERT INTO {db.table('outbox')} VALUES (?,1,0,0,NULL,?)",
            [r for r in outbox_rows if r[0] not in existing_outbox],
            many=True,
        )
        # Association confidence on original transaction item sets (not synthetic UI history).
        singles = Counter()
        pairs = Counter()
        for r in records:
            items = set(r["itemIds"])
            singles.update(items)
            # Only demo-mapped drinks are assigned beverage semantics.
            drinks = {i for i in items if seeds.get(i, {}).get("categoryId") == 6}
            pairs.update((a, b) for a in items for b in drinks if a != b)
        if pairs:
            db.execute(
                f"INSERT INTO {db.table('item_rules')} VALUES (?,?,?,?)",
                [[a, b, n, n / singles[a]] for (a, b), n in pairs.items()],
                many=True,
            )
        db.execute(
            f"INSERT INTO {db.table('imports')} VALUES (?,?)",
            [
                "food",
                dumps(
                    dict(
                        checksum=checksum, transactions=len(records), source="food.txt"
                    )
                ),
            ],
        )
    print(f"Imported {len(records)} research transactions; checksum {checksum}")


def require_dataset(db, checksum):
    rows = db.docs("imports", "WHERE entity_id=?", ["food"])
    if len(rows) != 1 or rows[0]["checksum"] != checksum:
        raise ValueError(
            "Import the matching food dataset into this schema before using the artifact"
        )
