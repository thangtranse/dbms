import json
import numpy as np
from ol.pipeline import split, mine, tokens, fit_model, infer, normalize
from ol.benchmark import recall_at_k, vote, validate_sql_tables
from ol.models import DishInput, MealInput
from pydantic import ValidationError
import pytest


def test_duplicate_content_stays_on_one_side():
    rows = [
        dict(
            id=i + 1,
            itemIds=[i % 20 + 1, (i % 20) + 100],
            label="yes" if i % 2 else "no",
        )
        for i in range(100)
    ]
    a, b = split(rows, 3)
    key = lambda r: tuple(sorted(set(r["itemIds"])))
    assert {key(rows[i]) for i in a}.isdisjoint({key(rows[i]) for i in b})
    assert set(a) | set(b) == set(range(100))


def test_itemset_fixture_and_unseen_tokens():
    patterns = mine(
        [{"itemIds": [1, 2, 2]}, {"itemIds": [1, 2]}, {"itemIds": [1, 3]}], 0.6
    )
    assert patterns == [(1,), (1, 2), (2,)]
    assert tokens([1, 2], patterns) == ["fi:1", "fi:1,2", "fi:2"]
    assert tokens([1, 3], patterns) == ["fi:1"]


def test_doc2vec_inference_is_repeatable_and_does_not_learn_test():
    m = fit_model([["i:1", "i:2"], ["i:2", "i:3"]], 8, 5, 0)
    before = m.dv.vectors.copy()
    assert np.array_equal(infer(m, ["i:1"], 7, 5), infer(m, ["i:1"], 7, 5))
    assert not infer(m, ["i:never-seen"], 7, 5).any()
    np.testing.assert_array_equal(before, m.dv.vectors)
    np.testing.assert_allclose(
        np.linalg.norm(normalize([[1, 2, 3]]), axis=1), 1, rtol=1e-6
    )


def test_tie_aware_recall_does_not_replace_strict_neighbor():
    scores = np.array([1.0, 0.5, 0.5, 0.5, 0.1])
    assert recall_at_k([0, 2], scores, 2) == 1
    assert recall_at_k([1, 2], scores, 2) == 0.5
    assert vote(["yes", "no"]) == "no"


def test_reject_invalid_input_and_client_cluster_changes():
    with pytest.raises(ValidationError):
        MealInput(date="not-date", itemIds=[], label="yes")
    with pytest.raises(ValidationError):
        DishInput(itemId=1, name="a", price=-1)
    with pytest.raises(ValidationError):
        DishInput(itemId=1, name="a", price=1, clusterId=7)


def test_full_training_fixture_writes_real_artifacts(tmp_path, monkeypatch):
    from ol import pipeline

    source = tmp_path / "food.txt"
    source.write_text(
        "\n".join(
            ("yes" if i % 2 else "no") + "\t" + f"1 {i % 20 + 2} {i % 7 + 22}"
            for i in range(100)
        )
    )
    monkeypatch.setattr(pipeline, "FOOD", source)
    monkeypatch.setattr(pipeline, "ARTIFACTS", tmp_path)
    manifest = pipeline.train("fixture", seeds=range(1), dim=8, epochs=2, minsup=0.1)
    assert manifest["status"] == "complete"
    assert {r["method"] for r in manifest["results"]} == {
        "Bag-of-items + LinearSVC",
        "Trans2Vec-Ind",
        "Trans2Vec-Joi",
    }
    folder = tmp_path / "fixture" / "seed-0"
    arrays = np.load(folder / "vectors.npz")
    assert np.isfinite(arrays["train"]).all() and np.isfinite(arrays["test"]).all()
    assert set(arrays["trainIds"]).isdisjoint(arrays["testIds"])
    assert len(arrays["trainIds"]) + len(arrays["testIds"]) == 100
    assert (
        json.loads((tmp_path / "fixture" / "manifest.json").read_text())["dimension"]
        == 8
    )


def test_benchmark_storage_cannot_target_business_tables():
    assert validate_sql_tables(("bv_0123456789ab", "bq_0123456789ab")) == (
        "bv_0123456789ab",
        "bq_0123456789ab",
    )
    with pytest.raises(ValueError):
        validate_sql_tables(("users", "meals"))
    with pytest.raises(ValueError):
        validate_sql_tables(("vectors",))


def test_blas_negative_one_is_a_value_not_an_exception():
    from ol.numerics import check_blas

    assert check_blas()["negativeOneDot"] == -1.0
