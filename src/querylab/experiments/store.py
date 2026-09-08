"""Local metadata plus immutable DuckDB files. No credentials or remote sources."""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
from threading import Timer
from uuid import uuid4

import duckdb

from querylab.engines.base import QueryResult
from querylab.experiments.models import DatasetDraft, Experiment, SaveQueries

MAX_ROWS = 500
TIMEOUT_SECONDS = 5


@contextmanager
def database(path: Path, *, read_only: bool):
    with closing(
        duckdb.connect(
            str(path),
            read_only=read_only,
            config={
                "enable_external_access": "false",
                "memory_limit": "256MB",
                "threads": "1",
                "max_temp_directory_size": "0B",
            },
        )
    ) as connection:
        timer = Timer(TIMEOUT_SECONDS, connection.interrupt)
        timer.daemon = True
        timer.start()
        try:
            yield connection
        finally:
            timer.cancel()
            timer.join()


class ExperimentStore:
    def __init__(self, root: Path):
        self.root = root

    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.root / "experiments.sqlite3")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)"
        )
        return connection

    def get(self, experiment_id: str) -> Experiment:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM experiments WHERE id = ?", (experiment_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Experiment not found")
        return Experiment.model_validate_json(row[0])

    def list(self) -> list[Experiment]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM experiments ORDER BY rowid DESC"
            ).fetchall()
        return [Experiment.model_validate_json(row[0]) for row in rows]

    def snapshot_path(self, experiment_id: str) -> Path:
        # Resolve the ID through stored metadata before constructing a path.
        experiment = self.get(experiment_id)
        return self.root / f"{experiment.id}.duckdb"

    def create(self, draft: DatasetDraft) -> Experiment:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        experiment_id = uuid4().hex
        path = self.root / f"{experiment_id}.duckdb"
        try:
            with database(path, read_only=False) as connection:
                for table in draft.tables:
                    statements = connection.extract_statements(table.ddl)
                    if (
                        len(statements) != 1
                        or statements[0].type != duckdb.StatementType.CREATE
                    ):
                        raise ValueError(
                            "Each table requires one CREATE TABLE statement"
                        )
                    connection.execute(table.ddl)
                actual = {
                    row[0] for row in connection.execute("SHOW TABLES").fetchall()
                }
                if actual != {table.name for table in draft.tables}:
                    raise ValueError(
                        "Created tables must match the declared table names"
                    )
                statements = connection.extract_statements(draft.seed_sql)
                if not statements or any(
                    s.type != duckdb.StatementType.INSERT for s in statements
                ):
                    raise ValueError("Seed data must contain only INSERT statements")
                connection.execute(draft.seed_sql)
                # Reject views; only materialized tables may form a saved snapshot.
                if connection.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_type != 'BASE TABLE'"
                ).fetchone()[0]:
                    raise ValueError("Snapshots require materialized tables")
                total = sum(
                    connection.execute(
                        f'SELECT count(*) FROM "{table.name}"'
                    ).fetchone()[0]
                    for table in draft.tables
                )
                if total > 100000:
                    raise ValueError("Dataset exceeds the 100,000-row limit")
            experiment = Experiment(
                id=experiment_id,
                name=draft.name,
                description=draft.description,
                created_at=datetime.now(timezone.utc).isoformat(),
                tables=draft.tables,
                snapshot_sha256=sha256(path.read_bytes()).hexdigest(),
            )
            with closing(self.connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO experiments VALUES (?, ?, ?)",
                    (experiment.id, experiment.revision, experiment.model_dump_json()),
                )
            return experiment
        except Exception:
            path.unlink(missing_ok=True)
            Path(str(path) + ".wal").unlink(missing_ok=True)
            raise

    def save_queries(self, experiment_id: str, update: SaveQueries) -> Experiment:
        experiment = self.get(experiment_id)
        experiment.queries = update.queries
        experiment.revision = update.revision + 1
        with closing(self.connect()) as connection, connection:
            changed = connection.execute(
                "UPDATE experiments SET revision = ?, payload = ? WHERE id = ? AND revision = ?",
                (
                    experiment.revision,
                    experiment.model_dump_json(),
                    experiment_id,
                    update.revision,
                ),
            ).rowcount
        if not changed:
            raise ValueError(
                "Experiment changed in another tab. Reopen it before saving."
            )
        return experiment

    def run(self, experiment_id: str, sql: str) -> QueryResult:
        from time import perf_counter

        path = self.snapshot_path(experiment_id)
        if not path.is_file():
            raise ValueError("Saved dataset file is missing")
        with database(path, read_only=True) as connection:
            statements = connection.extract_statements(sql)
            if (
                len(statements) != 1
                or statements[0].type != duckdb.StatementType.SELECT
            ):
                raise ValueError("Run one read-only SELECT query at a time")
            started = perf_counter()
            cursor = connection.execute(sql)
            columns = tuple(column[0] for column in cursor.description)
            rows = cursor.fetchmany(MAX_ROWS + 1)
            if len(rows) > MAX_ROWS:
                raise ValueError(
                    f"Result exceeds {MAX_ROWS} rows. Add a LIMIT or aggregate; results were not truncated."
                )
            return QueryResult(
                columns=columns,
                rows=tuple(tuple(row) for row in rows),
                duration_ms=(perf_counter() - started) * 1000,
            )
