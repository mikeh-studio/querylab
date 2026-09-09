"""Versioned experiment contracts, independent of interview questions."""

from typing import Annotated, Literal
from pydantic import Field, model_validator
from querylab.models import StrictModel, TableDefinition


Question = Annotated[str, Field(min_length=1, max_length=2000)]


class DatasetDraft(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    tables: list[TableDefinition] = Field(min_length=1, max_length=6)
    seed_sql: str = Field(min_length=1, max_length=200000)
    questions: list[Question] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def unique_tables(self):
        names = [table.name.casefold() for table in self.tables]
        if len(names) != len(set(names)):
            raise ValueError("Table names must be unique")
        return self


class SavedQuery(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    sql: str = Field(min_length=1, max_length=20000)


class Experiment(StrictModel):
    schema_version: Literal[1] = 1
    id: str
    revision: int = 1
    name: str
    description: str
    created_at: str
    snapshot_sha256: str
    tables: list[TableDefinition]
    queries: list[SavedQuery] = Field(default_factory=list, max_length=20)
    questions: list[Question] = Field(default_factory=list, max_length=12)


class SaveQueries(StrictModel):
    revision: int = Field(ge=1)
    queries: list[SavedQuery] = Field(max_length=20)

    @model_validator(mode="after")
    def unique_queries(self):
        names = [query.name for query in self.queries]
        if len(names) != len(set(names)):
            raise ValueError("Query names must be unique")
        return self


class RunQuery(StrictModel):
    sql: str = Field(min_length=1, max_length=20000)


class GenerateDataset(StrictModel):
    interpret_prompt: bool = False
    guided: bool = False
    question: str = Field(default="", max_length=2000)
    description: str = Field(min_length=1, max_length=4000)
    provider: Literal["codex", "claude"] = "codex"


class SaveQuestions(StrictModel):
    revision: int = Field(ge=1)
    questions: list[Question] = Field(max_length=12)
