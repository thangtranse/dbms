import concurrent.futures
import json
import os
import platform
import threading
import time
import uuid
import re
import numpy as np
from qdrant_client import models as qm
from .config import ARTIFACTS, PREFIX, qclient
from .db import session, connect, DB
from .pipeline import metrics, write_json
from .vector import save_result


def validate_sql_tables(tables):
    if len(tables) != 2:
        raise ValueError("Expected two benchmark tables")
    vectors, queries = tables
    if not (vectors == "vectors" or re.fullmatch(r"bv_[0-9a-f]{12}", vectors)) or not (
        queries == "benchmark_queries" or re.fullmatch(r"bq_[0-9a-f]{12}", queries)
    ):
        raise ValueError("Unexpected SQL benchmark table")
    return vectors, queries


def create_sql_storage(run_id):
    from .schema import TABLES

    suffix = uuid.uuid5(uuid.NAMESPACE_URL, run_id).hex[:12]
    tables = (f"bv_{suffix}", f"bq_{suffix}")
    for base, name in zip(["vectors", "benchmark_queries"], tables):
        with session() as db:
            db.execute(
                f"CREATE MULTISET TABLE {db.table(name)} ({TABLES[base]}) UNIQUE PRIMARY INDEX (run_id,entity_id,dim_id)"
            )
    return tables


def sql_neighbors(db, run_id, query_id, k, tables=("vectors", "benchmark_queries")):
    if not 1 <= k <= 1000:
        raise ValueError("Invalid k")
    vectors, queries = validate_sql_tables(tables)
    return db.execute(
        f"""SELECT TOP {int(k)} v.entity_id, SUM(v.component*q.component)/
        NULLIFZERO(SQRT(SUM(v.component*v.component))*SQRT(SUM(q.component*q.component))) AS similarity
        FROM {db.table(vectors)} v JOIN {db.table(queries)} q
        ON v.run_id=q.run_id AND v.dim_id=q.dim_id
        WHERE v.run_id=? AND q.entity_id=? GROUP BY v.entity_id ORDER BY similarity DESC,v.entity_id""",
        [run_id, int(query_id)],
    )


def recall_at_k(ids, scores, k=15, atol=1e-6):
    # Any ground-truth boundary tie may fill a boundary slot, but cannot replace a strict neighbor.
    cutoff = np.sort(scores)[-k]
    strict = set(np.flatnonzero(scores > cutoff + atol).tolist())
    tied = set(np.flatnonzero(np.abs(scores - cutoff) <= atol).tolist())
    actual = set(ids)
    return (len(actual & strict) + min(k - len(strict), len(actual & tied))) / k


def vote(labels):
    return "yes" if list(labels).count("yes") > list(labels).count("no") else "no"


def run(
    training_id,
    run_id,
    seed=0,
    k=15,
    repeats=5,
    concurrencies=(1, 4),
    warmup=50,
    reuse_data_run=None,
):
    folder = ARTIFACTS / run_id
    folder.mkdir(parents=True, exist_ok=False)
    training = json.loads((ARTIFACTS / training_id / "manifest.json").read_text())
    from .ingest import require_dataset

    if training.get("status") != "complete":
        raise ValueError("Training must complete before benchmarking")
    with session() as db:
        require_dataset(db, training["datasetHash"])
    data = np.load(ARTIFACTS / training_id / f"seed-{seed}" / "vectors.npz")
    a = data["train"].astype(np.float32)
    b = data["test"].astype(np.float32)
    if k > len(a):
        raise ValueError("k exceeds corpus size")
    ids = data["trainIds"].astype(int)
    qids = data["testIds"].astype(int)
    labels = data["trainLabels"]
    truth = data["testLabels"]
    if not np.all(np.linalg.norm(a, axis=1) > 0) or not np.all(
        np.linalg.norm(b, axis=1) > 0
    ):
        raise ValueError("Zero vectors cannot be compared using cosine")
    q = qclient()
    collection = f"{PREFIX}_bench_{uuid.uuid5(uuid.NAMESPACE_URL, run_id).hex[:12]}"
    index_start = time.perf_counter()
    q.create_collection(
        collection,
        vectors_config=qm.VectorParams(size=a.shape[1], distance=qm.Distance.COSINE),
        hnsw_config=qm.HnswConfigDiff(m=16, ef_construct=100, full_scan_threshold=10),
        optimizers_config=qm.OptimizersConfigDiff(
            indexing_threshold=1, default_segment_number=1
        ),
    )
    for start in range(0, len(a), 128):
        q.upsert(
            collection,
            [
                qm.PointStruct(id=int(i), vector=v.tolist(), payload={"label": str(l)})
                for i, v, l in zip(
                    ids[start : start + 128],
                    a[start : start + 128],
                    labels[start : start + 128],
                )
            ],
            wait=True,
        )
    deadline = time.monotonic() + 180
    while True:
        info = q.get_collection(collection)
        if info.status == qm.CollectionStatus.GREEN and (
            info.indexed_vectors_count or 0
        ) >= len(a):
            break
        if time.monotonic() > deadline:
            raise RuntimeError("HNSW indexing not ready; do not label full scan as ANN")
        time.sleep(1)
    q_index_seconds = time.perf_counter() - index_start
    sql_start = time.perf_counter()
    data_run = run_id
    prepared = dict(
        trainingRunId=training_id,
        seed=seed,
        datasetHash=training["datasetHash"],
        train=len(a),
        test=len(b),
        dimension=a.shape[1],
    )
    if reuse_data_run:
        previous = json.loads(
            (ARTIFACTS / reuse_data_run / "prepared.json").read_text()
        )
        tables = validate_sql_tables(
            tuple(previous.pop("sqlTables", ["vectors", "benchmark_queries"]))
        )
        if previous != prepared:
            raise ValueError("Prepared corpus differs from requested model/split")
        data_run = reuse_data_run
        with session() as db:
            for table, expected in zip(tables, [a.size, b.size]):
                if (
                    int(
                        db.execute(
                            f"SELECT COUNT(*) FROM {db.table(table)} WHERE run_id=?",
                            [data_run],
                        )[0][0]
                    )
                    != expected
                ):
                    raise ValueError("Prepared SQL corpus incomplete")
    else:
        tables = create_sql_storage(run_id)
        # Benchmark setup is unpublished until completion; bounded committed batches avoid
        # retaining a huge ANSI transaction/journal while loading the long-form vectors.
        for start in range(0, len(a), 32):
            with session() as db:
                db.execute(
                    f"INSERT INTO {db.table(tables[0])} VALUES (?,?,?,?,?)",
                    [
                        [run_id, int(i), j, float(x), str(label)]
                        for i, v, label in zip(
                            ids[start : start + 32],
                            a[start : start + 32],
                            labels[start : start + 32],
                        )
                        for j, x in enumerate(v)
                    ],
                    many=True,
                )
        for start in range(0, len(b), 32):
            with session() as db:
                db.execute(
                    f"INSERT INTO {db.table(tables[1])} VALUES (?,?,?,?)",
                    [
                        [run_id, int(i), j, float(x)]
                        for i, v in zip(qids[start : start + 32], b[start : start + 32])
                        for j, x in enumerate(v)
                    ],
                    many=True,
                )
        write_json(folder / "prepared.json", prepared | {"sqlTables": list(tables)})
    for table in tables:
        with session() as db:
            db.execute(
                f"COLLECT STATISTICS COLUMN (run_id), COLUMN (dim_id), COLUMN (run_id,entity_id), COLUMN (run_id,dim_id) ON {db.table(table)}"
            )
    sql_index_seconds = time.perf_counter() - sql_start
    # Renormalize stored float32 inputs in float64 for reference cosine.
    af = a.astype(np.float64)
    af /= np.linalg.norm(af, axis=1, keepdims=True)
    bf = b.astype(np.float64)
    bf /= np.linalg.norm(bf, axis=1, keepdims=True)
    ground = bf @ af.T
    pos = {int(i): j for j, i in enumerate(ids)}
    resources = []
    local = threading.local()
    guard = threading.Lock()

    def connections():
        if not hasattr(local, "td"):
            local.td = connect()
            local.q = qclient()
            with guard:
                resources.append((local.td, local.q))
        return local.td, local.q

    def query(engine, j):
        conn, client = connections()
        started = time.perf_counter()
        try:
            if engine == "teradata_exact":
                db = DB(conn)
                rows = sql_neighbors(db, data_run, int(qids[j]), k, tables)
                conn.commit()
                found = [int(r[0]) for r in rows]
                returned = [float(r[1]) for r in rows]
            else:
                points = client.query_points(
                    collection,
                    query=b[j].tolist(),
                    limit=k,
                    search_params=qm.SearchParams(
                        exact=engine == "qdrant_exact", hnsw_ef=128
                    ),
                    with_payload=False,
                ).points
                found = [int(p.id) for p in points]
                returned = [float(p.score) for p in points]
            elapsed = time.perf_counter() - started
            return dict(
                queryId=int(qids[j]),
                seconds=elapsed,
                ids=found,
                scores=returned,
                actual=str(truth[j]),
                error=None,
            )
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return dict(
                queryId=int(qids[j]),
                seconds=time.perf_counter() - started,
                error=type(exc).__name__,
            )

    query_positions = {int(i): j for j, i in enumerate(qids)}

    def evaluate(row, engine):
        if row["error"]:
            return row
        j = query_positions[row["queryId"]]
        indices = [pos[i] for i in row["ids"]]
        row["recall"] = recall_at_k(indices, ground[j], k)
        row["scoreError"] = max(
            [
                abs(score - ground[j, pos[i]])
                for i, score in zip(row["ids"], row["scores"])
            ]
            or [0]
        )
        row["predicted"] = vote(labels[indices])
        if engine != "qdrant_ann" and (row["recall"] < 1 or row["scoreError"] > 1e-5):
            row["error"] = "Exact search differs from reference"
        return row

    engines = ["teradata_exact", "qdrant_exact", "qdrant_ann"]
    summaries = []
    try:
        for concurrency in concurrencies:
            for repeat in range(repeats):
                order = engines[repeat % 3 :] + engines[: repeat % 3]
                for engine in order:
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=concurrency
                    ) as pool:
                        warm = list(
                            pool.map(
                                lambda j: query(engine, j),
                                [j % len(b) for j in range(warmup)],
                            )
                        )
                        warm = [evaluate(r, engine) for r in warm]
                        if any(r["error"] for r in warm):
                            raise RuntimeError(f"{engine}: warmup failed: {warm[0]}")
                        started = time.perf_counter()
                        rows = list(pool.map(lambda j: query(engine, j), range(len(b))))
                        wall = time.perf_counter() - started
                    for connection, qc in resources:
                        connection.close()
                        qc.close()
                    resources.clear()
                    rows = [evaluate(r, engine) for r in rows]
                    path = folder / f"{engine}-c{concurrency}-r{repeat}.jsonl"
                    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
                    good = [r for r in rows if not r["error"]]
                    latency = np.array([r["seconds"] for r in good]) * 1000
                    summaries.append(
                        dict(
                            engine=engine,
                            concurrency=concurrency,
                            repeat=repeat,
                            queries=len(rows),
                            errors=len(rows) - len(good),
                            errorRate=1 - len(good) / len(rows),
                            p50Ms=float(np.percentile(latency, 50))
                            if len(latency)
                            else None,
                            p95Ms=float(np.percentile(latency, 95))
                            if len(latency)
                            else None,
                            p99Ms=float(np.percentile(latency, 99))
                            if len(latency)
                            else None,
                            throughput=len(good) / wall,
                            recall=float(np.mean([r["recall"] for r in good]))
                            if good
                            else None,
                            quality=metrics(
                                [r["actual"] for r in good],
                                [r["predicted"] for r in good],
                            )
                            if good
                            else None,
                        )
                    )
                    print(
                        engine,
                        "concurrency",
                        concurrency,
                        "repeat",
                        repeat,
                        "complete",
                        flush=True,
                    )
        manifest = dict(
            runId=run_id,
            status="complete",
            trainingRunId=training_id,
            sqlDataRunId=data_run,
            sqlTables=list(tables),
            reusedSqlData=bool(reuse_data_run),
            seed=seed,
            k=k,
            warmup=warmup,
            repeats=repeats,
            dimension=a.shape[1],
            datasetHash=training["datasetHash"],
            train=len(a),
            test=len(b),
            floatInput="float32",
            groundTruth="float64 cosine",
            tieTolerance=1e-6,
            sqlOptimizerStatistics=True,
            hnsw=dict(
                m=16,
                full_scan_threshold=10,
                ef_construct=100,
                hnsw_ef=128,
                indexedVectors=info.indexed_vectors_count,
                segments=info.segments_count,
            ),
            setupSeconds=dict(
                qdrant=q_index_seconds,
                teradata=None if reuse_data_run else sql_index_seconds,
                teradataValidation=sql_index_seconds if reuse_data_run else None,
            ),
            host=dict(
                platform=platform.platform(),
                machine=platform.machine(),
                cpuCount=os.cpu_count(),
            ),
            topology=dict(
                teradataHost=os.environ["TERADATA_HOST"],
                qdrantUrl=os.environ["QDRANT_URL"],
                note="Sandbox host runner; Teradata VM vs Qdrant container; no hardware-equivalence claim",
            ),
            summaries=summaries,
        )
        import importlib.metadata as md
        import subprocess

        manifest["versions"] = {
            p: md.version(p) for p in ["teradatasql", "qdrant-client", "numpy"]
        }
        manifest["versions"]["qdrant-server"] = q.info().version
        with session() as db:
            manifest["versions"]["teradata-server"] = [
                list(r) for r in db.execute("SELECT InfoKey,InfoData FROM DBC.DBCInfoV")
            ]
        manifest["resourceSnapshot"] = {}
        for name, command in [
            ("hostMemory", ["sysctl", "-n", "hw.memsize"]),
            (
                "dockerEngine",
                [
                    "/Users/gper/Applications/Docker.app/Contents/Resources/bin/docker",
                    "info",
                    "--format",
                    "{{.MemTotal}} bytes / {{.NCPU}} CPUs",
                ],
            ),
            (
                "qdrantContainer",
                [
                    "/Users/gper/Applications/Docker.app/Contents/Resources/bin/docker",
                    "inspect",
                    "--format",
                    "{{json .HostConfig.Memory}} {{json .HostConfig.NanoCpus}} {{json .Config.Image}}",
                    "dbms-qdrant",
                ],
            ),
        ]:
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, timeout=10
                )
                manifest["resourceSnapshot"][name] = (
                    result.stdout.strip() if result.returncode == 0 else "unavailable"
                )
            except (OSError, subprocess.TimeoutExpired):
                manifest["resourceSnapshot"][name] = "unavailable"
        try:
            processes = subprocess.run(
                ["ps", "-axo", "command"], capture_output=True, text=True, timeout=10
            )
            manifest["resourceSnapshot"]["teradataVm"] = [
                line
                for line in processes.stdout.splitlines()
                if "qemu-system-x86_64 " in line and "-m " in line
            ]
        except (OSError, subprocess.TimeoutExpired):
            manifest["resourceSnapshot"]["teradataVm"] = "unavailable"
        manifest["qdrantCollectionConfig"] = info.config.model_dump(mode="json")
        manifest["measurementScope"] = (
            "latency: query call only; throughput: client query wall time; validation/scoring outside timed rounds"
        )
        # Raw measurements are separate, compact summaries persisted for UI.
        write_json(folder / "manifest.json", manifest)
        with session() as db:
            save_result(db, run_id, "benchmark", manifest)
        return manifest
    finally:
        for conn, client in resources:
            conn.close()
            client.close()
        q.close()
