"""Read-only fingerprints around a manual VM restart. Stop API/worker first."""

import hashlib
import json
import sys
from ol.config import ARTIFACTS
from ol.db import session
from ol.schema import TABLES
from ol.pipeline import write_json

phase = sys.argv[1]
assert phase in ("before", "after")
summary = {}
with session() as db:
    for table in TABLES:
        rows = db.execute(f"SELECT * FROM {db.table(table)}")
        encoded = sorted(json.dumps(row, ensure_ascii=False, default=str) for row in rows)
        digest = hashlib.sha256()
        for row in encoded:
            digest.update(row.encode())
            digest.update(b"\n")
        summary[table] = dict(rows=len(rows), sha256=digest.hexdigest())
if phase == "after":
    previous = json.loads((ARTIFACTS / "database-restart-before.json").read_text())
    changed = [name for name in TABLES if summary[name] != previous[name]]
    assert not changed, f"Database content changed during restart: {changed}"
write_json(ARTIFACTS / f"database-restart-{phase}.json", summary)
print(json.dumps({name: value["rows"] for name, value in summary.items()}))
print("PASS: database fingerprints " + ("recorded" if phase == "before" else "match across VM restart"))
