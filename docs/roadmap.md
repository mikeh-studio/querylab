# QueryLab development roadmap

QueryLab now supports three connected workflows alongside interview practice.

## Slice 1: saved datasets and free exploration

Generate a dataset without questions or reference answers, or load the offline
sample. Inspect tables, run read-only SQL, and explicitly save named queries.
Materialized DuckDB snapshots preserve the data across application restarts;
revision checks protect saved SQL from stale browser tabs.

## Slice 2: query comparison

Compare two to six saved queries on one fixed snapshot. Inspect full bounded outputs,
column differences, row differences and errors with configurable ordering and numeric
tolerance. The first selected query is a comparison baseline, not an oracle.

## Slice 3: reviewed query evaluation

Save an immutable case with an explicit expected behavior, a reviewed reference query,
one to four dataset snapshots and comparison rules. Run one to six candidates and
retain per-dataset results, candidate SQL, reference SQL, fingerprints and engine
version. Reopen past reports or compare runs for regressions and improvements.

This first evaluation slice uses reviewed reference SQL. Assertion-only cases and
AI-generated query candidates can be added later without changing the execution core.
Matching a reference on finite datasets is evidence, not proof of general correctness.
Missing or modified snapshots and reference failures invalidate that scenario; they
never count as a candidate pass.

## Later: additional data sources

- CSV/Parquet uploads with previews, explicit table names, type handling and size limits.
- Read-only external connections with explicit local snapshots for repeatable evaluation.
- Dataset controls for row counts, NULL frequency, duplicates and other edge cases.

Keep credentials out of saved experiments and exports. Native execution and dialect
emulation must remain clearly distinguished; exploration currently uses native DuckDB.
