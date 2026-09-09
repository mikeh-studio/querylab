import duckdb
import pytest
from fastapi.testclient import TestClient

from querylab.experiments.models import DatasetDraft, SaveQueries
from querylab.experiments.store import ExperimentStore
from querylab.web.app import create_app


def draft(seed="INSERT INTO items VALUES (1), (1), (NULL);"):
    return DatasetDraft(
        name="Items",
        description="Duplicate and NULL fixtures",
        tables=[
            dict(
                name="items",
                ddl="CREATE TABLE items (value INTEGER)",
                description="Values",
            )
        ],
        seed_sql=seed,
    )


@pytest.fixture
def store(tmp_path):
    return ExperimentStore(tmp_path / "experiments")


def test_snapshot_survives_restart_and_query_saves(store):
    saved = store.create(draft())
    before = store.snapshot_path(saved.id).read_bytes()
    changed = store.save_queries(
        saved.id,
        SaveQueries(revision=1, queries=[dict(name="All", sql="SELECT * FROM items")]),
    )
    reopened = ExperimentStore(store.root)
    assert reopened.get(saved.id) == changed
    assert reopened.run(saved.id, changed.queries[0].sql).rows == ((1,), (1,), (None,))
    assert reopened.snapshot_path(saved.id).read_bytes() == before
    with pytest.raises(ValueError, match="another tab"):
        reopened.save_queries(saved.id, SaveQueries(revision=1, queries=[]))
    assert reopened.get(saved.id).queries == changed.queries


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM items",
        "CREATE TABLE bad (n INT)",
        "SELECT 1; SELECT 2",
        "COPY items TO '/tmp/querylab-bad.csv'",
        "SELECT * FROM read_csv('/etc/passwd')",
    ],
)
def test_read_only_and_external_access(store, sql):
    saved = store.create(draft())
    with pytest.raises((ValueError, duckdb.Error)):
        store.run(saved.id, sql)
    assert len(store.run(saved.id, "SELECT * FROM items").rows) == 3


def test_result_limit_is_error_not_partial_success(store):
    saved = store.create(draft())
    with pytest.raises(ValueError, match="not truncated"):
        store.run(saved.id, "SELECT * FROM range(501)")


def test_failed_dataset_not_saved(store):
    with pytest.raises(ValueError, match="INSERT"):
        store.create(draft("DROP TABLE items"))
    assert store.list() == []
    assert list(store.root.glob("*.duckdb")) == []


def test_paths_are_resolved_only_for_known_ids(store):
    with pytest.raises(KeyError):
        store.snapshot_path("../../etc/passwd")


def test_generated_values_materialized_once(store):
    saved = store.create(
        draft(
            "INSERT INTO items SELECT CAST(random() * 100000 AS INTEGER) FROM range(10)"
        )
    )
    assert (
        store.run(saved.id, "SELECT * FROM items").rows
        == ExperimentStore(store.root).run(saved.id, "SELECT * FROM items").rows
    )


def test_generation_and_api_restart(store, monkeypatch):
    monkeypatch.setenv("QUERYLAB_HISTORY_DB", str(store.root / "practice.sqlite3"))

    class Provider:
        def generate(self, prompt, *, output_schema):
            assert "reference SQL" in prompt
            assert "question" not in output_schema["properties"]
            return draft().model_dump_json()

    monkeypatch.setattr(
        "querylab.experiments.api.create_provider", lambda *args: Provider()
    )
    with TestClient(create_app(experiment_store=store)) as client:
        assert client.get("/explore").status_code == 200
        response = client.post(
            "/api/experiments/generate", json={"description": "items"}
        )
        assert response.status_code == 200, response.text
        saved = response.json()
        assert (
            client.put(
                f"/api/experiments/{saved['id']}/queries",
                json={
                    "revision": 1,
                    "queries": [{"name": "All", "sql": "SELECT * FROM items"}],
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/experiments/{saved['id']}/run", json={"sql": "DROP TABLE items"}
            ).status_code
            == 400
        )
        assert client.get("/api/experiments/missing").status_code == 404
    with TestClient(create_app(experiment_store=ExperimentStore(store.root))) as client:
        assert len(client.get("/api/experiments").json()) == 1
        assert (
            client.get(f"/api/experiments/{saved['id']}").json()["queries"][0]["name"]
            == "All"
        )
        assert client.post(
            f"/api/experiments/{saved['id']}/run", json={"sql": "SELECT * FROM items"}
        ).json()["rows"] == [[1], [1], [None]]
        assert client.post("/api/experiments/demo").status_code == 200


def test_unusual_sql_values_have_json_display(store, monkeypatch):
    monkeypatch.setenv("QUERYLAB_HISTORY_DB", str(store.root / "practice.sqlite3"))
    saved = store.create(draft())
    with TestClient(create_app(experiment_store=store)) as client:
        response = client.post(
            f"/api/experiments/{saved.id}/run",
            json={
                "sql": "SELECT 'NaN'::DOUBLE AS n, 1.25::DECIMAL(4,2) AS d, DATE '2026-01-01' AS day"
            },
        )
        assert response.status_code == 200
        assert response.json()["rows"] == [["nan", "1.25", "2026-01-01"]]
