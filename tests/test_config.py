from __future__ import annotations

from querylab.config import Settings, default_history_db_path


def test_querylab_environment_variables_take_precedence(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INTERVIEW_LAB_LLM_PROVIDER", "claude")
    monkeypatch.setenv("QUERYLAB_LLM_PROVIDER", "codex")

    assert Settings.from_env().llm_provider == "codex"


def test_data_interview_lab_environment_variables_remain_supported(monkeypatch) -> None:
    monkeypatch.delenv("QUERYLAB_LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("DATA_INTERVIEW_LAB_LLM_TIMEOUT", "45")

    assert Settings.from_env().llm_timeout_seconds == 45


def test_existing_data_interview_lab_history_is_reused_without_copying(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("QUERYLAB_HISTORY_DB", raising=False)
    monkeypatch.delenv("DATA_INTERVIEW_LAB_HISTORY_DB", raising=False)
    monkeypatch.setattr("querylab.config.Path.home", lambda: tmp_path)
    compatibility_path = tmp_path / ".data-interview-lab" / "history.db"
    compatibility_path.parent.mkdir()
    compatibility_path.touch()

    assert default_history_db_path() == compatibility_path


def test_querylab_history_path_wins_when_both_paths_exist(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("QUERYLAB_HISTORY_DB", raising=False)
    monkeypatch.delenv("DATA_INTERVIEW_LAB_HISTORY_DB", raising=False)
    monkeypatch.setattr("querylab.config.Path.home", lambda: tmp_path)
    current_path = tmp_path / ".querylab" / "history.db"
    compatibility_path = tmp_path / ".data-interview-lab" / "history.db"
    current_path.parent.mkdir()
    compatibility_path.parent.mkdir()
    current_path.touch()
    compatibility_path.touch()

    assert default_history_db_path() == current_path


def test_sql_lab_environment_fallback(monkeypatch):
    monkeypatch.delenv("QUERYLAB_LLM_TIMEOUT", raising=False)
    monkeypatch.setenv("SQL_LAB_LLM_TIMEOUT", "73")
    monkeypatch.setenv("DATA_INTERVIEW_LAB_LLM_TIMEOUT", "45")
    assert Settings.from_env().llm_timeout_seconds == 73


def test_querylab_environment_wins_over_both_legacy_names(monkeypatch):
    monkeypatch.setenv("QUERYLAB_LLM_TIMEOUT", "90")
    monkeypatch.setenv("SQL_LAB_LLM_TIMEOUT", "73")
    monkeypatch.setenv("DATA_INTERVIEW_LAB_LLM_TIMEOUT", "45")
    assert Settings.from_env().llm_timeout_seconds == 90


def test_existing_sql_history_reused_without_moving(monkeypatch, tmp_path):
    for prefix in ("QUERYLAB_", "SQL_LAB_", "DATA_INTERVIEW_LAB_"):
        monkeypatch.delenv(prefix + "HISTORY_DB", raising=False)
    monkeypatch.setattr("querylab.config.Path.home", lambda: tmp_path)
    legacy = tmp_path / ".sql-interview-lab" / "history.db"
    legacy.parent.mkdir()
    legacy.write_bytes(b"existing history")
    assert default_history_db_path() == legacy
    assert legacy.read_bytes() == b"existing history"
    assert not (tmp_path / ".querylab").exists()
    current = tmp_path / ".querylab" / "history.db"
    current.parent.mkdir()
    current.touch()
    assert default_history_db_path() == current
