"""Inductive adaptation of Trans2Vec Ind/Joi. Frequent sets are mined on train only.
Reference: github.com/nphdang/Trans2Vec; legacy scripts train on all data. We do not.
"""

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
import numpy as np
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth
from .ingest import load_food
from .config import ARTIFACTS, FOOD


def normalize(x):
    x = np.asarray(x, dtype=np.float32)
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


def split(records, seed):
    y = [r["label"] for r in records]
    groups = [" ".join(map(str, sorted(set(r["itemIds"])))) for r in records]
    train, test = next(
        StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed).split(
            np.zeros(len(y)), y, groups
        )
    )
    return train, test


def mine(records, minsup):
    import pandas as pd

    sets = [sorted(set(map(str, r["itemIds"]))) for r in records]
    enc = TransactionEncoder()
    matrix = enc.fit(sets).transform(sets, sparse=True)
    frame = pd.DataFrame.sparse.from_spmatrix(matrix, columns=enc.columns_).astype(
        pd.SparseDtype(bool, False)
    )
    result = fpgrowth(frame, min_support=minsup, use_colnames=True)
    return sorted([tuple(sorted(map(int, s))) for s in result.itemsets if len(s) >= 1])


def tokens(items, patterns):
    unique = set(items)
    return [f"fi:{','.join(map(str, p))}" for p in patterns if set(p) <= unique]


def stable_seed(value):
    return int(hashlib.sha256(str(value).encode()).hexdigest()[:8], 16)


def infer(model, words, seed, epochs):
    known = [w for w in words if w in model.wv]
    if not known:
        return np.zeros(model.vector_size, dtype=np.float32)
    model.random.seed(seed)
    return model.infer_vector(known, epochs=epochs).astype(np.float32)


def fit_model(sentences, dim, epochs, seed):
    # workers=1 and stable hash eliminate thread scheduling/PYTHONHASHSEED drift.
    docs = [TaggedDocument(s, [str(i)]) for i, s in enumerate(sentences)]
    m = Doc2Vec(
        vector_size=dim,
        min_count=1,
        workers=1,
        dm=0,
        epochs=epochs,
        seed=seed,
        hashfxn=stable_seed,
    )
    m.build_vocab(docs)
    m.train(docs, total_examples=len(docs), epochs=epochs)
    return m


def metrics(y, pred):
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=["no", "yes"]).ravel().tolist()
    return dict(
        accuracy=float(accuracy_score(y, pred)),
        f1=float(f1_score(y, pred, average="macro", zero_division=0)),
        confusion=dict(tp=tp, fn=fn, fp=fp, tn=tn),
    )


def write_json(path, obj):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    temporary.replace(path)


def train(run_id, seeds=range(10), dim=128, epochs=50, minsup=0.006):
    from .numerics import check_blas

    blas = check_blas()
    checksum, records = load_food(FOOD)
    root = ARTIFACTS / run_id
    root.mkdir(parents=True, exist_ok=False)
    outputs = []
    started = time.perf_counter()
    for seed in seeds:
        folder = root / f"seed-{seed}"
        folder.mkdir()
        train_idx, test_idx = split(records, seed)
        tr = [records[i] for i in train_idx]
        te = [records[i] for i in test_idx]
        patterns = mine(tr, minsup)
        write_json(folder / "patterns.json", patterns)
        write_json(
            folder / "split.json",
            dict(train=[r["id"] for r in tr], test=[r["id"] for r in te]),
        )
        item_tr = [[f"i:{i}" for i in r["itemIds"]] for r in tr]
        fis_tr = [tokens(r["itemIds"], patterns) or ["fi:empty"] for r in tr]
        item_te = [[f"i:{i}" for i in r["itemIds"]] for r in te]
        fis_te = [tokens(r["itemIds"], patterns) or ["fi:empty"] for r in te]
        y = [r["label"] for r in tr]
        yt = [r["label"] for r in te]
        t = time.perf_counter()
        cv = CountVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False)
        a = cv.fit_transform([" ".join(x) for x in item_tr])
        b = cv.transform([" ".join(x) for x in item_te])
        clf = LinearSVC(random_state=seed, max_iter=10000).fit(a, y)
        outputs.append(
            dict(
                seed=seed,
                method="Bag-of-items + LinearSVC",
                **metrics(yt, clf.predict(b)),
                trainSeconds=time.perf_counter() - t,
            )
        )
        t = time.perf_counter()
        mi = fit_model(item_tr, dim, epochs, seed)
        mf = fit_model(fis_tr, dim, epochs, seed)
        mi.save(str(folder / "ind-items.model"))
        mf.save(str(folder / "ind-fis.model"))
        vi = np.array([(mi.dv[str(i)] + mf.dv[str(i)]) / 2 for i in range(len(tr))])
        vt = np.array(
            [
                (
                    infer(mi, a, seed + int(r["id"]), epochs)
                    + infer(mf, b, seed + int(r["id"]), epochs)
                )
                / 2
                for a, b, r in zip(item_te, fis_te, te)
            ]
        )
        clf = LinearSVC(random_state=seed, max_iter=10000).fit(vi, y)
        outputs.append(
            dict(
                seed=seed,
                method="Trans2Vec-Ind",
                **metrics(yt, clf.predict(vt)),
                trainSeconds=time.perf_counter() - t,
            )
        )
        t = time.perf_counter()
        mj = fit_model([a + b for a, b in zip(item_tr, fis_tr)], dim, epochs, seed)
        mj.save(str(folder / "joi.model"))
        vj = np.array([mj.dv[str(i)] for i in range(len(tr))])
        vjt = np.array(
            [
                infer(mj, a + b, seed + int(r["id"]), epochs)
                for a, b, r in zip(item_te, fis_te, te)
            ]
        )
        clf = LinearSVC(random_state=seed, max_iter=10000).fit(vj, y)
        outputs.append(
            dict(
                seed=seed,
                method="Trans2Vec-Joi",
                **metrics(yt, clf.predict(vjt)),
                trainSeconds=time.perf_counter() - t,
            )
        )
        np.savez_compressed(
            folder / "vectors.npz",
            train=normalize(vj),
            test=normalize(vjt),
            trainIds=[r["id"] for r in tr],
            testIds=[r["id"] for r in te],
            trainLabels=y,
            testLabels=yt,
        )
        # Infer singleton items through the trained document model: DBOW word vectors are not trained.
        ids = sorted({i for r in tr for i in r["itemIds"]})
        iv = normalize(
            [
                infer(mj, [f"i:{i}"] + tokens([i], patterns), seed + i, epochs)
                for i in ids
            ]
        )
        cl = KMeans(
            n_clusters=min(7, len(ids)), random_state=seed, n_init=10
        ).fit_predict(iv)
        xy = PCA(n_components=2, random_state=seed).fit_transform(iv)
        span = np.maximum(np.ptp(xy, axis=0), 1e-8)
        xy = 5 + 90 * (xy - xy.min(axis=0)) / span
        np.savez_compressed(
            folder / "items.npz", ids=ids, vectors=iv, clusters=cl, xy=xy
        )
        print(f"Completed seed {seed}, frequent itemsets={len(patterns)}", flush=True)
    lengths = [len(r["itemIds"]) for r in records]
    labels = Counter(r["label"] for r in records)
    manifest = dict(
        runId=run_id,
        status="complete",
        datasetHash=checksum,
        dimension=dim,
        epochs=epochs,
        minsup=minsup,
        seeds=list(seeds),
        embedding="Trans2Vec-Joi",
        workers=1,
        blasRegression=blas,
        inductive=True,
        reference="https://github.com/nphdang/Trans2Vec",
        adaptation="Python FP-growth; train-only itemsets and Doc2Vec; held-out infer_vector; no claim of paper reproduction",
        dataset=dict(
            transactions=len(records),
            yes=labels["yes"],
            no=labels["no"],
            uniqueItems=len({i for r in records for i in r["itemIds"]}),
            avgLength=sum(lengths) / len(lengths),
            minLength=min(lengths),
            maxLength=max(lengths),
        ),
        totalSeconds=time.perf_counter() - started,
        results=outputs,
    )
    import importlib.metadata as md

    manifest["versions"] = {
        p: md.version(p) for p in ["numpy", "gensim", "scikit-learn", "mlxtend"]
    }
    write_json(root / "manifest.json", manifest)
    return manifest
