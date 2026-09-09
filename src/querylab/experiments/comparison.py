"""Compare candidate outputs on one fixed snapshot, without a correctness claim."""

from dataclasses import asdict
from hashlib import sha256
import duckdb
from pydantic import Field, model_validator

from querylab.experiments.models import SavedQuery
from querylab.experiments.store import ExperimentStore
from querylab.grading.compare import compare_results
from querylab.models import GradingConfig, StrictModel


class ComparisonRules(GradingConfig):
    numeric_tolerance: float = Field(default=0.000001, ge=0, le=1, allow_inf_nan=False)


class CompareQueries(StrictModel):
    queries: list[SavedQuery] = Field(min_length=2, max_length=6)
    rules: ComparisonRules = Field(default_factory=ComparisonRules)

    @model_validator(mode="after")
    def unique_names(self):
        names = [query.name for query in self.queries]
        if len(names) != len(set(names)):
            raise ValueError("Candidate names must be unique")
        return self


def compare_queries(
    store: ExperimentStore, experiment_id: str, request: CompareQueries
):
    experiment = store.get(experiment_id)

    def verify_snapshot():
        try:
            digest = sha256(store.snapshot_path(experiment_id).read_bytes()).hexdigest()
        except OSError as exc:
            raise ValueError("Saved dataset file could not be read") from exc
        if digest != experiment.snapshot_sha256:
            raise ValueError("Dataset snapshot no longer matches the saved snapshot")

    verify_snapshot()
    outputs = []
    results = []
    for query in request.queries:
        try:
            result = store.run(experiment_id, query.sql)
            results.append(result)
            outputs.append(
                {"query": query.model_dump(), "result": asdict(result), "error": None}
            )
        except (ValueError, duckdb.Error) as exc:
            results.append(None)
            outputs.append(
                {"query": query.model_dump(), "result": None, "error": str(exc)}
            )
    verify_snapshot()
    baseline = results[0]
    for index, output in enumerate(outputs):
        result = results[index]
        output["comparison"] = (
            asdict(compare_results(baseline, result, request.rules))
            if index > 0 and baseline is not None and result is not None
            else None
        )
    return {
        "experiment_id": experiment.id,
        "snapshot_sha256": experiment.snapshot_sha256,
        "baseline": request.queries[0].name,
        "rules": request.rules.model_dump(),
        "meaning": "Agreement with the first query is not a correctness judgment.",
        "outputs": outputs,
    }
