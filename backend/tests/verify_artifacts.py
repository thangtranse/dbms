"""Audit a completed training run without databases; writes a validation sidecar."""

import argparse
import json
import math
import numpy as np
from gensim.models import Doc2Vec
from ol.config import ARTIFACTS, FOOD
from ol.ingest import load_food
from ol.numerics import check_blas
from ol.pipeline import write_json

p = argparse.ArgumentParser()
p.add_argument("run_id")
args = p.parse_args()
assert args.run_id and all(c.isalnum() or c in "_-" for c in args.run_id)
root = ARTIFACTS / args.run_id
manifest = json.loads((root / "manifest.json").read_text())
assert manifest["status"] == "complete" and manifest["runId"] == args.run_id
checksum, records = load_food(FOOD)
assert checksum == manifest["datasetHash"]
by_id = {r["id"]: r for r in records}
group = lambda i: tuple(sorted(set(by_id[i]["itemIds"])))
audited = []
for seed in manifest["seeds"]:
    folder = root / f"seed-{seed}"
    for name in ["ind-items.model", "ind-fis.model", "joi.model"]:
        model = Doc2Vec.load(str(folder / name))
        assert model.vector_size == manifest["dimension"]
        assert np.isfinite(model.dv.vectors).all()
    split = json.loads((folder / "split.json").read_text())
    train_ids, test_ids = set(split["train"]), set(split["test"])
    assert not train_ids & test_ids and train_ids | test_ids == set(by_id)
    assert {group(i) for i in train_ids}.isdisjoint(group(i) for i in test_ids)
    with np.load(folder / "vectors.npz") as vectors:
        for part in ["train", "test"]:
            assert list(vectors[part + "Ids"]) == split[part]
            a = vectors[part]
            assert a.dtype == np.float32 and a.shape == (len(split[part]), manifest["dimension"])
            assert np.isfinite(a).all()
            np.testing.assert_allclose(np.linalg.norm(a, axis=1), 1, atol=1e-5)
            assert list(vectors[part + "Labels"]) == [by_id[i]["label"] for i in split[part]]
    patterns = json.loads((folder / "patterns.json").read_text())
    train_sets = [set(by_id[i]["itemIds"]) for i in train_ids]
    threshold = math.ceil(len(train_ids) * manifest["minsup"] - 1e-9)
    assert all(sum(set(pattern) <= row for row in train_sets) >= threshold for pattern in patterns)
    with np.load(folder / "items.npz") as items:
        assert set(items["ids"]) == set.union(*train_sets)
        assert np.isfinite(items["vectors"]).all() and np.isfinite(items["xy"]).all()
        assert len(items["clusters"]) == len(items["ids"])
    rows = [r for r in manifest["results"] if r["seed"] == seed]
    assert {r["method"] for r in rows} == {"Bag-of-items + LinearSVC", "Trans2Vec-Ind", "Trans2Vec-Joi"}
    for row in rows:
        assert 0 <= row["accuracy"] <= 1 and 0 <= row["f1"] <= 1
        assert sum(row["confusion"].values()) == len(test_ids)
    audited.append(dict(seed=seed, train=len(train_ids), test=len(test_ids), itemsets=len(patterns)))
report = dict(runId=args.run_id, datasetHash=checksum, status="passed", seeds=audited, blas=check_blas())
write_json(root / "validation.json", report)
print(json.dumps(report))
