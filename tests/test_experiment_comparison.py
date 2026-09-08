import pytest
from pydantic import ValidationError
from querylab.experiments.comparison import CompareQueries, compare_queries
from querylab.experiments.store import ExperimentStore
from test_experiments import draft


def request(*sql, order=False):
    return CompareQueries(
        queries=[dict(name=f"Q{i}", sql=query) for i, query in enumerate(sql)],
        rules=dict(order_matters=order),
    )


def test_comparison_duplicates_nulls_order_and_errors(tmp_path):
    store = ExperimentStore(tmp_path)
    experiment = store.create(draft())
    report = compare_queries(
        store,
        experiment.id,
        request(
            "SELECT value FROM items ORDER BY value NULLS FIRST",
            "SELECT value FROM items ORDER BY value NULLS LAST",
            "SELECT DISTINCT value FROM items",
            "SELECT bad FROM items",
        ),
    )
    assert report["outputs"][1]["comparison"]["passed"]
    assert not report["outputs"][2]["comparison"]["passed"]
    assert report["outputs"][3]["error"]
    assert report["outputs"][3]["comparison"] is None
    ordered = compare_queries(
        store,
        experiment.id,
        request(
            "SELECT value FROM items ORDER BY value NULLS FIRST",
            "SELECT value FROM items ORDER BY value NULLS LAST",
            order=True,
        ),
    )
    assert not ordered["outputs"][1]["comparison"]["passed"]
    assert report["snapshot_sha256"] == experiment.snapshot_sha256
    assert "not a correctness" in report["meaning"]


def test_baseline_error_never_reports_match(tmp_path):
    store = ExperimentStore(tmp_path)
    experiment = store.create(draft())
    report = compare_queries(
        store,
        experiment.id,
        request("SELECT missing FROM items", "SELECT * FROM items"),
    )
    assert report["outputs"][1]["comparison"] is None
    assert report["outputs"][1]["result"] is not None


def test_tolerance_and_column_names(tmp_path):
    store = ExperimentStore(tmp_path)
    experiment = store.create(draft())
    report = compare_queries(
        store,
        experiment.id,
        request("SELECT 1.0 AS n", "SELECT 1.0000001 AS n", "SELECT 1.0 AS renamed"),
    )
    assert report["outputs"][1]["comparison"]["passed"]
    assert not report["outputs"][2]["comparison"]["passed"]


def test_duplicate_names_and_nonfinite_tolerance_rejected():
    with pytest.raises(ValidationError):
        CompareQueries(queries=[dict(name="same", sql="SELECT 1")] * 2)
    with pytest.raises(ValidationError):
        CompareQueries(
            queries=[dict(name="a", sql="SELECT 1"), dict(name="b", sql="SELECT 1")],
            rules=dict(numeric_tolerance=float("nan")),
        )
