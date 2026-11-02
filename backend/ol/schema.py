from .db import connect, DB
from .config import SCHEMA

TABLES = {
    "users": "entity_id VARCHAR(64) NOT NULL, doc VARCHAR(16000) CHARACTER SET UNICODE",
    "dishes": "item_id INTEGER NOT NULL, price INTEGER, category_id INTEGER, cluster_id INTEGER, active_flag BYTEINT, doc VARCHAR(16000) CHARACTER SET UNICODE",
    "meals": "entity_id VARCHAR(64) NOT NULL, user_id VARCHAR(64), meal_date DATE, label VARCHAR(3), doc VARCHAR(16000) CHARACTER SET UNICODE",
    "meal_items": "entity_id VARCHAR(64) NOT NULL, position_id INTEGER NOT NULL, item_id INTEGER",
    "research_transactions": "entity_id INTEGER NOT NULL, dataset_hash VARCHAR(64), label VARCHAR(3), doc VARCHAR(16000) CHARACTER SET UNICODE",
    "research_items": "entity_id INTEGER NOT NULL, item_id INTEGER NOT NULL",
    "outbox": "entity_id VARCHAR(128) NOT NULL, revision BIGINT, applied BIGINT, attempts INTEGER, last_error VARCHAR(1000), doc VARCHAR(16000) CHARACTER SET UNICODE",
    "item_rules": "antecedent INTEGER NOT NULL, consequent INTEGER NOT NULL, support_count INTEGER, confidence FLOAT",
    "vectors": "run_id VARCHAR(100) NOT NULL, entity_id INTEGER NOT NULL, dim_id INTEGER NOT NULL, component FLOAT, label VARCHAR(3)",
    "benchmark_queries": "run_id VARCHAR(100) NOT NULL, entity_id INTEGER NOT NULL, dim_id INTEGER NOT NULL, component FLOAT",
    "results": "entity_id VARCHAR(100) NOT NULL, result_kind VARCHAR(20), doc VARCHAR(30000) CHARACTER SET UNICODE",
    "imports": "entity_id VARCHAR(64) NOT NULL, doc VARCHAR(16000) CHARACTER SET UNICODE",
}
KEYS = {
    "dishes": "item_id",
    "meal_items": "entity_id,position_id",
    "research_items": "entity_id,item_id",
    "item_rules": "antecedent,consequent",
    "vectors": "run_id,entity_id,dim_id",
    "benchmark_queries": "run_id,entity_id,dim_id",
}


def migrate():
    conn = connect()
    db = DB(conn)
    try:
        found = db.execute(
            "SELECT DatabaseName FROM DBC.DatabasesV WHERE DatabaseName = ?", [SCHEMA]
        )
        conn.commit()
        if not found:
            db.execute(
                f"CREATE DATABASE {SCHEMA} AS PERM = 300000000, SPOOL = 300000000"
            )
            conn.commit()
        tables = {
            r[0].strip().lower()
            for r in db.execute(
                "SELECT TableName FROM DBC.TablesV WHERE DatabaseName = ?", [SCHEMA]
            )
        }
        conn.commit()
        for name, columns in TABLES.items():
            if name not in tables:
                db.execute(
                    f"CREATE MULTISET TABLE {SCHEMA}.{name} ({columns}) UNIQUE PRIMARY INDEX ({KEYS.get(name, 'entity_id')})"
                )
                conn.commit()
        print(f"Schema ready: {SCHEMA}")
    finally:
        conn.close()
