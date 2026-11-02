"""Opt-in real Teradata tests: only own namespace, transaction is rolled back."""

import os
import pytest
from ol.db import connect, DB


@pytest.mark.skipif(
    os.getenv("LIVE_DB_TESTS") != "1", reason="requires sandbox credentials"
)
def test_rollback_keeps_entity_and_outbox_atomic():
    conn = connect()
    db = DB(conn)
    try:
        assert conn.autocommit is False
        key = "test-rollback-only"
        db.execute(f"INSERT INTO {db.table('users')} VALUES (?,?)", [key, "{}"])
        db.execute(
            f"INSERT INTO {db.table('outbox')} VALUES (?,1,0,0,NULL,?)", [key, "{}"]
        )
        conn.rollback()
        assert not db.execute(
            f"SELECT entity_id FROM {db.table('users')} WHERE entity_id=?", [key]
        )
        assert not db.execute(
            f"SELECT entity_id FROM {db.table('outbox')} WHERE entity_id=?", [key]
        )
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.skipif(
    os.getenv("LIVE_DB_TESTS") != "1", reason="requires sandbox credentials"
)
@pytest.mark.parametrize("isolated", [False, True])
def test_real_sql_cosine_matches_numpy(isolated):
    import numpy as np
    from ol.benchmark import sql_neighbors, create_sql_storage

    conn = connect()
    db = DB(conn)
    rng = np.random.default_rng(17)
    a = rng.normal(size=(20, 8)).astype(np.float32)
    q = rng.normal(size=8).astype(np.float32)
    import uuid

    run = "test-cosine-" + uuid.uuid4().hex[:12]
    tables = create_sql_storage(run) if isolated else ("vectors", "benchmark_queries")
    try:
        db.execute(
            f"INSERT INTO {db.table(tables[0])} VALUES (?,?,?,?,?)",
            [
                [run, i, j, float(x), "yes"]
                for i, v in enumerate(a)
                for j, x in enumerate(v)
            ],
            many=True,
        )
        db.execute(
            f"INSERT INTO {db.table(tables[1])} VALUES (?,?,?,?)",
            [[run, 1, j, float(x)] for j, x in enumerate(q)],
            many=True,
        )
        actual = sql_neighbors(db, run, 1, 3, tables)
        reference = (a.astype(np.float64) @ q.astype(np.float64)) / (
            np.linalg.norm(a.astype(np.float64), axis=1)
            * np.linalg.norm(q.astype(np.float64))
        )
        expected = np.argsort(-reference)[:3]
        assert [int(r[0]) for r in actual] == list(expected)
        np.testing.assert_allclose(
            [r[1] for r in actual], reference[expected], atol=1e-6
        )
    finally:
        conn.rollback()
        if isolated:
            for name in tables:
                db.execute(f"DROP TABLE {db.table(name)}")
                conn.commit()
        conn.close()
