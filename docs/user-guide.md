# QueryLab user guide

For installation and the browser workflow, start with the [README](../README.md).

## Launch options

```bash
querylab --web
querylab --web --port 9000 --no-open
```

Activate `.venv` if the command is not found. The older `sql-lab` and `data-interview-lab` commands remain aliases; Python imports use `querylab`.

## AI providers

Install and authenticate a local Codex CLI or Claude CLI before generating data. In the browser, choose it under **Settings**. The offline example needs neither provider. Direct API providers are not implemented.

For terminal practice:

```bash
querylab --llm codex
querylab --llm claude
```

Both adapters pass prompts through standard input and validate structured output. Authentication stays with the CLI; do not put credentials in this repository.

Optional configuration:

```bash
export QUERYLAB_CODEX_COMMAND='codex exec --ephemeral --sandbox read-only --skip-git-repo-check --color never'
export QUERYLAB_CLAUDE_COMMAND='claude --print --no-session-persistence --permission-mode dontAsk --tools ""'
export QUERYLAB_LLM_TIMEOUT=600
export QUERYLAB_ADVANCED_LLM_TIMEOUT=1200
```

Do not add a prompt sentinel or `--output-schema` to the Codex command; the adapter supplies them. Standard calls default to 600 seconds and Advanced interview calls to 1,200 seconds.

## Saved work

Interview history defaults to `~/.querylab/history.db`. If it does not exist, QueryLab reuses `~/.sql-interview-lab/history.db`, then `~/.data-interview-lab/history.db`, when available. Files are not copied or moved.

```bash
export QUERYLAB_HISTORY_DB='/path/to/querylab-history.db'
export QUERYLAB_HISTORY_LIMIT=200
```

`QUERYLAB_*` settings take precedence over the older `SQL_LAB_*` and `DATA_INTERVIEW_LAB_*` prefixes.

Saved datasets live in an `experiments/` directory beside the history database. Each dataset has a DuckDB snapshot, saved questions, and named SQL queries. Evaluation cases and reports live alongside this metadata. Saving SQL changes metadata, not dataset rows.

Interview history is separate. It stores exercise state, submissions, hints, and solution visibility, with a default limit of 200 sets. It also holds generation telemetry and a cache of up to 50 shared datasets. **Clear all history** removes interview sessions, telemetry, and that cache; it does not remove saved experiments. The interview interface has a **Save this session locally** option.

## Comparison and evaluation

**Compare** accepts two to six saved queries. The first selected query is the baseline. Results include execution errors and differences in columns or rows, using the selected ordering and absolute numeric tolerance rules. Boolean and numeric values are distinct, and large integer and decimal comparisons preserve precision.

**Evaluate** uses a reference query you have reviewed. Describe the expected behavior, select one to four saved datasets, enter the reference SQL, and confirm your review. Saving validates the reference against each dataset and freezes the case. To change the reference, datasets, or rules, create another case.

Evaluate one to six saved queries against a case. Reports retain the candidate SQL, reference, dataset fingerprints, rules, and engine version. Outcomes distinguish passes, mismatches, execution errors, and invalid cases. Compare saved runs by candidate name and dataset; added or removed candidates appear as absent.

Use deterministic reference queries for repeatable results. Generated questions are prompts, not trusted expectations. Assertion-only cases are not implemented.

## Interview practice

The separate `/practice` interface retains Standard and Advanced modes. Standard generates three SQL questions. Advanced adds SQL construction, debugging, and an analytical case. Its self-review rubric does not override deterministic grading.

Advanced mode opens after the first question validates while the remaining questions generate. Grading executes submitted and reference SQL in separate fresh databases across visible and hidden datasets. Hidden data and reference SQL remain server-side until the solution is revealed.

The interview interface supports native DuckDB and emulated Redshift, BigQuery, Snowflake, Databricks SQL, and Presto. Emulation translates supported SQL through SQLGlot into DuckDB; it does not connect to those warehouses or support every native feature. The main exploration workspace uses DuckDB only.

## Terminal practice

```bash
querylab --static
```

| Command | Action |
| --- | --- |
| `.run` | Run the SQL buffer on visible data. |
| `.submit` | Grade against fresh visible and hidden datasets. |
| `.schema` / `.tables` | Inspect tables. |
| `.hint` / `.solution` | Reveal help. |
| `.clear` | Clear the SQL buffer. |
| `.reset` | Recreate the visible database. |
| `.new` / `.quit` | Start another exercise or exit. |

Ending a statement with `;` runs it. Grading compares results, not SQL text.

## Limits

Keep the server on loopback: it has no authentication or per-user access controls. Never commit generated history, datasets, or credentials. See [SECURITY.md](../SECURITY.md).

Exploration accepts one read-only SELECT, disables external file access, and limits each database operation to five seconds and 256 MB of DuckDB memory. Queries returning more than 500 rows fail rather than silently truncating. Dataset creation accepts at most 100,000 rows; the generation prompt requests small datasets of at most 1,000 rows.

Uploads, external data connections, and direct AI API providers remain planned work.
