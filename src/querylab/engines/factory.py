"""Execution backend routing with explicit native versus emulated modes."""

from querylab.engines.base import SQLEngine
from querylab.engines.duckdb_engine import DuckDBEngine
from querylab.engines.emulated_duckdb import EmulatedDuckDBEngine
from querylab.models import Dialect


SUPPORTED_DIALECTS = (
    Dialect.DUCKDB,
    Dialect.REDSHIFT,
    Dialect.BIGQUERY,
    Dialect.SNOWFLAKE,
    Dialect.DATABRICKS,
    Dialect.PRESTO,
)


def create_engine(dialect: Dialect) -> SQLEngine:
    if dialect is Dialect.DUCKDB:
        return DuckDBEngine()
    if dialect in SUPPORTED_DIALECTS:
        return EmulatedDuckDBEngine(dialect)
    raise ValueError(f"No execution path is configured for {dialect.value}")


def execution_mode(dialect: Dialect) -> str:
    return "native" if dialect is Dialect.DUCKDB else "emulated"
