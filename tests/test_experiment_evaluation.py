import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from querylab.experiments.evaluation import CreateCase, EvaluateQueries, EvaluationStore
from querylab.experiments.store import ExperimentStore
from querylab.web.app import create_app
from test_experiments import draft


def setup_case(tmp_path):
    experiments = ExperimentStore(tmp_path)
    normal = experiments.create(draft("INSERT INTO items VALUES (1), (2)"))
    edge = experiments.create(draft())
    evaluations = EvaluationStore(experiments)
    case = evaluations.create_case(
        CreateCase(
            name="All values",
            expectation="Preserve duplicates and NULLs",
            dataset_ids=[normal.id, edge.id],
            reference_sql="SELECT value FROM items",
            reference_reviewed=True,
        )
    )
    return experiments, evaluations, case


def candidates(sql):
    return EvaluateQueries(queries=[dict(name="Candidate", sql=sql)])


def test_reports_find_edge_failure_and_preserve_original_sql(tmp_path):
    experiments, evaluations, case = setup_case(tmp_path)
    first = evaluations.evaluate(
        case["id"], candidates("SELECT DISTINCT value FROM items")
    )
    assert first["summary"] == dict(passed=1, failed=1, error=0, invalid_case=0)
    second = evaluations.evaluate(case["id"], candidates("SELECT value FROM items"))
    reopened = EvaluationStore(ExperimentStore(tmp_path))
    assert (
        reopened.run(first["id"])["queries"][0]["sql"]
        == "SELECT DISTINCT value FROM items"
    )
    assert reopened.run(first["id"]) == first
    assert reopened.cases()[0] == case
    assert len(reopened.runs(case["id"])) == 2
    comparison = reopened.compare_runs(first["id"], second["id"])
    assert sum(row["improvement"] for row in comparison["changes"]) == 1
    assert comparison["same_engine_version"]
    reverse = reopened.compare_runs(second["id"], first["id"])
    assert sum(row["regression"] for row in reverse["changes"]) == 1


def test_invalid_reference_and_modified_snapshot_do_not_pass(tmp_path):
    experiments, evaluations, case = setup_case(tmp_path)
    path = experiments.snapshot_path(case["dataset_ids"][0])
    path.write_bytes(b"changed")
    report = evaluations.evaluate(case["id"], candidates("SELECT value FROM items"))
    assert report["summary"]["invalid_case"] == 1
    assert report["summary"]["passed"] == 1
    assert "no longer matches" in report["outcomes"][0]["error"]


def test_candidate_error_is_separate_and_cases_cannot_mix(tmp_path):
    experiments, evaluations, case = setup_case(tmp_path)
    failed = evaluations.evaluate(case["id"], candidates("SELECT missing FROM items"))
    assert failed["summary"]["error"] == 2
    other = evaluations.create_case(
        CreateCase(
            name="Other",
            expectation="Constant",
            dataset_ids=case["dataset_ids"],
            reference_sql="SELECT 1",
            reference_reviewed=True,
        )
    )
    other_run = evaluations.evaluate(other["id"], candidates("SELECT 1"))
    with pytest.raises(ValueError, match="same frozen"):
        evaluations.compare_runs(failed["id"], other_run["id"])


def test_review_and_unique_ids_required():
    with pytest.raises(ValidationError, match="Review"):
        CreateCase(
            name="Test",
            expectation="Test",
            dataset_ids=["x"],
            reference_sql="SELECT 1",
            reference_reviewed=False,
        )
    with pytest.raises(ValidationError, match="once"):
        CreateCase(
            name="Test",
            expectation="Test",
            dataset_ids=["x", "x"],
            reference_sql="SELECT 1",
            reference_reviewed=True,
        )
    with pytest.raises(ValidationError, match="unique"):
        EvaluateQueries(queries=[dict(name="a", sql="SELECT 1")] * 2)


def test_evaluation_api_restart_and_missing_ids(tmp_path, monkeypatch):
    experiments, evaluations, case = setup_case(tmp_path)
    monkeypatch.setenv("QUERYLAB_HISTORY_DB", str(tmp_path / "practice.sqlite3"))
    with TestClient(create_app(experiment_store=experiments)) as client:
        assert len(client.get("/api/evaluation-cases").json()) == 1
        assert (
            client.post(
                "/api/evaluation-cases",
                json={
                    "name": "Invalid",
                    "expectation": "Anything",
                    "dataset_ids": case["dataset_ids"],
                    "reference_sql": "SELECT nonexistent FROM items",
                    "reference_reviewed": True,
                },
            ).status_code
            == 400
        )
        one = client.post(
            f"/api/evaluation-cases/{case['id']}/runs",
            json=candidates("SELECT value FROM items").model_dump(),
        ).json()
        two = client.post(
            f"/api/evaluation-cases/{case['id']}/runs",
            json=candidates("SELECT DISTINCT value FROM items").model_dump(),
        ).json()
    with TestClient(create_app(experiment_store=ExperimentStore(tmp_path))) as client:
        assert len(client.get(f"/api/evaluation-cases/{case['id']}/runs").json()) == 2
        response = client.get(
            "/api/evaluation-runs/compare",
            params={"earlier": one["id"], "later": two["id"]},
        )
        assert response.status_code == 200
        assert any(change["regression"] for change in response.json()["changes"])
        assert client.get("/api/evaluation-cases/missing/runs").status_code == 404
        assert (
            client.get(
                "/api/evaluation-runs/compare",
                params={"earlier": "missing", "later": one["id"]},
            ).status_code
            == 404
        )


def test_timeout_becomes_error_and_next_query_still_runs(tmp_path, monkeypatch):
    experiments, evaluations, case = setup_case(tmp_path)
    monkeypatch.setattr("querylab.experiments.store.TIMEOUT_SECONDS", 0.1)
    report = evaluations.evaluate(
        case["id"],
        candidates(
            "SELECT sum(sin(a.i + b.i)) FROM range(1000000) a(i), range(1000000) b(i)"
        ),
    )
    assert report["summary"]["error"] == 2
    assert all("interrupt" in row["error"].lower() for row in report["outcomes"])
    assert experiments.run(case["dataset_ids"][0], "SELECT 1").rows == ((1,),)
