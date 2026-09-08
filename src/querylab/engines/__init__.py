"""SQL execution backends."""

from querylab.engines.duckdb_engine import DuckDBEngine
from querylab.engines.emulated_duckdb import EmulatedDuckDBEngine
from querylab.engines.factory import (
    SUPPORTED_DIALECTS,
    create_engine,
    execution_mode,
)

__all__ = [
    "DuckDBEngine",
    "EmulatedDuckDBEngine",
    "SUPPORTED_DIALECTS",
    "create_engine",
    "execution_mode",
]
