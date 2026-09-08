"""Immutable reviewed evaluation cases and append-only execution reports."""

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

import duckdb
from pydantic import Field, model_validator

from querylab import __version__
from querylab.experiments.comparison import ComparisonRules
from querylab.experiments.models import SavedQuery
from querylab.experiments.serialization import display_json
from querylab.experiments.store import ExperimentStore
from querylab.grading.compare import compare_results
from querylab.models import StrictModel


class CreateCase(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    expectation: str = Field(min_length=1, max_length=2000)
    dataset_ids: list[str] = Field(min_length=1, max_length=4)
    reference_sql: str = Field(min_length=1, max_length=20000)
    reference_reviewed: bool
    rules: ComparisonRules = Field(default_factory=ComparisonRules)

    @model_validator(mode="after")
    def reviewed(self):
        if not self.reference_reviewed:
            raise ValueError(
                "Review the reference SQL before saving an evaluation case"
            )
        if len(self.dataset_ids) != len(set(self.dataset_ids)):
            raise ValueError("Choose each dataset only once")
        return self


class EvaluateQueries(StrictModel):
    queries: list[SavedQuery] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_names(self):
        names = [query.name for query in self.queries]
        if len(names) != len(set(names)):
            raise ValueError("Candidate names must be unique")
        return self


class EvaluationStore:
    def __init__(self, experiments: ExperimentStore):
        self.experiments = experiments

    def connect(self):
        connection = self.experiments.connect()
        connection.execute(
            "CREATE TABLE IF NOT EXISTS evaluation_cases (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS evaluation_runs (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        return connection

    def cases(self):
        with closing(self.connect()) as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM evaluation_cases ORDER BY rowid DESC"
                )
            ]

    def case(self, case_id):
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM evaluation_cases WHERE id=?", (case_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Evaluation case not found")
        return json.loads(row[0])

    def create_case(self, request: CreateCase):
        datasets = []
        for dataset_id in request.dataset_ids:
            experiment = self.experiments.get(dataset_id)
            # Validate the expectation on every scenario before freezing the case.
            self.experiments.run(dataset_id, request.reference_sql)
            digest = sha256(
                self.experiments.snapshot_path(dataset_id).read_bytes()
            ).hexdigest()
            if digest != experiment.snapshot_sha256:
                raise ValueError(
                    "Dataset snapshot changed on disk; create a new dataset"
                )
            datasets.append(
                {"id": experiment.id, "name": experiment.name, "sha256": digest}
            )
        case = {
            **request.model_dump(),
            "id": uuid4().hex,
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "datasets": datasets,
        }
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO evaluation_cases VALUES (?, ?)",
                (case["id"], json.dumps(case)),
            )
        return case

    def runs(self, case_id):
        self.case(case_id)
        with closing(self.connect()) as connection:
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM evaluation_runs WHERE case_id=? ORDER BY rowid DESC",
                    (case_id,),
                )
            ]

    def run(self, run_id):
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM evaluation_runs WHERE id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Evaluation run not found")
        return json.loads(row[0])

    def evaluate(self, case_id: str, request: EvaluateQueries):
        case = self.case(case_id)
        outcomes = []
        rules = ComparisonRules.model_validate(case["rules"])
        for dataset in case["datasets"]:
            try:
                path = self.experiments.snapshot_path(dataset["id"])
                if sha256(path.read_bytes()).hexdigest() != dataset["sha256"]:
                    raise ValueError(
                        "Dataset snapshot no longer matches the frozen case"
                    )
                reference = self.experiments.run(dataset["id"], case["reference_sql"])
            except (ValueError, duckdb.Error, OSError, KeyError) as exc:
                outcomes.extend(
                    {
                        "dataset_id": dataset["id"],
                        "dataset_name": dataset["name"],
                        "candidate": query.name,
                        "status": "invalid_case",
                        "error": str(exc),
                        "comparison": None,
                    }
                    for query in request.queries
                )
                continue
            for query in request.queries:
                outcome = {
                    "dataset_id": dataset["id"],
                    "dataset_name": dataset["name"],
                    "candidate": query.name,
                }
                try:
                    actual = self.experiments.run(dataset["id"], query.sql)
                    comparison = compare_results(reference, actual, rules)
                    outcome.update(
                        status="passed" if comparison.passed else "failed",
                        comparison=asdict(comparison),
                        error=None,
                        duration_ms=actual.duration_ms,
                    )
                except (ValueError, duckdb.Error) as exc:
                    outcome.update(status="error", error=str(exc), comparison=None)
                outcomes.append(outcome)
        report = display_json(
            {
                "schema_version": 1,
                "id": uuid4().hex,
                "case_id": case_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "case": case,
                "queries": [query.model_dump() for query in request.queries],
                "engine": "duckdb",
                "engine_version": duckdb.__version__,
                "querylab_version": __version__,
                "outcomes": outcomes,
                "summary": {
                    state: sum(row["status"] == state for row in outcomes)
                    for state in ("passed", "failed", "error", "invalid_case")
                },
            }
        )
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO evaluation_runs VALUES (?, ?, ?)",
                (report["id"], case_id, json.dumps(report)),
            )
        return report

    def compare_runs(self, earlier_id: str, later_id: str):
        earlier, later = self.run(earlier_id), self.run(later_id)
        if earlier["case_id"] != later["case_id"]:
            raise ValueError("Compare runs of the same frozen evaluation case")
        before = {
            (row["dataset_id"], row["candidate"]): row for row in earlier["outcomes"]
        }
        after = {
            (row["dataset_id"], row["candidate"]): row for row in later["outcomes"]
        }
        changes = []
        for key in sorted(before.keys() | after.keys()):
            old, new = before.get(key), after.get(key)
            old_status = old["status"] if old else "absent"
            new_status = new["status"] if new else "absent"
            changes.append(
                {
                    "dataset_id": key[0],
                    "candidate": key[1],
                    "before": old_status,
                    "after": new_status,
                    "regression": old_status == "passed"
                    and new_status in ("failed", "error"),
                    "improvement": old_status in ("failed", "error")
                    and new_status == "passed",
                }
            )
        return {
            "earlier": earlier,
            "later": later,
            "changes": changes,
            "same_engine_version": earlier["engine_version"] == later["engine_version"],
        }
