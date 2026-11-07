import json
from contextlib import contextmanager
import numpy as np
from ol import vector


class FakeDB:
    def __init__(self):
        self.revision = 1
        self.applied = 0
        self.attempts = 0
        self.deleted = False

    def table(self, name):
        return name

    def docs(self, *args):
        return [] if self.deleted else [dict(itemId=1, price=10, tags=[], categoryId=0)]

    def execute(self, sql, params=None):
        if sql.startswith("SELECT TOP"):
            return (
                [
                    (
                        "dish:1",
                        self.revision,
                        json.dumps(dict(kind="dish", id=1, action="upsert")),
                    )
                ]
                if self.revision > self.applied
                else []
            )
        if "applied=?" in sql and params[2] == self.revision:
            self.applied = params[0]
        if "attempts=attempts+1" in sql:
            self.attempts += 1
        return []


def setup(monkeypatch, db, client):
    @contextmanager
    def session():
        yield db

    @contextmanager
    def lock():
        yield

    class Model:
        version = "test"
        active = {"dishes": "officelunch_test", "transactions": "officelunch_test_tx"}
        items = {1: {"vector": np.array([1.0, 0.0])}}

        def refresh(self):
            return self

    client.close = lambda: None
    monkeypatch.setattr(vector, "session", session)
    monkeypatch.setattr(vector, "worker_lock", lock)
    monkeypatch.setattr(vector, "model", Model())
    monkeypatch.setattr(vector, "qclient", lambda: client)


def test_failure_retries_and_ack_is_conditional_on_revision(monkeypatch):
    db = FakeDB()

    class Client:
        fail = True

        def upsert(self, *args, **kwargs):
            if self.fail:
                raise RuntimeError("offline")
            db.revision += 1  # concurrent API update while sending snapshot

    client = Client()
    setup(monkeypatch, db, client)
    assert vector.sync_once() == 0
    assert db.applied == 0 and db.attempts == 1
    client.fail = False
    assert vector.sync_once() == 1
    assert db.applied == 0  # stale completion cannot acknowledge newer revision
    client.upsert = lambda *a, **k: None
    assert vector.sync_once() == 1
    assert db.applied == db.revision
    assert vector.sync_once() == 0


def test_delete_tombstone_is_applied(monkeypatch):
    db = FakeDB()
    db.deleted = True

    class Client:
        called = False

        def delete(self, *args, **kwargs):
            self.called = True

    client = Client()
    setup(monkeypatch, db, client)
    assert vector.sync_once() == 1 and client.called and db.applied == 1


def test_new_dish_vector_uses_trained_neighbors_and_matching_tags():
    items = {
        1: {"vector": np.array([1.0, 0.0])},
        2: {"vector": np.array([0.0, 1.0])},
        3: {"vector": np.array([-1.0, 0.0])},
    }
    catalog = [
        dict(itemId=1, categoryId=0, tags=["Nóng"]),
        dict(itemId=2, categoryId=0, tags=["lạnh"]),
        dict(itemId=3, categoryId=1, tags=["nóng"]),
    ]
    dish = dict(itemId=4, categoryId=0, tags=["nóng"])
    expected = np.array([2.0, 1.0]) / np.sqrt(5)
    np.testing.assert_allclose(vector.dish_vector(items, dish, catalog), expected)
    assert vector.dish_vector(items, {**dish, "categoryId": 6}, catalog) is None
