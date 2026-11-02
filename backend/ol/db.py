"""Short transactions; query logs contain SQL templates only, never parameter values."""

import contextvars
import json
import os
import time
import queue
from contextlib import contextmanager
import teradatasql
from .config import SCHEMA

trace = contextvars.ContextVar("trace", default=None)


def connect():
    conn = teradatasql.connect(
        host=os.environ["TERADATA_HOST"],
        user=os.environ["TERADATA_USER"],
        password=os.environ["TERADATA_PASSWORD"],
        logmech=os.getenv("TERADATA_LOGMECH", "TD2"),
        encryptdata=os.getenv("TERADATA_ENCRYPTDATA", "true"),
        logon_timeout=os.getenv("TERADATA_LOGON_TIMEOUT", "10"),
        tmode="ANSI",
    )
    conn.autocommit = False
    return conn


class DB:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None, many=False):
        if many and not params:
            return []
        started = time.perf_counter()
        with self.conn.cursor() as c:
            if many:
                try:
                    c.executemany(sql, params)
                except teradatasql.Error as exc:
                    # Retrieve server diagnostics before rollback clears the batch error.
                    c.execute("{fn teradata_nativesql}{fn teradata_get_errors}" + sql)
                    detail = c.fetchone()
                    raise RuntimeError(
                        f"Teradata batch failed: {str(detail)[:2000]}"
                    ) from exc
            else:
                c.execute(sql, params)
            rows = c.fetchall() if c.description else []
            count = (
                len(rows)
                if c.description
                else (c.rowcount if c.rowcount >= 0 else None)
            )
        entries = trace.get()
        if entries is not None and len(entries) < 12:
            entries.append(
                dict(
                    engine="teradata",
                    title="SQL thực thi",
                    text=sql,
                    durationMs=round((time.perf_counter() - started) * 1000, 3),
                )
            )
            if count is not None:
                entries[-1]["rows"] = count
        return rows

    def table(self, name):
        return f"{SCHEMA}.{name}"

    def docs(self, table, where="", params=None):
        return [
            json.loads(r[0])
            for r in self.execute(
                f"SELECT doc FROM {self.table(table)} {where}", params
            )
        ]


_pool = queue.LifoQueue(maxsize=4)


@contextmanager
def session():
    try:
        conn = _pool.get_nowait()
    except queue.Empty:
        conn = connect()
    healthy = True
    try:
        yield DB(conn)
        conn.commit()
    except BaseException:
        healthy = False
        conn.rollback()
        raise
    finally:
        if healthy:
            try:
                _pool.put_nowait(conn)
            except queue.Full:
                conn.close()
        else:
            conn.close()


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def close_pool():
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            break
        conn.close()
