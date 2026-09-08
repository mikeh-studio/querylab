# QueryLab development roadmap

QueryLab brings generated and real data into a SQL exploration and evaluation workspace.
Saved datasets and free exploration are implemented alongside interview practice.
Query comparison and evaluation are the next two slices; uploads and connections follow.

## Slice 1: saved datasets and free exploration (implemented)

Reuse the existing schema/data models and DuckDB execution boundary. Add a dataset-only
workflow that does not require questions, reference SQL, or a grading submission.
Persist a versioned dataset snapshot and saved queries so reopening an experiment uses
the same data. Keep existing exercise generation and grading available.

Acceptance: generate or load an offline dataset, inspect tables, execute arbitrary
supported read queries, save, restart, and reopen with identical data and SQL.
Query execution must retain the current restrictions and resource limits.

## Following slices

- CSV/Parquet upload: local ingestion, explicit table names and inferred types,
  preview before import, bounded file size, and actionable parse errors.
- Evaluation: versioned cases, multiple candidate queries, reviewed reference results
  or assertions, per-dataset differences, batch execution, and comparable run reports.
- Connections: read-only credentials, bounded queries, and explicit snapshots for
  reproducible evaluation. Do not persist secrets in experiment exports or history.

Agreement between queries is not proof of correctness. An evaluation requires a
stated expectation; free exploration does not. Native execution and dialect emulation
must remain clearly distinguished. AI query generation can later supply candidates
without changing the evaluator's source of truth.
